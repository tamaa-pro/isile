import asyncio,ipaddress,os,socket,sys,time
SSH_PORT=int(os.environ.get("SSH_PORT","22"))
PUB_PORT=int(os.environ.get("MUX_PUBLIC_PORT","80"))
TLS_PORT=int(os.environ.get("MUX_TLS_PORT","10444"))
WEB_PLAIN=int(os.environ.get("MUX_WEB_PLAIN","10080"))
WEB_TLS=int(os.environ.get("MUX_WEB_TLS","10443"))
WEB_PLAIN_H2=int(os.environ.get("MUX_WEB_PLAIN_H2","10081"))
WEB_TLS_H2=int(os.environ.get("MUX_WEB_TLS_H2","10442"))
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
async def handle(cr,cw,tls):
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
            except OSError:
                pass
        if tls:
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
            if banned(ip) or CONN.get(ip,0)>=MAXC:
                return
            CONN[ip]=CONN.get(ip,0)+1
            counted=True
            t0=time.time()
            sr,sw=await asyncio.open_connection("127.0.0.1",SSH_PORT)
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
    await asyncio.gather(*(s.serve_forever() for s in servers))
asyncio.run(main())
