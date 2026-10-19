import os,sys,re,json,time,uuid,hmac,secrets,shutil,sqlite3,functools,threading,traceback,subprocess
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
PROTOS=("ssh","vless","trojan")
NAME_RE=re.compile(r"^[a-z][a-z0-9_]{2,19}$")
SECRET_RE=re.compile(r"^[A-Za-z0-9@#%_.+=-]{6,64}$")
UUID_RE=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ALNUM="abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LOCK=threading.RLock()
FAILS={}
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
    for u in uids:
        L.append('  ct mark %d counter name "cd%d"'%(u,u))
    L.append(" }")
    L.append("}")
    r=sh(["nft","-f","-"],inp="\n".join(L)+"\n")
    if r.returncode:
        print("nft error:",r.stderr,file=sys.stderr)
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
def xray_conf(c):
    sk=get("secret_key")
    vl=[];tr=[]
    for r in c.execute("SELECT * FROM accounts WHERE status='active' AND proto IN ('vless','trojan') ORDER BY name"):
        if r["proto"]=="vless":
            vl.append({"id":r["secret"],"email":r["name"],"level":0})
        else:
            tr.append({"password":r["secret"],"email":r["name"],"level":0})
    if not vl:
        vl.append({"id":str(uuid.uuid5(uuid.NAMESPACE_URL,sk)),"email":"placeholder-v","level":0})
    if not tr:
        tr.append({"password":uuid.uuid5(uuid.NAMESPACE_URL,sk+"t").hex,"email":"placeholder-t","level":0})
    return {
        "log":{"loglevel":"warning"},
        "stats":{},
        "api":{"tag":"api","services":["StatsService"]},
        "policy":{"levels":{"0":{"statsUserUplink":True,"statsUserDownlink":True}}},
        "inbounds":[
            {"tag":"api","listen":"127.0.0.1","port":10085,"protocol":"dokodemo-door","settings":{"address":"127.0.0.1"}},
            {"tag":"vless-in","listen":"127.0.0.1","port":10001,"protocol":"vless","settings":{"clients":vl,"decryption":"none"},"streamSettings":{"network":"ws","wsSettings":{"path":"/vless"}}},
            {"tag":"trojan-in","listen":"127.0.0.1","port":10002,"protocol":"trojan","settings":{"clients":tr},"streamSettings":{"network":"ws","wsSettings":{"path":"/trojan"}}}],
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
def worker():
    while True:
        time.sleep(30)
        try:
            with LOCK:
                c=db()
                try:
                    collect(c)
                    reconcile(c)
                finally:
                    c.close()
        except Exception:
            traceback.print_exc()
def err(m,code=400):
    return jsonify(error=m),code
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
    r.headers["Cache-Control"]="no-store"
    return r
@app.route("/login",methods=["GET","POST"])
def login():
    if not session.get("csrf"):
        session["csrf"]=secrets.token_hex(16)
    if request.method=="GET":
        return render_template("login.html",csrf=session["csrf"],err=None)
    ip=client_ip()
    if blocked(ip):
        return render_template("login.html",csrf=session["csrf"],err="محاولات كثيرة، حاول لاحقاً"),429
    if not hmac.compare_digest(request.form.get("csrf",""),session["csrf"]):
        return render_template("login.html",csrf=session["csrf"],err="انتهت الجلسة، أعد المحاولة"),403
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
    return render_template("login.html",csrf=session["csrf"],err="بيانات الدخول غير صحيحة"),401
@app.get("/")
def index():
    if not valid_session():
        return redirect("/login")
    return render_template("index.html",csrf=session["csrf"],domain=get("domain",""))
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
        return err("كلمة المرور الحالية غير صحيحة")
    if len(new)<10 or len(new)>128:
        return err("كلمة المرور الجديدة: 10 أحرف على الأقل")
    h=generate_password_hash(new)
    put("admin_hash",h)
    session["ph"]=h[:16]
    return jsonify(ok=True)
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
    with open("/proc/uptime") as f:
        up=float(f.read().split()[0])
    return jsonify(load=list(os.getloadavg()),mem_total=mem.get("MemTotal",0),mem_used=mem.get("MemTotal",0)-mem.get("MemAvailable",0),disk_total=du.total,disk_used=du.used,uptime=up,services=sv)
@app.get("/api/accounts")
@auth
def lst():
    c=db()
    rows=[{k:r[k] for k in ("name","proto","status","manual","created","expires","quota","up","down","note")} for r in c.execute("SELECT * FROM accounts ORDER BY created DESC")]
    c.close()
    return jsonify(rows)
@app.get("/api/accounts/<name>/info")
@auth
def info(name):
    c=db()
    r=c.execute("SELECT * FROM accounts WHERE name=?",(name,)).fetchone()
    c.close()
    if not r:
        return err("غير موجود",404)
    dom=get("domain","")
    s=r["secret"]
    n=r["name"]
    h=quote(n,safe="")
    if r["proto"]=="vless":
        items=[{"label":"رابط VLESS","value":"vless://%s@%s:443?encryption=none&security=tls&sni=%s&fp=chrome&type=ws&host=%s&path=%%2Fvless#%s"%(s,dom,dom,dom,h),"rows":4},{"label":"UUID","value":s,"rows":1}]
    elif r["proto"]=="trojan":
        items=[{"label":"رابط Trojan","value":"trojan://%s@%s:443?security=tls&sni=%s&fp=chrome&type=ws&host=%s&path=%%2Ftrojan#%s"%(quote(s,safe=""),dom,dom,dom,h),"rows":4},{"label":"كلمة المرور","value":s,"rows":1}]
    else:
        items=[{"label":"SSH WS + TLS (443)","value":"%s:443@%s:%s"%(dom,n,s),"rows":2},{"label":"SSH WS بدون TLS (80)","value":"%s:80@%s:%s"%(dom,n,s),"rows":2},{"label":"Payload","value":"GET / HTTP/1.1[crlf]Host: %s[crlf]Upgrade: websocket[crlf][crlf]"%dom,"rows":3},{"label":"المستخدم","value":n,"rows":1},{"label":"كلمة المرور","value":s,"rows":1}]
    return jsonify(items=items)
@app.post("/api/accounts")
@auth
def create():
    d=request.get_json(silent=True) or {}
    proto=d.get("proto")
    name=str(d.get("name","")).strip().lower()
    if proto not in PROTOS:
        return err("بروتوكول غير صالح")
    if not NAME_RE.match(name):
        return err("الاسم: أحرف إنجليزية صغيرة وأرقام و _ بطول 3-20 ويبدأ بحرف")
    try:
        days=int(d.get("days") or 0)
        quota=float(d.get("quota_gb") or 0)
    except (TypeError,ValueError):
        return err("قيم غير صالحة")
    if not (0<=days<=3650 and 0<=quota<=100000):
        return err("قيم غير صالحة")
    sec=str(d.get("secret") or "").strip()
    if proto=="vless":
        sec=sec.lower() or str(uuid.uuid4())
        if not UUID_RE.match(sec):
            return err("UUID غير صالح")
    else:
        sec=sec or gen_pass()
        if not SECRET_RE.match(sec):
            return err("كلمة المرور: 6-64 حرفاً من A-Za-z0-9@#%_.+=-")
    note=str(d.get("note") or "")[:100]
    with LOCK:
        c=db()
        try:
            if c.execute("SELECT 1 FROM accounts WHERE name=?",(name,)).fetchone():
                return err("الاسم مستخدم")
            uid=None
            if proto=="ssh":
                if sysuser_exists(name):
                    return err("الاسم محجوز في النظام")
                try:
                    uid=next_uid(c)
                    ssh_add(name,sec,uid)
                except RuntimeError as e:
                    return err(str(e))
            now=int(time.time())
            c.execute("INSERT INTO accounts(name,proto,secret,uid,created,expires,quota,note,status) VALUES(?,?,?,?,?,?,?,?,'active')",(name,proto,sec,uid,now,now+days*86400 if days else 0,int(quota*GB),note))
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
                return err("غير موجود",404)
            collect(c)
            sets={}
            sec=None
            if d.get("regen"):
                sec=str(uuid.uuid4()) if r["proto"]=="vless" else gen_pass()
            elif d.get("secret"):
                sec=str(d["secret"]).strip()
                if r["proto"]=="vless":
                    sec=sec.lower()
                    if not UUID_RE.match(sec):
                        return err("UUID غير صالح")
                elif not SECRET_RE.match(sec):
                    return err("كلمة المرور: 6-64 حرفاً من A-Za-z0-9@#%_.+=-")
            if sec:
                sets["secret"]=sec
            try:
                if d.get("days") not in (None,""):
                    days=int(d["days"])
                    if not 0<=days<=3650:
                        return err("قيم غير صالحة")
                    sets["expires"]=int(time.time())+days*86400 if days else 0
                if d.get("quota_gb") not in (None,""):
                    q=float(d["quota_gb"])
                    if not 0<=q<=100000:
                        return err("قيم غير صالحة")
                    sets["quota"]=int(q*GB)
            except (TypeError,ValueError):
                return err("قيم غير صالحة")
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
                return err("غير موجود",404)
            collect(c)
            if r["proto"]=="ssh":
                ssh_del(name)
            c.execute("DELETE FROM accounts WHERE name=?",(name,))
            c.commit()
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
