import os,sys,re,json,time,uuid,hmac,base64,secrets,shutil,sqlite3,ipaddress,functools,threading,traceback,subprocess
from datetime import timedelta
from urllib.parse import quote
from flask import Flask,request,session,jsonify,render_template,redirect
from werkzeug.security import generate_password_hash,check_password_hash
BASE=os.path.dirname(os.path.abspath(__file__))
DATA="/var/lib/vpnpanel"
DBP=DATA+"/panel.db"
XCONF="/usr/local/etc/xray/config.json"
XBIN="/usr/local/bin/xray"
XAPI="127.0.0.1:10085"
UID0=20000
UID1=60000
GB=1073741824
V2=("vless","vmess","trojan")
PROTOS=("ssh",)+V2
MODES=("tls","plain")
PORTS={("vless","tls"):10001,("trojan","tls"):10002,("vmess","tls"):10003,("vless","plain"):10011,("trojan","plain"):10012,("vmess","plain"):10013}
NAME_RE=re.compile(r"^[a-z][a-z0-9_]{2,19}$")
SECRET_RE=re.compile(r"^[A-Za-z0-9@#%_.+=-]{6,64}$")
UUID_RE=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ALNUM="abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LOCK=threading.RLock()
FAILS={}
ONLINE={}
SEEN={}
CPU={}
try:
    with open(BASE+"/VERSION") as f:
        VERSION=f.read().strip()
except OSError:
    VERSION="0"
app=Flask(__name__,template_folder=BASE+"/templates",static_folder=BASE+"/static",static_url_path="/static")
def db():
    c=sqlite3.connect(DBP,timeout=30)
    c.row_factory=sqlite3.Row
    return c
def init_db():
    os.makedirs(DATA,mode=0o700,exist_ok=True)
    c=db()
    c.executescript("""CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(name TEXT PRIMARY KEY,proto TEXT NOT NULL,secret TEXT NOT NULL,uid INTEGER,created INTEGER NOT NULL,expires INTEGER NOT NULL DEFAULT 0,quota INTEGER NOT NULL DEFAULT 0,up INTEGER NOT NULL DEFAULT 0,down INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'active',manual INTEGER NOT NULL DEFAULT 0,note TEXT NOT NULL DEFAULT '');""")
    cols={r["name"] for r in c.execute("PRAGMA table_info(accounts)")}
    if "tls" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN tls TEXT NOT NULL DEFAULT 'tls'")
    if "maxdev" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN maxdev INTEGER NOT NULL DEFAULT 0")
    c.execute("UPDATE accounts SET tls='both' WHERE proto='ssh' AND tls<>'both'")
    c.commit()
    c.close()
    os.chmod(DBP,0o600)
    if not get("secret_key"):
        put("secret_key",secrets.token_hex(32))
def get(k,d=None):
    c=db()
    r=c.execute("SELECT v FROM settings WHERE k=?",(k,)).fetchone()
    c.close()
    return r["v"] if r else d
def put(k,v):
    c=db()
    c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(k,v))
    c.commit()
    c.close()
def sh(args,inp=None):
    return subprocess.run(args,input=inp,capture_output=True,text=True,timeout=40)
def gen_pass():
    return "".join(secrets.choice(ALNUM) for _ in range(14))
def calc(r,now):
    if r["manual"]:
        return "disabled"
    if r["expires"] and r["expires"]<=now:
        return "expired"
    if r["quota"] and r["up"]+r["down"]>=r["quota"]:
        return "limit"
    return "active"
def sysuser_exists(n):
    return sh(["getent","passwd",n]).returncode==0
def next_uid(c):
    m=c.execute("SELECT MAX(uid) m FROM accounts").fetchone()["m"]
    u=max(UID0,(m or 0)+1)
    while sh(["getent","passwd",str(u)]).returncode==0:
        u+=1
    if u>=UID1:
        raise RuntimeError("no free uid")
    return u
def ssh_add(n,pw,uid):
    r=sh(["useradd","-M","-N","-g","vpnusers","-s","/usr/sbin/nologin","-u",str(uid),n])
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "useradd failed")
    r=sh(["chpasswd"],inp=n+":"+pw+"\n")
    if r.returncode:
        sh(["userdel","-f",n])
        raise RuntimeError(r.stderr.strip() or "chpasswd failed")
def ssh_pass(n,pw):
    sh(["chpasswd"],inp=n+":"+pw+"\n")
    sh(["pkill","-KILL","-u",n])
def ssh_lock(n,lock):
    sh(["usermod","-L" if lock else "-U",n])
    if lock:
        sh(["pkill","-KILL","-u",n])
def ssh_del(n):
    r=sh(["id","-u",n])
    if r.returncode==0 and r.stdout.strip().isdigit() and UID0<=int(r.stdout.strip())<UID1:
        sh(["pkill","-KILL","-u",n])
        time.sleep(0.3)
        sh(["userdel","-f",n])
def nft_apply(c):
    uids=[r["uid"] for r in c.execute("SELECT uid FROM accounts WHERE proto='ssh' AND uid IS NOT NULL")]
    rng="meta skuid >= %d meta skuid < %d"%(UID0,UID1)
    L=["table inet vpnacct","delete table inet vpnacct","table inet vpnacct {"]
    L.append(" set blk4 { type ipv4_addr; flags timeout; }")
    L.append(" set blk6 { type ipv6_addr; flags timeout; }")
    for u in uids:
        L.append(" counter cu%d { }"%u)
        L.append(" counter cd%d { }"%u)
    L.append(" chain out {")
    L.append("  type filter hook output priority -150; policy accept;")
    L.append("  "+rng+" meta l4proto { tcp, udp } th dport 53 accept")
    L.append("  "+rng+" ip daddr { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.168.0.0/16 } drop")
    L.append("  "+rng+" ip6 daddr { ::1, fc00::/7, fe80::/10 } drop")
    for u in uids:
        L.append('  meta skuid %d counter name "cu%d" ct mark set %d'%(u,u,u))
    L.append(" }")
    L.append(" chain in {")
    L.append("  type filter hook input priority -150; policy accept;")
    L.append("  ip saddr @blk4 tcp dport { 80, 443 } drop")
    L.append("  ip6 saddr @blk6 tcp dport { 80, 443 } drop")
    for u in uids:
        L.append('  ct mark %d counter name "cd%d"'%(u,u))
    L.append(" }")
    L.append("}")
    r=sh(["nft","-f","-"],inp="\n".join(L)+"\n")
    if r.returncode:
        print("nft error:",r.stderr,file=sys.stderr)
def block_ip(ip):
    try:
        a=ipaddress.ip_address(ip)
    except ValueError:
        return
    sh(["nft","add","element","inet","vpnacct","blk6" if a.version==6 else "blk4","{ %s timeout 5m }"%a])
def harvest_nft():
    r=sh(["nft","-j","reset","counters","table","inet","vpnacct"])
    out={}
    if r.returncode:
        return out
    try:
        items=json.loads(r.stdout or "{}").get("nftables",[])
    except ValueError:
        return out
    for it in items:
        k=it.get("counter")
        if not k:
            continue
        m=re.match(r"c([ud])(\d+)$",k.get("name",""))
        if m:
            out.setdefault(int(m.group(2)),[0,0])[0 if m.group(1)=="u" else 1]+=int(k.get("bytes",0))
    return out
def xray_running():
    return sh(["systemctl","is-active","--quiet","xray"]).returncode==0
def harvest_xray():
    out={}
    if not xray_running():
        return out
    r=sh([XBIN,"api","statsquery","-s",XAPI,"-pattern","user>>>","-reset=true"])
    if r.returncode:
        return out
    try:
        arr=json.loads(r.stdout or "{}").get("stat",[])
    except ValueError:
        return out
    for s in arr:
        m=re.match(r"user>>>(.+)>>>traffic>>>(uplink|downlink)$",s.get("name",""))
        if m:
            out.setdefault(m.group(1),[0,0])[0 if m.group(2)=="uplink" else 1]+=int(s.get("value",0) or 0)
    return out
def collect(c):
    with LOCK:
        x=harvest_xray()
        s=harvest_nft()
        um={r["uid"]:r["name"] for r in c.execute("SELECT name,uid FROM accounts WHERE uid IS NOT NULL")}
        for n,(u,d) in x.items():
            c.execute("UPDATE accounts SET up=up+?,down=down+? WHERE name=?",(u,d,n))
        for uid,(u,d) in s.items():
            n=um.get(uid)
            if n:
                c.execute("UPDATE accounts SET up=up+?,down=down+? WHERE name=?",(u,d,n))
        c.commit()
def client_of(r):
    if r["proto"]=="trojan":
        return {"password":r["secret"],"email":r["name"],"level":0}
    o={"id":r["secret"],"email":r["name"],"level":0}
    if r["proto"]=="vmess":
        o["alterId"]=0
    return o
def placeholder(sk,p,m):
    h=uuid.uuid5(uuid.NAMESPACE_URL,sk+p+m)
    e="placeholder-%s-%s"%(p,m)
    if p=="trojan":
        return {"password":h.hex,"email":e,"level":0}
    o={"id":str(h),"email":e,"level":0}
    if p=="vmess":
        o["alterId"]=0
    return o
def xray_conf(c):
    sk=get("secret_key")
    cl={(p,m):[] for p in V2 for m in MODES}
    for r in c.execute("SELECT * FROM accounts WHERE status='active' AND proto IN ('vless','vmess','trojan') ORDER BY name"):
        for m in (MODES if r["tls"]=="both" else (r["tls"],)):
            if (r["proto"],m) in cl:
                cl[(r["proto"],m)].append(client_of(r))
    inb=[{"tag":"api","listen":"127.0.0.1","port":10085,"protocol":"dokodemo-door","settings":{"address":"127.0.0.1"}}]
    for p in V2:
        for m in MODES:
            st={"clients":cl[(p,m)] or [placeholder(sk,p,m)]}
            if p=="vless":
                st["decryption"]="none"
            inb.append({"tag":p+"-"+m,"listen":"127.0.0.1","port":PORTS[(p,m)],"protocol":p,"settings":st,"streamSettings":{"network":"ws","wsSettings":{"path":"/"+p}}})
    return {
        "log":{"loglevel":"warning"},
        "stats":{},
        "api":{"tag":"api","services":["StatsService"]},
        "policy":{"levels":{"0":{"statsUserUplink":True,"statsUserDownlink":True,"statsUserOnline":True}}},
        "inbounds":inb,
        "outbounds":[{"tag":"direct","protocol":"freedom"},{"tag":"block","protocol":"blackhole"}],
        "routing":{"domainStrategy":"IPIfNonMatch","rules":[
            {"type":"field","inboundTag":["api"],"outboundTag":"api"},
            {"type":"field","ip":["geoip:private"],"outboundTag":"block"}]}}
def write_xray_conf(c):
    txt=json.dumps(xray_conf(c),indent=1,sort_keys=True)
    try:
        with open(XCONF) as f:
            old=f.read()
    except OSError:
        old=None
    if old==txt:
        return False
    os.makedirs(os.path.dirname(XCONF),exist_ok=True)
    tmp=XCONF+".tmp"
    with open(tmp,"w") as f:
        f.write(txt)
    os.chmod(tmp,0o640)
    shutil.chown(tmp,"root","xray")
    os.replace(tmp,XCONF)
    return True
def xray_sync(c):
    with LOCK:
        changed=write_xray_conf(c)
        run=xray_running()
        if run and not changed:
            return
        if run:
            collect(c)
        sh(["systemctl","restart","xray"])
def reconcile(c):
    with LOCK:
        now=int(time.time())
        for r in c.execute("SELECT * FROM accounts").fetchall():
            new=calc(r,now)
            if new==r["status"]:
                continue
            c.execute("UPDATE accounts SET status=? WHERE name=?",(new,r["name"]))
            c.commit()
            if r["proto"]=="ssh":
                ssh_lock(r["name"],new!="active")
        c.commit()
        xray_sync(c)
def ssh_sessions():
    out={}
    r=sh(["ps","-eo","user:32=,pid=,etimes=,comm="])
    for l in r.stdout.splitlines():
        p=l.split()
        if len(p)>=4 and p[3].startswith("sshd") and p[0]!="root" and p[1].isdigit() and p[2].isdigit():
            out.setdefault(p[0],[]).append((int(p[2]),int(p[1])))
    return out
def find_ips(o):
    if isinstance(o,dict):
        if isinstance(o.get("ips"),dict):
            return o["ips"]
        for v in o.values():
            x=find_ips(v)
            if x is not None:
                return x
    return None
def v2_ips(name):
    r=sh([XBIN,"api","statsonlineiplist","-s",XAPI,"-email="+name])
    if r.returncode:
        return []
    try:
        ips=find_ips(json.loads(r.stdout or "{}"))
    except ValueError:
        return []
    return list(ips) if ips else []
def v2_limit(name,ips,maxdev):
    now=time.time()
    seen=SEEN.setdefault(name,{})
    for ip in list(seen):
        if ip not in ips:
            seen.pop(ip,None)
    for ip in ips:
        seen.setdefault(ip,now)
    if maxdev and len(seen)>maxdev:
        for ip in sorted(seen,key=lambda i:seen[i])[maxdev:]:
            block_ip(ip)
def update_online(c):
    global ONLINE
    rows=c.execute("SELECT name,proto,maxdev FROM accounts WHERE status='active'").fetchall()
    ssh=ssh_sessions()
    xr=xray_running()
    on={}
    for r in rows:
        n=r["name"]
        if r["proto"]=="ssh":
            s=sorted(ssh.get(n,[]))
            ex=len(s)-r["maxdev"] if r["maxdev"] else 0
            if ex>0:
                for et,pid in s[:ex]:
                    sh(["kill","-KILL",str(pid)])
                s=s[ex:]
            on[n]=len(s)
        elif xr:
            ips=v2_ips(n)
            on[n]=len(ips)
            v2_limit(n,ips,r["maxdev"])
    ONLINE=on
def worker():
    n=0
    while True:
        time.sleep(10)
        n+=1
        try:
            with LOCK:
                c=db()
                try:
                    update_online(c)
                    if n%3==0:
                        collect(c)
                        reconcile(c)
                finally:
                    c.close()
        except Exception:
            traceback.print_exc()
def err(code,status=400,detail=None):
    return jsonify(error=code,detail=detail),status
def valid_session():
    h=get("admin_hash","")
    return bool(session.get("u")) and session.get("ph")==h[:16]
def auth(f):
    @functools.wraps(f)
    def w(*a,**k):
        if not valid_session():
            return err("unauthorized",401)
        if request.method!="GET" and not hmac.compare_digest(request.headers.get("X-CSRF",""),session.get("csrf","")):
            return err("csrf",403)
        return f(*a,**k)
    return w
def client_ip():
    return request.headers.get("X-Real-IP") or request.remote_addr or "-"
def blocked(ip):
    f=FAILS.get(ip)
    return bool(f and f[0]>=5 and time.time()-f[1]<900)
def fail(ip):
    now=time.time()
    for k in [k for k,v in FAILS.items() if now-v[1]>900]:
        FAILS.pop(k,None)
    f=FAILS.get(ip,[0,now])
    FAILS[ip]=[f[0]+1,now]
@app.after_request
def headers(r):
    if request.path.startswith("/static/fa/"):
        r.headers["Cache-Control"]="public, max-age=604800"
    else:
        r.headers["Cache-Control"]="no-store"
    return r
@app.route("/login",methods=["GET","POST"])
def login():
    if not session.get("csrf"):
        session["csrf"]=secrets.token_hex(16)
    if request.method=="GET":
        return render_template("login.html",csrf=session["csrf"],err="",version=VERSION)
    ip=client_ip()
    if blocked(ip):
        return render_template("login.html",csrf=session["csrf"],err="too_many",version=VERSION),429
    if not hmac.compare_digest(request.form.get("csrf",""),session["csrf"]):
        return render_template("login.html",csrf=session["csrf"],err="session_expired",version=VERSION),403
    u=request.form.get("username","")
    p=request.form.get("password","")
    ok_u=hmac.compare_digest(u.encode(),get("admin_user","").encode())
    ok_p=check_password_hash(get("admin_hash",""),p)
    if ok_u and ok_p:
        FAILS.pop(ip,None)
        session.clear()
        session.permanent=True
        session["u"]=1
        session["csrf"]=secrets.token_hex(16)
        session["ph"]=get("admin_hash")[:16]
        return redirect("/")
    fail(ip)
    time.sleep(0.5)
    return render_template("login.html",csrf=session["csrf"],err="bad_login",version=VERSION),401
@app.get("/")
def index():
    if not valid_session():
        return redirect("/login")
    return render_template("index.html",csrf=session["csrf"],domain=get("domain",""),version=VERSION)
@app.post("/api/logout")
@auth
def logout():
    session.clear()
    return jsonify(ok=True)
@app.post("/api/password")
@auth
def change_password():
    d=request.get_json(silent=True) or {}
    old=str(d.get("old",""))
    new=str(d.get("new",""))
    if not check_password_hash(get("admin_hash",""),old):
        return err("wrong_password")
    if len(new)<10 or len(new)>128:
        return err("short_password")
    h=generate_password_hash(new)
    put("admin_hash",h)
    session["ph"]=h[:16]
    return jsonify(ok=True)
def cpu_pct():
    with open("/proc/stat") as f:
        v=[int(x) for x in f.readline().split()[1:]]
    idle=v[3]+v[4]
    tot=sum(v)
    last=CPU.get("l")
    CPU["l"]=(idle,tot)
    if not last or tot==last[1]:
        return 0.0
    return round(max(0.0,min(100.0,100*(1-(idle-last[0])/(tot-last[1])))),1)
def net_totals():
    rx=tx=0
    with open("/proc/net/dev") as f:
        for l in list(f)[2:]:
            n,_,v=l.partition(":")
            if n.strip()=="lo":
                continue
            p=v.split()
            if len(p)>=9:
                rx+=int(p[0])
                tx+=int(p[8])
    return rx,tx
@app.get("/api/stats")
@auth
def stats():
    mem={}
    with open("/proc/meminfo") as f:
        for l in f:
            k,v=l.split(":",1)
            mem[k]=int(v.split()[0])*1024
    du=shutil.disk_usage("/")
    sv={s:sh(["systemctl","is-active","--quiet",s]).returncode==0 for s in ("xray","nginx","vpnbridge")}
    sv["ssh"]=any(sh(["systemctl","is-active","--quiet",s]).returncode==0 for s in ("ssh","ssh.socket"))
    sv["panel"]=True
    with open("/proc/uptime") as f:
        up=float(f.read().split()[0])
    rx,tx=net_totals()
    return jsonify(version=VERSION,cpu=cpu_pct(),cores=os.cpu_count() or 1,load=list(os.getloadavg()),mem_total=mem.get("MemTotal",0),mem_used=mem.get("MemTotal",0)-mem.get("MemAvailable",0),disk_total=du.total,disk_used=du.used,uptime=up,net_rx=rx,net_tx=tx,ts=time.time(),services=sv,domain=get("domain",""))
@app.get("/api/accounts")
@auth
def lst():
    c=db()
    rows=[]
    for r in c.execute("SELECT * FROM accounts ORDER BY created DESC"):
        o={k:r[k] for k in ("name","proto","status","manual","created","expires","quota","up","down","note","tls","maxdev")}
        o["online"]=ONLINE.get(r["name"],0)
        rows.append(o)
    c.close()
    return jsonify(rows)
def vmess_link(n,s,dom,tls):
    o={"v":"2","ps":n+("-TLS" if tls else "-80"),"add":dom,"port":"443" if tls else "80","id":s,"aid":"0","scy":"auto","net":"ws","type":"none","host":dom,"path":"/vmess","tls":"tls" if tls else "","sni":dom if tls else ""}
    return "vmess://"+base64.b64encode(json.dumps(o,separators=(",",":")).encode()).decode()
@app.get("/api/accounts/<name>/info")
@auth
def info(name):
    c=db()
    r=c.execute("SELECT * FROM accounts WHERE name=?",(name,)).fetchone()
    c.close()
    if not r:
        return err("not_found",404)
    dom=get("domain","")
    s=r["secret"]
    n=r["name"]
    h=quote(n,safe="")
    items=[]
    p=r["proto"]
    if p=="ssh":
        items=[{"k":"ssh_tls","value":"%s:443@%s:%s"%(dom,n,s),"rows":2},{"k":"ssh_plain","value":"%s:80@%s:%s"%(dom,n,s),"rows":2},{"k":"payload","value":"GET / HTTP/1.1[crlf]Host: %s[crlf]Upgrade: websocket[crlf][crlf]"%dom,"rows":3},{"k":"user","value":n,"rows":1},{"k":"pass","value":s,"rows":1}]
    else:
        modes=MODES if r["tls"]=="both" else (r["tls"],)
        for m in modes:
            tls=m=="tls"
            if p=="vmess":
                v=vmess_link(n,s,dom,tls)
            elif p=="vless":
                v="vless://%s@%s:%d?encryption=none&security=%s&%stype=ws&host=%s&path=%%2Fvless#%s"%(s,dom,443 if tls else 80,"tls" if tls else "none","sni=%s&fp=chrome&"%dom if tls else "",dom,h+("-TLS" if tls else "-80"))
            else:
                v="trojan://%s@%s:%d?security=%s&%stype=ws&host=%s&path=%%2Ftrojan#%s"%(quote(s,safe=""),dom,443 if tls else 80,"tls" if tls else "none","sni=%s&fp=chrome&"%dom if tls else "",dom,h+("-TLS" if tls else "-80"))
            items.append({"k":"link_tls" if tls else "link_plain","value":v,"rows":4})
        items.append({"k":"pass" if p=="trojan" else "uuid","value":s,"rows":1})
    return jsonify(items=items,online=ONLINE.get(n,0),maxdev=r["maxdev"],status=r["status"],up=r["up"],down=r["down"],quota=r["quota"],expires=r["expires"],proto=p,tls=r["tls"])
def parse_common(d,creating):
    try:
        out={}
        if creating or d.get("days") not in (None,""):
            days=int(d.get("days") or 0)
            if not 0<=days<=3650:
                return None
            out["days"]=days
        if creating or d.get("quota_gb") not in (None,""):
            q=float(d.get("quota_gb") or 0)
            if not 0<=q<=100000:
                return None
            out["quota"]=int(q*GB)
        if creating or d.get("maxdev") not in (None,""):
            m=int(d.get("maxdev") or 0)
            if not 0<=m<=100:
                return None
            out["maxdev"]=m
        return out
    except (TypeError,ValueError):
        return None
@app.post("/api/accounts")
@auth
def create():
    d=request.get_json(silent=True) or {}
    proto=d.get("proto")
    name=str(d.get("name","")).strip().lower()
    if proto not in PROTOS:
        return err("bad_proto")
    if not NAME_RE.match(name):
        return err("bad_name")
    pc=parse_common(d,True)
    if pc is None:
        return err("bad_values")
    tls=d.get("tls","tls") if proto!="ssh" else "both"
    if tls not in ("tls","plain","both"):
        return err("bad_values")
    sec=str(d.get("secret") or "").strip()
    if proto in ("vless","vmess"):
        sec=sec.lower() or str(uuid.uuid4())
        if not UUID_RE.match(sec):
            return err("bad_uuid")
    else:
        sec=sec or gen_pass()
        if not SECRET_RE.match(sec):
            return err("bad_secret")
    note=str(d.get("note") or "")[:100]
    with LOCK:
        c=db()
        try:
            if c.execute("SELECT 1 FROM accounts WHERE name=?",(name,)).fetchone():
                return err("name_taken")
            uid=None
            if proto=="ssh":
                if sysuser_exists(name):
                    return err("name_reserved")
                try:
                    uid=next_uid(c)
                    ssh_add(name,sec,uid)
                except RuntimeError as e:
                    return err("system",400,str(e))
            now=int(time.time())
            c.execute("INSERT INTO accounts(name,proto,secret,uid,created,expires,quota,note,status,tls,maxdev) VALUES(?,?,?,?,?,?,?,?,'active',?,?)",(name,proto,sec,uid,now,now+pc["days"]*86400 if pc["days"] else 0,pc["quota"],note,tls,pc["maxdev"]))
            c.commit()
            if proto=="ssh":
                collect(c)
                nft_apply(c)
            else:
                xray_sync(c)
        finally:
            c.close()
    return jsonify(ok=True,name=name)
@app.patch("/api/accounts/<name>")
@auth
def edit(name):
    d=request.get_json(silent=True) or {}
    with LOCK:
        c=db()
        try:
            r=c.execute("SELECT * FROM accounts WHERE name=?",(name,)).fetchone()
            if not r:
                return err("not_found",404)
            collect(c)
            sets={}
            sec=None
            if d.get("regen"):
                sec=str(uuid.uuid4()) if r["proto"] in ("vless","vmess") else gen_pass()
            elif d.get("secret"):
                sec=str(d["secret"]).strip()
                if r["proto"] in ("vless","vmess"):
                    sec=sec.lower()
                    if not UUID_RE.match(sec):
                        return err("bad_uuid")
                elif not SECRET_RE.match(sec):
                    return err("bad_secret")
            if sec:
                sets["secret"]=sec
            pc=parse_common(d,False)
            if pc is None:
                return err("bad_values")
            if "days" in pc:
                sets["expires"]=int(time.time())+pc["days"]*86400 if pc["days"] else 0
            if "quota" in pc:
                sets["quota"]=pc["quota"]
            if "maxdev" in pc:
                sets["maxdev"]=pc["maxdev"]
            if d.get("tls") and r["proto"]!="ssh":
                if d["tls"] not in ("tls","plain","both"):
                    return err("bad_values")
                sets["tls"]=d["tls"]
            if "note" in d:
                sets["note"]=str(d.get("note") or "")[:100]
            if "manual" in d:
                sets["manual"]=1 if d["manual"] else 0
            if d.get("reset"):
                sets["up"]=0
                sets["down"]=0
            if sets:
                c.execute("UPDATE accounts SET "+",".join(k+"=?" for k in sets)+" WHERE name=?",list(sets.values())+[name])
                c.commit()
            if sec and r["proto"]=="ssh":
                ssh_pass(name,sec)
            reconcile(c)
        finally:
            c.close()
    return jsonify(ok=True)
@app.delete("/api/accounts/<name>")
@auth
def delete(name):
    with LOCK:
        c=db()
        try:
            r=c.execute("SELECT * FROM accounts WHERE name=?",(name,)).fetchone()
            if not r:
                return err("not_found",404)
            collect(c)
            if r["proto"]=="ssh":
                ssh_del(name)
            c.execute("DELETE FROM accounts WHERE name=?",(name,))
            c.commit()
            SEEN.pop(name,None)
            if r["proto"]=="ssh":
                nft_apply(c)
            else:
                xray_sync(c)
        finally:
            c.close()
    return jsonify(ok=True)
def main():
    cmd=sys.argv[1] if len(sys.argv)>1 else "serve"
    init_db()
    if cmd=="setup":
        put("admin_user",os.environ["VPN_ADMIN_USER"])
        put("admin_hash",generate_password_hash(os.environ["VPN_ADMIN_PASS"]))
        put("domain",os.environ["VPN_DOMAIN"])
        c=db()
        write_xray_conf(c)
        c.close()
        return
    if cmd=="setadmin":
        if os.environ.get("VPN_ADMIN_USER"):
            put("admin_user",os.environ["VPN_ADMIN_USER"])
        if os.environ.get("VPN_ADMIN_PASS"):
            put("admin_hash",generate_password_hash(os.environ["VPN_ADMIN_PASS"]))
        return
    app.config.update(SECRET_KEY=get("secret_key"),SESSION_COOKIE_NAME="vpnsid",SESSION_COOKIE_SECURE=True,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Strict",PERMANENT_SESSION_LIFETIME=timedelta(hours=12),MAX_CONTENT_LENGTH=65536)
    with LOCK:
        c=db()
        nft_apply(c)
        reconcile(c)
        c.close()
    threading.Thread(target=worker,daemon=True).start()
    from waitress import serve
    serve(app,host="127.0.0.1",port=8000,threads=8)
if __name__=="__main__":
    main()
