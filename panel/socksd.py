import asyncio,ipaddress,json,os,secrets,signal,socket,struct,sys,time,hmac
# SOCKS5 server for "VayDNS Direct" accounts.
# It only listens on loopback: the multiplexer (sshmux.py) hands it the connections that arrive through the VayDNS tunnel
# and start with the SOCKS5 greeting (first byte 0x05). Username/password authentication (RFC 1929) is mandatory;
# the accounts come from USERS (written by the panel: active accounts only, so expired / over-quota / disabled ones are
# simply absent) and the traffic of every account is published in STATS for the panel to read.
HOST=os.environ.get("SOCKS_HOST","127.0.0.1")
PORT=int(os.environ.get("SOCKS_PORT","10054"))
USERS=os.environ.get("SOCKS_USERS","/etc/vpnpanel/socks-users.json")
STATS=os.environ.get("SOCKS_STATS","/run/vpnsocks/stats.json")
MAX_ALL=int(os.environ.get("SOCKS_MAX_CONN","8000"))
MAX_USER=int(os.environ.get("SOCKS_MAX_USER","1500"))
HANDSHAKE=float(os.environ.get("SOCKS_HANDSHAKE","15"))
CONNECT=float(os.environ.get("SOCKS_CONNECT","10"))
IDLE=float(os.environ.get("SOCKS_IDLE","1800"))
ALLOW_PRIVATE=os.environ.get("SOCKS_ALLOW_PRIVATE","0")=="1"
BLOCK_SELF=os.environ.get("SOCKS_BLOCK_SELF","1")=="1"
BOOT=secrets.token_hex(8)
ACC={}
CONNS={}
TOTAL=[0]
STAT={}
DIRTY=[False]
FAILS=[]
def log(*a):
    print(*a,file=sys.stderr,flush=True)
def load_users():
    """Returns True when the account list changed."""
    try:
        with open(USERS) as f:
            j=json.load(f)
        u=j.get("users",{})
        if not isinstance(u,dict):
            return False
        new={str(k):str(v) for k,v in u.items() if isinstance(k,str) and isinstance(v,(str,int))}
    except FileNotFoundError:
        new={}
    except (OSError,ValueError,AttributeError):
        return False
    if new==ACC:
        return False
    old=dict(ACC)
    ACC.clear()
    ACC.update(new)
    for n,ws in list(CONNS.items()):
        if n not in ACC or old.get(n)!=ACC.get(n):
            for w in list(ws):
                try:
                    w.close()
                except Exception:
                    pass
    return True
def check(user,pw):
    s=ACC.get(user)
    if s is None:
        hmac.compare_digest(pw.encode(),b"x"*8)
        return False
    return hmac.compare_digest(pw.encode(),s.encode())
def addr_ok(ip):
    try:
        a=ipaddress.ip_address(ip)
    except ValueError:
        return False
    if a.version==6 and a.ipv4_mapped:
        a=a.ipv4_mapped
    if a.is_loopback or a.is_unspecified or a.is_multicast or a.is_link_local or a.is_reserved:
        return False
    if not ALLOW_PRIVATE and not a.is_global:
        return False
    if BLOCK_SELF:
        s=None
        try:
            s=socket.socket(socket.AF_INET6 if a.version==6 else socket.AF_INET,socket.SOCK_STREAM)
            s.bind((str(a),0))
            return False
        except OSError:
            pass
        finally:
            if s:
                s.close()
    return True
async def reply(w,rep):
    w.write(b"\x05"+bytes([rep])+b"\x00\x01\x00\x00\x00\x00\x00\x00")
    await w.drain()
async def handshake(r,w):
    """Returns (user,host,port) or None. Answers the client itself on every failure."""
    h=await r.readexactly(2)
    if h[0]!=5:
        return None
    ms=await r.readexactly(h[1]) if h[1] else b""
    if 2 not in ms:
        w.write(b"\x05\xff")
        await w.drain()
        return None
    w.write(b"\x05\x02")
    await w.drain()
    a=await r.readexactly(2)
    if a[0]!=1:
        return None
    user=(await r.readexactly(a[1])).decode("utf-8","replace") if a[1] else ""
    pl=(await r.readexactly(1))[0]
    pw=(await r.readexactly(pl)).decode("utf-8","replace") if pl else ""
    if not check(user,pw):
        now=time.time()
        FAILS[:]=[t for t in FAILS if now-t<60]
        FAILS.append(now)
        if len(FAILS)<=5:
            log("auth failed for",repr(user[:32]))
        await asyncio.sleep(1 if len(FAILS)<50 else 5)
        w.write(b"\x01\x01")
        await w.drain()
        return None
    w.write(b"\x01\x00")
    await w.drain()
    q=await r.readexactly(4)
    if q[0]!=5:
        return None
    if q[1]!=1:
        await reply(w,7)
        return None
    t=q[3]
    if t==1:
        host=socket.inet_ntop(socket.AF_INET,await r.readexactly(4))
    elif t==4:
        host=socket.inet_ntop(socket.AF_INET6,await r.readexactly(16))
    elif t==3:
        n=(await r.readexactly(1))[0]
        if n==0:
            await reply(w,1)
            return None
        host=(await r.readexactly(n)).decode("utf-8","replace").strip(".")
    else:
        await reply(w,8)
        return None
    port=struct.unpack(">H",await r.readexactly(2))[0]
    if not port or not host:
        await reply(w,1)
        return None
    return user,host,port
async def dial(host,port):
    """Resolves host, drops the destinations that are not allowed, connects. Returns (reader,writer) or an int SOCKS error code."""
    loop=asyncio.get_running_loop()
    try:
        ipaddress.ip_address(host)
        ips=[host]
    except ValueError:
        try:
            inf=await asyncio.wait_for(loop.getaddrinfo(host,port,type=socket.SOCK_STREAM),CONNECT)
        except asyncio.TimeoutError:
            return 4
        except (socket.gaierror,OSError):
            return 4
        ips=[]
        for i in inf:
            if i[4][0] not in ips:
                ips.append(i[4][0])
    ips=[i for i in ips if addr_ok(i)] if ips else []
    if not ips:
        return 2
    code=1
    for ip in ips[:4]:
        try:
            return await asyncio.wait_for(asyncio.open_connection(ip,port),CONNECT)
        except asyncio.TimeoutError:
            code=6
        except ConnectionRefusedError:
            code=5
        except OSError as e:
            code=3 if e.errno==101 else 4 if e.errno==113 else 1
    return code
def tune(w,keep=False):
    s=w.get_extra_info("socket")
    if s is None:
        return
    try:
        s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
        if keep:
            s.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1)
            s.setsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPIDLE,60)
            s.setsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPINTVL,15)
            s.setsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPCNT,4)
    except OSError:
        pass
async def pump(r,w,user,idx):
    try:
        while True:
            d=await asyncio.wait_for(r.read(65536),IDLE)
            if not d:
                break
            st=STAT.setdefault(user,[0,0])
            st[idx]+=len(d)
            DIRTY[0]=True
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
async def handle(r,w):
    user=None
    sw=None
    reg=False
    try:
        if TOTAL[0]>=MAX_ALL:
            return
        TOTAL[0]+=1
        reg=True
        tune(w)
        try:
            res=await asyncio.wait_for(handshake(r,w),HANDSHAKE)
        except (asyncio.TimeoutError,asyncio.IncompleteReadError,ConnectionError):
            return
        if not res:
            return
        user,host,port=res
        if len(CONNS.get(user,())) >= MAX_USER:
            await reply(w,1)
            return
        d=await dial(host,port)
        if isinstance(d,int):
            await reply(w,d)
            return
        sr,sw=d
        tune(sw,True)
        if user not in ACC:
            return
        CONNS.setdefault(user,set()).update((w,sw))
        await reply(w,0)
        await asyncio.gather(pump(r,sw,user,0),pump(sr,w,user,1))
    except Exception:
        pass
    finally:
        if reg:
            TOTAL[0]-=1
        for x in (w,sw):
            if x is None:
                continue
            if user and user in CONNS:
                CONNS[user].discard(x)
            try:
                x.close()
            except Exception:
                pass
        if user and user in CONNS and not CONNS[user]:
            CONNS.pop(user,None)
def write_stats():
    try:
        os.makedirs(os.path.dirname(STATS),exist_ok=True)
        tmp=STATS+".tmp"
        with open(tmp,"w") as f:
            json.dump({"boot":BOOT,"t":int(time.time()),"u":STAT},f)
        os.chmod(tmp,0o644)
        os.replace(tmp,STATS)
        DIRTY[0]=False
    except OSError as e:
        log("cannot write stats:",e)
async def housekeeping():
    n=0
    while True:
        await asyncio.sleep(1)
        n+=1
        load_users()
        if n%2==0 and DIRTY[0]:
            write_stats()
async def main():
    load_users()
    write_stats()
    srv=await asyncio.start_server(handle,HOST,PORT,backlog=1024)
    loop=asyncio.get_running_loop()
    stop=asyncio.Event()
    for sg in (signal.SIGTERM,signal.SIGINT):
        loop.add_signal_handler(sg,stop.set)
    t=loop.create_task(housekeeping())
    log("SOCKS5 listening on %s:%d"%(HOST,PORT))
    await stop.wait()
    t.cancel()
    srv.close()
    write_stats()
asyncio.run(main())
