import os,re,json,ipaddress
LOG="/var/log/xray/access.log"
STATE="/var/lib/vpnpanel/v2claims.json"
GRACE=90
BLOCK_IDLE=120
LONG=1800
NEW=10
WAIT=6
DEAD=3
READ_MAX=8388608
WANT_MAX=20000
LINE=re.compile(rb"from (?:tcp:|udp:)?(?:\[([0-9a-fA-F:.]+)\]|([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)):\d+ accepted .*?\[[^\]]*?(?:>>|->)\s*([^\]\s]+)\s*\]\s*email:\s*(\S+)")
def established(ports=(80,443)):
    out=set()
    for f,v6 in (("/proc/net/tcp",False),("/proc/net/tcp6",True)):
        try:
            fh=open(f)
        except OSError:
            continue
        with fh:
            next(fh,None)
            for l in fh:
                p=l.split()
                if len(p)<7 or p[3]!="01":
                    continue
                try:
                    if int(p[1].rpartition(":")[2],16) not in ports:
                        continue
                    if int(p[6])>=DEAD:
                        continue
                    h,_,pt=p[2].rpartition(":")
                    b=bytes.fromhex(h)
                    if v6:
                        a=ipaddress.IPv6Address(b"".join(b[i:i+4][::-1] for i in (0,4,8,12)))
                        if a.ipv4_mapped:
                            a=a.ipv4_mapped
                    else:
                        a=ipaddress.IPv4Address(b[::-1])
                    out.add((str(a),int(pt,16)))
                except ValueError:
                    continue
    return out
class Watch:
    def __init__(self,state=STATE):
        self.state=state
        self.off=0
        self.first={}
        self.claim={}
        self.want=[]
        self.blk={}
        self.over={}
        self.blocked={}
        self.ipc={}
        self.loop=0
        self.real=0
        self.saved=0
        self.dirty=False
        self.boot=self.load()
    def load(self):
        try:
            with open(self.state) as f:
                d=json.load(f)
            return {(ip,int(pt)):(n,float(t)) for ip,pt,n,t in d}
        except (OSError,ValueError,TypeError):
            return {}
    def save(self,now):
        if not self.dirty or now-self.saved<10:
            return
        self.saved=now
        self.dirty=False
        try:
            tmp=self.state+".tmp"
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,"w") as f:
                json.dump([[ip,pt,n,self.first.get((ip,pt),now)] for (ip,pt),n in self.claim.items()],f)
            os.replace(tmp,self.state)
        except OSError:
            pass
    def norm(self,raw):
        v=self.ipc.get(raw)
        if v is None:
            if len(self.ipc)>5000:
                self.ipc.clear()
            try:
                a=ipaddress.ip_address(raw.decode("ascii","ignore"))
                v="lo" if a.is_loopback else str(a)
            except ValueError:
                v=""
            self.ipc[raw]=v
        return v
    def line(self,s,now):
        m=LINE.search(s)
        if not m:
            return
        ip=self.norm(m.group(1) or m.group(2))
        if not ip:
            return
        if ip=="lo":
            self.loop+=1
            return
        self.real+=1
        n=m.group(4).decode("ascii","ignore")
        if m.group(3)==b"block":
            self.blk[(n,ip)]=now
        elif len(self.want)<WANT_MAX:
            self.want.append([n,ip,now])
    def ingest(self,now):
        try:
            size=os.stat(LOG).st_size
        except OSError:
            return
        if size<self.off:
            self.off=0
        if size>self.off:
            try:
                with open(LOG,"rb") as f:
                    f.seek(self.off)
                    data=f.read(min(size-self.off,READ_MAX))
            except OSError:
                return
            cut=data.rfind(b"\n")
            if cut>=0:
                self.off+=cut+1
                for s in data[:cut].replace(b"\x00",b"").split(b"\n"):
                    self.line(s,now)
        try:
            if self.off and os.stat(LOG).st_size==self.off:
                os.truncate(LOG,0)
                self.off=0
        except OSError:
            pass
        if len(self.blk)>2000 or now%60<1:
            for k in [k for k,t in self.blk.items() if now-t>LONG]:
                self.blk.pop(k,None)
    def sync(self,now,socks):
        for k in [k for k in self.first if k not in socks]:
            self.first.pop(k,None)
            if self.claim.pop(k,None) is not None:
                self.dirty=True
        for k in socks:
            if k not in self.first:
                b=self.boot.get(k)
                self.first[k]=b[1] if b else now
                if b and k not in self.claim:
                    self.claim[k]=b[0]
        self.boot={}
        byip={}
        for k in socks:
            if k not in self.claim:
                byip.setdefault(k[0],[]).append(k)
        have=set((n,k[0]) for k,n in self.claim.items())
        keep=[]
        for ev in self.want:
            n,ip,t=ev
            free=byip.get(ip)
            pick=None
            if free:
                new=[k for k in free if now-self.first[k]<=NEW]
                if new:
                    pick=min(new,key=lambda k:self.first[k])
                elif (n,ip) not in have:
                    pick=max(free,key=lambda k:self.first[k])
            if pick:
                free.remove(pick)
                self.claim[pick]=n
                have.add((n,ip))
                self.dirty=True
            elif now-t<WAIT:
                keep.append(ev)
        self.want=keep
        self.save(now)
    def live(self,now,socks):
        self.sync(now,socks)
        since={}
        for k,n in self.claim.items():
            if k[0] in self.blocked.get(n,{}):
                continue
            key=(n,k[0])
            t=self.first.get(k,now)
            if key not in since or t<since[key]:
                since[key]=t
        out={}
        for (n,ip),t in since.items():
            out.setdefault(n,[]).append((t,ip))
        for l in out.values():
            l.sort()
        return out
    def plan(self,limits,live,now):
        add=[]
        rem=[]
        for n in list(self.blocked):
            if n not in limits:
                rem+=[(n,ip) for ip in self.blocked[n]]
                self.over.pop(n,None)
        for n in list(self.over):
            if n not in limits:
                self.over.pop(n,None)
        for n,L in limits.items():
            b=self.blocked.get(n,{})
            gone=[ip for ip,t in b.items() if now-max(t,self.blk.get((n,ip),0))>BLOCK_IDLE]
            rem+=[(n,ip) for ip in gone]
            cur=live.get(n,[])
            if len(cur)>L:
                t0=self.over.setdefault(n,now)
                if now-t0>=GRACE:
                    add+=[(n,ip) for since,ip in cur[L:]]
            else:
                self.over.pop(n,None)
                room=L-len(cur)
                if room>0:
                    rest=sorted((t,ip) for ip,t in b.items() if ip not in gone)
                    rem+=[(n,ip) for t,ip in rest[:room]]
        return add,rem
    def confirm_add(self,n,ip,now):
        self.blocked.setdefault(n,{})[ip]=now
    def confirm_rem(self,n,ip):
        b=self.blocked.get(n)
        if b:
            b.pop(ip,None)
            if not b:
                self.blocked.pop(n,None)
