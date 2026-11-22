import asyncio,json,os,time
SSH_PORT=int(os.environ.get("SSH_PORT","22"))
RESP=b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n"
BAN={}
BANN={}
HITS={}
LIVE={}
LIVE_DIRTY=[False]
LIVE_FILE="/tmp/isile-conns-ws.json"
# Table of the connections this process currently forwards to sshd: {local port of the upstream socket: [client ip, kind, start]}.
# The panel (root) reads it through /proc/<pid>/root/tmp and matches the port with the peer port of each sshd session,
# which is the only way to learn the real client address behind a loopback connection.
def live_add(sw,ip,kind):
    try:
        p=sw.get_extra_info("sockname")[1]
    except Exception:
        return None
    LIVE[p]=[ip,kind,int(time.time())]
    LIVE_DIRTY[0]=True
    return p
def live_del(p):
    if p is not None and LIVE.pop(p,None) is not None:
        LIVE_DIRTY[0]=True
async def live_writer():
    last=0.0
    while True:
        await asyncio.sleep(0.3)
        now=time.time()
        if not LIVE_DIRTY[0] and now-last<5:
            continue
        LIVE_DIRTY[0]=False
        last=now
        try:
            tmp=LIVE_FILE+".tmp"
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,"w") as f:
                json.dump({"t":now,"c":{str(k):v for k,v in LIVE.items()}},f)
            os.replace(tmp,LIVE_FILE)
        except Exception:
            pass
def banned(ip):
    t=BAN.get(ip)
    if t and t>time.time():
        return True
    BAN.pop(ip,None)
    return False
def strike(ip):
    now=time.time()
    if len(HITS)>20000:
        HITS.clear()
        BAN.clear()
        BANN.clear()
    h=[x for x in HITS.get(ip,[]) if now-x<60]
    h.append(now)
    HITS[ip]=h
    if len(h)>=30:
        n,t0=BANN.get(ip,(0,0))
        if now-t0>86400:
            n=0
        n+=1
        BANN[ip]=(n,now)
        BAN[ip]=now+min(600*2**(n-1),86400)
        HITS.pop(ip,None)
async def pipe(r,w):
    try:
        while True:
            d=await r.read(65536)
            if not d:
                break
            w.write(d)
            await w.drain()
    except Exception:
        pass
    finally:
        try:
            w.close()
        except Exception:
            pass
async def handle(cr,cw):
    ip="-"
    sw=None
    lp=None
    t0=time.time()
    try:
        head=await asyncio.wait_for(cr.readuntil(b"\r\n\r\n"),10)
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"x-real-ip:"):
                ip=line.split(b":",1)[1].strip().decode("ascii","ignore")[:45]
        if banned(ip):
            return
        sr,sw=await asyncio.open_connection("127.0.0.1",SSH_PORT)
        lp=live_add(sw,ip,"ws")
        cw.write(RESP)
        await cw.drain()
        await asyncio.gather(pipe(cr,sw),pipe(sr,cw))
    except Exception:
        pass
    finally:
        live_del(lp)
        for w in (cw,sw):
            try:
                if w:
                    w.close()
            except Exception:
                pass
        if time.time()-t0<5:
            strike(ip)
async def main():
    wt=asyncio.get_running_loop().create_task(live_writer())
    s=await asyncio.start_server(handle,"127.0.0.1",10022,backlog=512)
    async with s:
        await s.serve_forever()
asyncio.run(main())
