import os,re,ipaddress
LOG="/var/log/xray/access.log"
TTL=20
LONG=1800
GRACE=25
BLOCK_IDLE=120
READ_MAX=8388608
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
                if len(p)<4 or p[3]!="01":
                    continue
                try:
                    if int(p[1].rpartition(":")[2],16) not in ports:
                        continue
                    b=bytes.fromhex(p[2].rpartition(":")[0])
                    if v6:
                        a=ipaddress.IPv6Address(b"".join(b[i:i+4][::-1] for i in (0,4,8,12)))
                        if a.ipv4_mapped:
                            a=a.ipv4_mapped
                    else:
                        a=ipaddress.IPv4Address(b[::-1])
                except ValueError:
                    continue
                out.add(str(a))
    return out
class Watch:
    def __init__(self):
        self.seen={}
        self.off=0
        self.over={}
        self.blocked={}
        self.ipc={}
    def norm(self,raw):
        v=self.ipc.get(raw)
        if v is None:
            if len(self.ipc)>5000:
                self.ipc.clear()
            try:
                a=ipaddress.ip_address(raw.decode("ascii","ignore"))
                v="" if a.is_loopback else str(a)
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
        k=(m.group(4).decode("ascii","ignore"),ip)
        e=self.seen.get(k)
        if e is None:
            e=self.seen[k]=[0,0,0]
        if m.group(3)==b"block":
            e[2]=now
        else:
            if now-e[1]>TTL:
                e[0]=now
            e[1]=now
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
        if len(self.seen)>2000 or now%60<1:
            for k in [k for k,e in self.seen.items() if now-max(e[1],e[2])>LONG]:
                self.seen.pop(k,None)
    def live(self,now,estab,active):
        out={}
        cand={}
        for (n,ip),e in self.seen.items():
            if ip not in estab or ip in self.blocked.get(n,{}):
                continue
            if e[1] and now-e[1]<=TTL:
                out.setdefault(n,[]).append((e[0],ip))
            elif e[1] and now-e[1]<=LONG:
                cand.setdefault(n,[]).append((e[0],ip))
        for n,l in cand.items():
            if n not in out and n in active and len(l)==1:
                out[n]=l
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
            gone=[ip for ip,t in b.items() if now-max(t,self.seen.get((n,ip),[0,0,0])[2])>BLOCK_IDLE]
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
