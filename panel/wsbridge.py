import asyncio,os,time
SSH_PORT=int(os.environ.get("SSH_PORT","22"))
RESP=b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n"
BAN={}
HITS={}
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
    h=[x for x in HITS.get(ip,[]) if now-x<60]
    h.append(now)
    HITS[ip]=h
    if len(h)>=30:
        BAN[ip]=now+600
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
    t0=time.time()
    try:
        head=await asyncio.wait_for(cr.readuntil(b"\r\n\r\n"),10)
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"x-real-ip:"):
                ip=line.split(b":",1)[1].strip().decode("ascii","ignore")[:45]
        if banned(ip):
            return
        sr,sw=await asyncio.open_connection("127.0.0.1",SSH_PORT)
        cw.write(RESP)
        await cw.drain()
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
        if time.time()-t0<5:
            strike(ip)
async def main():
    s=await asyncio.start_server(handle,"127.0.0.1",10022,backlog=512)
    async with s:
        await s.serve_forever()
asyncio.run(main())
