import asyncio,ipaddress,os,socket,sys,time
SSH_PORT=int(os.environ.get("SSH_PORT","22"))
PUB_PORT=int(os.environ.get("MUX_PUBLIC_PORT","80"))
TLS_PORT=int(os.environ.get("MUX_TLS_PORT","10444"))
WEB_PLAIN=int(os.environ.get("MUX_WEB_PLAIN","10080"))
WEB_TLS=int(os.environ.get("MUX_WEB_TLS","10443"))
WEB_PLAIN_H2=int(os.environ.get("MUX_WEB_PLAIN_H2","10081"))
WEB_TLS_H2=int(os.environ.get("MUX_WEB_TLS_H2","10442"))
DNS_PORT=int(os.environ.get("MUX_DNS_PORT","10053"))
DNS_TLS_FRONT=int(os.environ.get("MUX_DNS_TLS_FRONT","443"))
DNS_UDP=int(os.environ.get("MUX_DNS_UDP","5302"))
DNS_ZONES=os.environ.get("MUX_DNS_ZONES","/etc/vpnpanel/dnszones")
DNS_DEFAULT=int(os.environ.get("MUX_DNS_DEFAULT","5300"))
LOCAL=("-","127.0.0.1","::1")
SNIFF=float(os.environ.get("MUX_SNIFF","2"))
MAXC=150
BAN={}
HITS={}
CONN={}
def norm(ip):
    ip=(ip or "").strip()
    if ip.lower().startswith("::ffff:") and "." in ip:
        ip=ip[7:]
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return "-"
def banned(ip):
    t=BAN.get(ip)
    if t and t>time.time():
        return True
    BAN.pop(ip,None)
    return False
def strike(ip):
    if ip=="-":
        return
    now=time.time()
    if len(HITS)>20000:
        HITS.clear()
        BAN.clear()
    h=[x for x in HITS.get(ip,[]) if now-x<60]
    h.append(now)
    HITS[ip]=h
    if len(h)>=30:
        BAN[ip]=now+600
        HITS.pop(ip,None)
def parse_proxy(line):
    p=line.decode("ascii","ignore").strip().split(" ")
    if len(p)<2 or p[0]!="PROXY":
        raise ValueError("no proxy header")
    if p[1] in ("TCP4","TCP6") and len(p)>=6:
        try:
            return norm(p[2]),int(p[4])
        except ValueError:
            pass
    return "-",0
def proxy_header(ip,sport,dport):
    if ip=="-":
        return b"PROXY UNKNOWN\r\n"
    if ":" in ip:
        return ("PROXY TCP6 %s ::1 %d %d\r\n"%(ip,sport,dport)).encode()
    return ("PROXY TCP4 %s 127.0.0.1 %d %d\r\n"%(ip,sport,dport)).encode()
async def sniff(cr):
    buf=b""
    loop=asyncio.get_running_loop()
    end=loop.time()+SNIFF
    while len(buf)<4:
        rem=end-loop.time()
        if rem<=0:
            return buf,True
        try:
            d=await asyncio.wait_for(cr.read(4096),rem)
        except asyncio.TimeoutError:
            return buf,True
        if not d:
            return buf,False
        buf+=d
    return buf,False
async def pipe(r,w):
    try:
        while True:
            d=await r.read(131072)
            if not d:
                break
            w.write(d)
            await w.drain()
    except Exception:
        try:
            w.close()
        except Exception:
            pass
        return
    try:
        if w.can_write_eof():
            w.write_eof()
        else:
            w.close()
    except Exception:
        pass
async def handle(cr,cw,tls,dns=False):
    ip="-"
    sw=None
    ssh=False
    counted=False
    t0=time.time()
    try:
        sock=cw.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1)
                sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPIDLE,60)
                sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPINTVL,15)
                sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPCNT,4)
            except OSError:
                pass
        if dns:
            ip,sport="-",0
        elif tls:
            line=await asyncio.wait_for(cr.readuntil(b"\r\n"),5)
            if len(line)>107:
                return
            ip,sport=parse_proxy(line)
        else:
            pn=cw.get_extra_info("peername") or ("-",0)
            ip,sport=norm(pn[0]),int(pn[1])
        buf,timed=await sniff(cr)
        if not buf and not timed:
            return
        ssh=buf.startswith(b"SSH-") or (timed and b"SSH-".startswith(buf))
        if ssh:
            if ip not in LOCAL:
                if banned(ip) or CONN.get(ip,0)>=MAXC:
                    return
                CONN[ip]=CONN.get(ip,0)+1
                counted=True
                t0=time.time()
            sr,sw=await asyncio.open_connection("127.0.0.1",SSH_PORT)
            sw.write(buf)
        elif dns and buf[:2]==b"\x16\x03":
            sr,sw=await asyncio.open_connection("127.0.0.1",DNS_TLS_FRONT)
            sw.write(buf)
        else:
            h2=buf.startswith(b"PRI ")
            sr,sw=await asyncio.open_connection("127.0.0.1",(WEB_TLS_H2 if h2 else WEB_TLS) if tls else (WEB_PLAIN_H2 if h2 else WEB_PLAIN))
            sw.write(proxy_header(ip,sport,443 if tls else 80)+buf)
        await sw.drain()
        await asyncio.gather(pipe(cr,sw),pipe(sr,cw))
    except Exception:
        pass
    finally:
        for w in (cw,sw):
            try:
                if w:
                    w.close()
            except Exception:
                pass
        if counted:
            n=CONN.get(ip,1)-1
            if n>0:
                CONN[ip]=n
            else:
                CONN.pop(ip,None)
            if time.time()-t0<5:
                strike(ip)
ZONES=[]
ZSTATE={"chk":0.0,"mt":None}
def load_zones():
    now=time.time()
    if now-ZSTATE["chk"]<2:
        return
    ZSTATE["chk"]=now
    try:
        mt=os.stat(DNS_ZONES).st_mtime
    except OSError:
        mt=-1
    if mt==ZSTATE["mt"]:
        return
    ZSTATE["mt"]=mt
    z=[]
    try:
        with open(DNS_ZONES) as f:
            for l in f:
                p=l.split()
                if len(p)==2 and p[1].isdigit() and 0<int(p[1])<65536:
                    z.append((p[0].lower().strip("."),int(p[1])))
    except OSError:
        pass
    z.sort(key=lambda x:-len(x[0]))
    ZONES[:]=z
def dns_qname(d):
    if len(d)<17 or d[2]&0x80 or ((d[4]<<8)|d[5])<1:
        return None
    i=12
    out=[]
    while i<len(d):
        n=d[i]
        if n==0:
            return b".".join(out).decode("ascii","ignore").lower()
        if n&0xC0 or i+1+n>len(d):
            return None
        out.append(d[i+1:i+1+n])
        i+=1+n
    return None
def dns_route(d):
    load_zones()
    if ZSTATE["mt"]==-1:
        return DNS_DEFAULT
    name=dns_qname(d)
    if not name:
        return None
    for dom,port in ZONES:
        if name==dom or name.endswith("."+dom):
            return port
    return None
class DnsFront:
    """UDP 53 is redirected here (nft). Each query goes to the tunnel server that owns its domain."""
    def __init__(self,loop):
        self.loop=loop
        self.flows={}
        s=None
        try:
            s=socket.socket(socket.AF_INET6,socket.SOCK_DGRAM)
            s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,0)
            s.bind(("::",DNS_UDP))
        except OSError:
            if s:
                s.close()
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            s.bind(("0.0.0.0",DNS_UDP))
        s.setblocking(False)
        self.s=s
        loop.add_reader(s.fileno(),self.on_query)
    def on_query(self):
        for _ in range(128):
            try:
                d,addr=self.s.recvfrom(4096)
            except (BlockingIOError,InterruptedError):
                return
            except OSError:
                return
            port=dns_route(d)
            if not port:
                continue
            key=(addr,port)
            fl=self.flows.get(key)
            if fl is None:
                if len(self.flows)>=4096:
                    self.drop(min(self.flows,key=lambda k:self.flows[k][1]))
                try:
                    u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                    u.setblocking(False)
                    u.connect(("127.0.0.1",port))
                except OSError:
                    continue
                fl=[u,0.0]
                self.flows[key]=fl
                self.loop.add_reader(u.fileno(),self.on_reply,key)
            fl[1]=time.time()
            try:
                fl[0].send(d)
            except OSError:
                pass
    def on_reply(self,key):
        fl=self.flows.get(key)
        if fl is None:
            return
        for _ in range(64):
            try:
                d=fl[0].recv(65535)
            except (BlockingIOError,InterruptedError):
                return
            except OSError:
                return
            fl[1]=time.time()
            try:
                self.s.sendto(d,key[0])
            except OSError:
                pass
    def drop(self,key):
        fl=self.flows.pop(key,None)
        if fl:
            try:
                self.loop.remove_reader(fl[0].fileno())
            except Exception:
                pass
            fl[0].close()
    async def gc(self):
        while True:
            await asyncio.sleep(30)
            now=time.time()
            for k in [k for k,v in self.flows.items() if now-v[1]>90]:
                self.drop(k)
async def main():
    servers=[]
    for host in ("0.0.0.0","::"):
        try:
            servers.append(await asyncio.start_server(lambda r,w:handle(r,w,False),host,PUB_PORT,backlog=1024))
        except OSError as e:
            if host=="0.0.0.0":
                raise
            print("IPv6 listener skipped:",e,file=sys.stderr)
    servers.append(await asyncio.start_server(lambda r,w:handle(r,w,True),"127.0.0.1",TLS_PORT,backlog=1024))
    servers.append(await asyncio.start_server(lambda r,w:handle(r,w,False,True),"127.0.0.1",DNS_PORT,backlog=1024))
    try:
        df=DnsFront(asyncio.get_running_loop())
        asyncio.get_running_loop().create_task(df.gc())
    except OSError as e:
        print("DNS front skipped:",e,file=sys.stderr)
    await asyncio.gather(*(s.serve_forever() for s in servers))
asyncio.run(main())
