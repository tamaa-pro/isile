import json,os,signal,socket,struct,time
# Counts live SSH connections of the panel accounts straight from the kernel (/proc), whatever transport carried them.
# One connection = one authenticated sshd process (uid of the account) whose parent is the root sshd monitor.
# For each of them we also work out the real client address and the transport:
#   - peer is not loopback            -> direct SSH, the peer is the client
#   - peer is a local front-end port  -> wsbridge / sshmux publish {upstream port: client ip, kind} in their private /tmp
#   - socket owned by udp-custom, stunnel or a DNS tunnel server -> transport known, client address not
# and whether data moved recently (rchar+wchar of the sshd process).
ACT_MIN=400    # bytes in one scan that count as traffic (an idle keepalive is far smaller)
ACT_WIN=20     # seconds a session stays "active" after its last traffic
FRONT_FILES=("tmp/isile-conns-ws.json","tmp/isile-conns-mux.json")
FRONT_SCRIPTS=("wsbridge.py","sshmux.py")
OWNER_COMM={"udp-custom":"udp","stunnel":"ssl","stunnel4":"ssl","vaydns-server":"dns"}
IO={}
HZ=os.sysconf("SC_CLK_TCK") if hasattr(os,"sysconf") else 100
def _uptime():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (OSError,ValueError):
        return 0.0
def _ip(h):
    try:
        if len(h)==8:
            return socket.inet_ntoa(struct.pack("<I",int(h,16)))
        b=b"".join(bytes.fromhex(h[i:i+8])[::-1] for i in range(0,32,8))
        if b[:12]==b"\0"*10+b"\xff\xff":
            return socket.inet_ntoa(b[12:])
        return socket.inet_ntop(socket.AF_INET6,b)
    except (ValueError,OSError,struct.error):
        return "-"
def _loop(ip):
    return ip=="::1" or ip.startswith("127.")
def tcp_table():
    """inode -> (local ip, local port, remote ip, remote port) of every ESTABLISHED TCP socket."""
    out={}
    for fn in ("/proc/net/tcp","/proc/net/tcp6"):
        try:
            with open(fn) as f:
                next(f,None)
                for l in f:
                    z=l.split()
                    if len(z)<10 or z[3]!="01":
                        continue
                    la,_,lp=z[1].partition(":")
                    ra,_,rp=z[2].partition(":")
                    out[int(z[9])]=(la,int(lp,16),ra,int(rp,16))
        except (OSError,ValueError):
            continue
    return out
def sock_inodes(pid):
    s=set()
    try:
        d="/proc/%s/fd/"%pid
        for fd in os.listdir(d):
            try:
                t=os.readlink(d+fd)
            except OSError:
                continue
            if t.startswith("socket:["):
                s.add(int(t[8:-1]))
    except (OSError,ValueError):
        pass
    return s
def _uid(pid):
    with open("/proc/%s/status"%pid) as f:
        for l in f:
            if l.startswith("Uid:"):
                return int(l.split()[1])
    return None
def _io(pid):
    t=0
    with open("/proc/%s/io"%pid) as f:
        for l in f:
            if l.startswith(("rchar:","wchar:")):
                t+=int(l.split()[1])
    return t
def front_tables(pids):
    out={}
    for p in pids:
        for fn in FRONT_FILES:
            try:
                with open("/proc/%s/root/%s"%(p,fn)) as f:
                    c=json.load(f).get("c",{})
            except (OSError,ValueError,AttributeError):
                continue
            for k,v in c.items():
                try:
                    out[int(k)]=(str(v[0]),str(v[1]))
                except (ValueError,IndexError,TypeError):
                    continue
    return out
def scan(uids):
    """{uid: [ {pid, st, ip, via, act, age} ... ]} oldest connection first. ip is "-" when the client address is unknown."""
    want=set(uids)
    out={}
    now=time.time()
    if not want:
        IO.clear()
        return out
    try:
        names=os.listdir("/proc")
    except OSError:
        return out
    cand=[]
    fronts=[]
    owners=[]
    for n in names:
        if not n.isdigit():
            continue
        try:
            with open("/proc/%s/comm"%n) as f:
                comm=f.read().strip()
            if comm.startswith("sshd"):
                if _uid(n) in want:
                    cand.append(n)
            elif comm.startswith("python"):
                with open("/proc/%s/cmdline"%n,"rb") as f:
                    cl=f.read().split(b"\0")
                if any(x.decode("utf-8","replace").endswith(FRONT_SCRIPTS) for x in cl[1:3]):
                    fronts.append(n)
            elif comm in OWNER_COMM:
                owners.append((n,comm))
        except (OSError,ValueError):
            continue
    up=_uptime()
    ses=[]
    for n in cand:
        try:
            uid=_uid(n)
            with open("/proc/%s/stat"%n) as f:
                z=f.read().rpartition(")")[2].split()
            st=int(z[19])
            pp=z[1]
            # forked helper children (same uid and name) and orphans reparented to init are not connections.
            with open("/proc/%s/comm"%pp) as f:
                if not f.read().startswith("sshd"):
                    continue
            if _uid(pp)!=0:
                continue
        except (OSError,ValueError,IndexError):
            continue
        ses.append((uid,st,int(n),pp))
    if not ses:
        IO.clear()
        return out
    tcp=tcp_table()
    ft=front_tables(fronts)
    pin={}
    own=None
    rev={}
    seen=set()
    for uid,st,pid,pp in ses:
        ip,via="-","ssh"
        try:
            if pp not in pin:
                pin[pp]=sock_inodes(pp)
            cs=[i for i in sock_inodes(pid)&pin[pp] if i in tcp]
            if cs:
                _,lport,ra,rport=tcp[cs[0]]
                rip=_ip(ra)
                if not _loop(rip):
                    ip,via=rip,"direct"
                else:
                    f=ft.get(rport)
                    if f:
                        ip,via=f[0],f[1]
                    else:
                        if own is None:
                            own={}
                            for p,c in owners:
                                k=OWNER_COMM[c]
                                if k=="dns":
                                    try:
                                        if "slowdns" in os.readlink("/proc/%s/exe"%p):
                                            k="slowdns"
                                    except OSError:
                                        pass
                                for i in sock_inodes(p):
                                    own[i]=k
                            for i,(la2,lp2,ra2,rp2) in tcp.items():
                                if i in own:
                                    rev[(lp2,rp2)]=i
                        i=rev.get((rport,lport))
                        if i is not None:
                            via=own[i]
        except (OSError,ValueError):
            pass
        act=False
        try:
            tot=_io(pid)
            old=IO.get(pid)
            if old and old[2]==st:
                last=now if tot-old[0]>=ACT_MIN else old[1]
            else:
                last=0
            IO[pid]=(tot,last,st)
            act=now-last<ACT_WIN
        except (OSError,ValueError):
            pass
        seen.add(pid)
        out.setdefault(uid,[]).append({"pid":pid,"st":st,"ip":ip,"via":via,"act":act,"age":max(0.0,up-st/HZ)})
    for k in [k for k in IO if k not in seen]:
        del IO[k]
    for v in out.values():
        v.sort(key=lambda x:(x["st"],x["pid"]))
    return out
def kill(pid):
    try:
        os.kill(pid,signal.SIGKILL)
        return True
    except OSError:
        return False
