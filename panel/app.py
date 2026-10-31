import os,sys,re,json,time,uuid,hmac,base64,socket,calendar,secrets,shutil,sqlite3,tempfile,functools,threading,traceback,subprocess
from datetime import timedelta,datetime,timezone
from zoneinfo import ZoneInfo,available_timezones
from shlex import quote as shq
from urllib.parse import quote
from urllib.request import urlopen,Request
from flask import Flask,request,session,jsonify,render_template,redirect,Response
from werkzeug.security import generate_password_hash,check_password_hash
import sshconn
BASE=os.path.dirname(os.path.abspath(__file__))
APPDIR=os.path.dirname(BASE)
DATA="/var/lib/vpnpanel"
DBP=DATA+"/panel.db"
JOBF=DATA+"/job.json"
RCF=DATA+"/job.rc"
LOGF="/var/log/isile-install.log"
BANNER_TXT="/etc/vpnpanel/banner.txt"
BANNER_CONF="/etc/ssh/sshd_config.d/99-zvpnpanel-banner.conf"
BANNER_MAX=2000
LOGS={"install":("file",LOGF),"panel":("unit",["vpnpanel"]),"xray":("unit",["xray"]),"ssh":("unit",["ssh","sshd"]),"bridge":("unit",["vpnbridge"]),"mux":("unit",["vpnmux"]),"stunnel":("unit",["vpnstunnel"]),"nginx":("unit",["nginx"]),"nginx_err":("file","/var/log/nginx/error.log"),"nginx_acc":("file","/var/log/nginx/access.log"),"udpcustom":("unit",["udp-custom"])}
XCONF="/usr/local/etc/xray/config.json"
XBIN="/usr/local/bin/xray"
XAPI="127.0.0.1:10085"
UID0=20000
UID1=60000
GB=1073741824
V2=("vless","vmess","trojan")
PROTOS=("ssh",)+V2
MODES=("tls","plain")
TRANSPORTS=("ws","ssl","udp","grpc")
V2NETS=("ws","grpc")
UNITDIR="/etc/systemd/system"
UDPC_DIR="/usr/local/lib/isile/udp-custom"
UDPC_BIN=UDPC_DIR+"/udp-custom"
UDPC_CONF=UDPC_DIR+"/config.json"
UDPC_INFO="/etc/vpnpanel/udp-custom.info"
UDPC_PORT=36712
COMBOS=(("sshws","tls","wsbridge"),("sshws","plain","wsbridge"),("sshssl","tls","sshssl"),("sshssl","plain","sshssl"),("sshudp","udp","udpcustom"),("vless","tls","xray"),("vless","plain","xray"),("vmess","tls","xray"),("vmess","plain","xray"),("trojan","tls","xray"),("trojan","plain","xray"))
COMP_UNIT={"wsbridge":"vpnbridge","sshssl":"vpnmux","udpcustom":"udp-custom","xray":"xray"}
REMOVABLE=("wsbridge","udpcustom","xray")
PORTS={("vless","tls"):10001,("trojan","tls"):10002,("vmess","tls"):10003,("vless","plain"):10011,("trojan","plain"):10012,("vmess","plain"):10013}
GPORTS={("vless","tls"):10101,("trojan","tls"):10102,("vmess","tls"):10103,("vless","plain"):10111,("trojan","plain"):10112,("vmess","plain"):10113}
NAME_RE=re.compile(r"^[a-z][a-z0-9_]{2,19}$")
SECRET_RE=re.compile(r"^[A-Za-z0-9@#%_.+=-]{6,64}$")
UUID_RE=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DOMAIN_RE=re.compile(r"^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")
EMAIL_RE=re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ALNUM="abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LOCK=threading.RLock()
FAILS={}
CPU={}
ACTIVE={}
ACTIVE_MIN=1024
ACTIVE_TTL=25
RUN=None
SPEED={}
SP_B={}
SP_T=time.time()
SPEED_TTL=30
RESERVED=("login","api","static")
CONN={}
SSH_OVER={}
CONN_MAX=1000
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
CREATE TABLE IF NOT EXISTS accounts(name TEXT PRIMARY KEY,proto TEXT NOT NULL,secret TEXT NOT NULL,uid INTEGER,created INTEGER NOT NULL,expires INTEGER NOT NULL DEFAULT 0,quota INTEGER NOT NULL DEFAULT 0,up INTEGER NOT NULL DEFAULT 0,down INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'active',manual INTEGER NOT NULL DEFAULT 0,note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS daily(d TEXT PRIMARY KEY,rx INTEGER NOT NULL DEFAULT 0,tx INTEGER NOT NULL DEFAULT 0);""")
    cols={r["name"] for r in c.execute("PRAGMA table_info(accounts)")}
    if "tls" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN tls TEXT NOT NULL DEFAULT 'tls'")
    if "transport" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN transport TEXT NOT NULL DEFAULT 'ws'")
    if "conn_limit" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN conn_limit INTEGER NOT NULL DEFAULT 0")
    c.execute("DROP TABLE IF EXISTS v2block")
    c.execute("UPDATE accounts SET conn_limit=0 WHERE proto!='ssh' AND conn_limit!=0")
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
def gets(*keys):
    c=db()
    r={x["k"]:x["v"] for x in c.execute("SELECT k,v FROM settings WHERE k IN (%s)"%",".join("?"*len(keys)),keys)}
    c.close()
    return r
def put(k,v):
    puts({k:v})
def puts(d):
    c=db()
    c.executemany("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",[(k,str(v)) for k,v in d.items()])
    c.commit()
    c.close()
def host():
    return get("domain","") or get("server_ip","")
def tls_on():
    return bool(get("domain",""))
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
    if comp_installed("udpcustom"):
        L.append("  "+rng+" ip daddr 127.0.0.1 tcp dport 7300 accept")
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
def unit_exists(n):
    return os.path.exists("%s/%s.service"%(UNITDIR,n))
def comp_installed(c):
    if c=="xray":
        return unit_exists("xray") and os.path.exists(XBIN)
    if c=="udpcustom":
        return unit_exists("udp-custom") and os.path.exists(UDPC_BIN)
    if c=="wsbridge":
        return unit_exists("vpnbridge")
    return True
def combos_off():
    return {x for x in get("combos_off","").split(",") if x}
def comp_combos(c):
    return [p+":"+m for p,m,k in COMBOS if k==c]
def comp_enabled(c,off=None):
    off=combos_off() if off is None else off
    return any(k not in off for k in comp_combos(c))
def comp_on(c):
    return comp_installed(c) and comp_enabled(c)
def svc_active(u):
    return sh(["systemctl","is-active","--quiet",u]).returncode==0
def block_state(c,off=None):
    if not comp_installed(c):
        return "bad"
    if not comp_enabled(c,off):
        return "off"
    return "ok" if svc_active(COMP_UNIT[c]) else "warn"
def udp_port():
    try:
        with open(UDPC_CONF) as f:
            m=re.search(r":(\d{1,5})$",str(json.load(f).get("listen","")))
        if m and 0<int(m.group(1))<65536:
            return int(m.group(1))
    except (OSError,ValueError,AttributeError):
        pass
    return UDPC_PORT
def udpc_info():
    o={}
    try:
        with open(UDPC_INFO) as f:
            for l in f:
                k,_,v=l.partition("=")
                if k in ("url","sha256"):
                    o[k]=v.strip()
    except OSError:
        return None
    return o or None
def combo_info(off=None):
    off=combos_off() if off is None else off
    t=tls_on()
    inst={c:comp_installed(c) for c in COMP_UNIT}
    out=[]
    for p,m,c in COMBOS:
        k=p+":"+m
        why=""
        if not inst[c]:
            why="not_installed"
        elif k in off:
            why="disabled"
        elif m=="tls" and not t:
            why="no_tls"
        out.append({"k":k,"p":p,"m":m,"c":c,"enabled":k not in off,"installed":inst[c],"avail":not why,"why":why})
    return out
def acct_keys(proto,transport,tls):
    if proto=="ssh":
        if transport=="udp":
            return ["sshudp:udp"]
        base="sshws" if transport=="ws" else "sshssl"
    else:
        base=proto
    return [base+":"+m for m in (MODES if tls=="both" else (tls,))]
def keys_denied(keys):
    off=combos_off()
    cm={p+":"+m:c for p,m,c in COMBOS}
    for k in keys:
        c=cm.get(k)
        if not c or not comp_installed(c) or k in off:
            return k
    return ""
def expected_units():
    u=["vpnpanel","nginx","vpnmux"]
    if comp_on("wsbridge"):
        u.append("vpnbridge")
    if comp_on("xray"):
        u.append("xray")
    if comp_on("udpcustom"):
        u.append("udp-custom")
    try:
        if os.path.getsize("/etc/vpnpanel/stunnel.conf")>0:
            u.append("vpnstunnel")
    except OSError:
        pass
    return u
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
# ---- UDP Custom: per-account sessions (from its log) and usage (nft counters per client ip:port) ----
import ipaddress
UDPS={}
UDPEND={}
UDPS_LOCK=threading.Lock()
UDP_MAIN=[None]
UDP_INIT=[False]
UDP_LAST={}
RE_USRC=re.compile(r"\[src:([^\]]+)\]")
RE_UUSER=re.compile(r"\[user:([^\]]+)\]")
RE_UPID=re.compile(r"udp-custom\[(\d+)\]")
RE_UNAME=re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
def udp_line(l):
    s=RE_USRC.search(l)
    if not s:
        return
    src=s.group(1)
    p=RE_UPID.search(l)
    pid=p.group(1) if p else ""
    with UDPS_LOCK:
        if "Client connected" in l:
            u=RE_UUSER.search(l)
            if u and RE_UNAME.match(u.group(1)):
                UDPS[src]=(u.group(1),pid)
        elif "Client disconnected" in l:
            v=UDPS.pop(src,None)
            if v:
                UDPEND[src]=v[0]
def udp_sessions():
    with UDPS_LOCK:
        m=UDP_MAIN[0]
        return [(s,v[0]) for s,v in UDPS.items() if m is None or not v[1] or v[1]==m]
def udp_follow():
    while True:
        try:
            if comp_installed("udpcustom"):
                p=subprocess.Popen(["journalctl","-u","udp-custom","-n","3000","-f","-o","short-iso","--no-pager"],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,errors="replace")
                for l in p.stdout:
                    udp_line(l)
                p.wait()
            else:
                time.sleep(30)
        except Exception:
            traceback.print_exc()
        time.sleep(5)
def udp_split(src):
    h,_,p=src.rpartition(":")
    h=h.strip("[]")
    ip=ipaddress.ip_address(h)
    return ("ip6" if ip.version==6 else "ip"),str(ip),int(p)
def harvest_udp():
    out={}
    if not comp_installed("udpcustom"):
        return out
    try:
        m=sh(["systemctl","show","-p","MainPID","--value","udp-custom"]).stdout.strip()
        UDP_MAIN[0]=m if m and m!="0" else None
    except Exception:
        pass
    lp=udp_port()
    if not UDP_INIT[0]:
        r=sh(["nft","-f","-"],inp="table inet vpnudp\ndelete table inet vpnudp\ntable inet vpnudp {\n chain in { type filter hook input priority -150; policy accept; }\n chain out { type filter hook output priority -150; policy accept; }\n}\n")
        if r.returncode:
            return out
        UDP_INIT[0]=True
        UDP_LAST.clear()
    cur=dict(udp_sessions())
    with UDPS_LOCK:
        UDPEND.clear()
    r=sh(["nft","-j","-a","list","table","inet","vpnudp"])
    if r.returncode:
        UDP_INIT[0]=False
        return out
    have={}
    try:
        items=json.loads(r.stdout or "{}").get("nftables",[])
    except ValueError:
        items=[]
    for it in items:
        ru=it.get("rule")
        if not ru:
            continue
        cm=(ru.get("comment") or "").split("|")
        if len(cm)!=4 or cm[0]!="udp":
            continue
        b=0
        for e in ru.get("expr",[]):
            if "counter" in e:
                b=int(e["counter"].get("bytes",0))
        have[(cm[2],cm[3])]=(ru.get("handle"),ru.get("chain"),b,cm[1])
    cmds=[]
    for key,(h,ch,b,u) in have.items():
        last=UDP_LAST.get(key,0)
        d=b-last if b>=last else b
        UDP_LAST[key]=b
        if d>0:
            o=out.setdefault(u,[0,0])
            o[0 if key[1]=="i" else 1]+=d
        if key[0] not in cur:
            cmds.append("delete rule inet vpnudp %s handle %s"%(ch,h))
            UDP_LAST.pop(key,None)
    for src,u in cur.items():
        if (src,"i") in have:
            continue
        try:
            fam,ip,pt=udp_split(src)
        except ValueError:
            continue
        cmds.append('add rule inet vpnudp in %s saddr %s udp sport %d udp dport %d counter comment "udp|%s|%s|i"'%(fam,ip,pt,lp,u,src))
        cmds.append('add rule inet vpnudp out %s daddr %s udp dport %d udp sport %d counter comment "udp|%s|%s|o"'%(fam,ip,pt,lp,u,src))
    if cmds:
        r=sh(["nft","-f","-"],inp="\n".join(cmds)+"\n")
        if r.returncode:
            print("nft udp error:",r.stderr,file=sys.stderr)
    return {k:(v[0],v[1]) for k,v in out.items()}
def collect(c):
    global SPEED,SP_T
    with LOCK:
        x=harvest_xray()
        for n,(u,d) in harvest_udp().items():
            o=x.get(n,(0,0))
            x[n]=(o[0]+u,o[1]+d)
        s=harvest_nft()
        um={r["uid"]:r["name"] for r in c.execute("SELECT name,uid FROM accounts WHERE uid IS NOT NULL")}
        now=time.time()
        got={}
        for n,(u,d) in x.items():
            c.execute("UPDATE accounts SET up=up+?,down=down+? WHERE name=?",(u,d,n))
            g=got.setdefault(n,[0,0])
            g[0]+=u
            g[1]+=d
            if u+d>=ACTIVE_MIN:
                ACTIVE[n]=now
        for uid,(u,d) in s.items():
            n=um.get(uid)
            if n:
                c.execute("UPDATE accounts SET up=up+?,down=down+? WHERE name=?",(u,d,n))
                g=got.setdefault(n,[0,0])
                g[0]+=u
                g[1]+=d
                if u+d>=ACTIVE_MIN:
                    ACTIVE[n]=now
        c.commit()
        for n,(u,d) in got.items():
            b=SP_B.setdefault(n,[0,0])
            b[0]+=u
            b[1]+=d
        if now-SP_T>=8:
            dt=now-SP_T
            SPEED={n:(b[0]/dt,b[1]/dt,now) for n,b in SP_B.items()}
            SP_B.clear()
            SP_T=now
def speed_of(n):
    sp=SPEED.get(n)
    if not sp or time.time()-sp[2]>SPEED_TTL:
        return 0,0
    return int(sp[0]),int(sp[1])
def page_url(n):
    return "%s://%s:2080/%s"%("https" if tls_on() else "http",host(),n)
def public_on():
    return get("public_page","0")=="1"
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
    cl={(p,m,n):[] for p in V2 for m in MODES for n in V2NETS}
    for r in c.execute("SELECT * FROM accounts WHERE status='active' AND proto IN ('vless','vmess','trojan') ORDER BY name"):
        net=r["transport"] if r["transport"] in V2NETS else "ws"
        for m in (MODES if r["tls"]=="both" else (r["tls"],)):
            if (r["proto"],m,net) in cl:
                cl[(r["proto"],m,net)].append(client_of(r))
    inb=[{"tag":"api","listen":"127.0.0.1","port":10085,"protocol":"dokodemo-door","settings":{"address":"127.0.0.1"}}]
    for p in V2:
        for m in MODES:
            for net in V2NETS:
                st={"clients":cl[(p,m,net)] or [placeholder(sk,p,m+"-"+net if net!="ws" else m)]}
                if p=="vless":
                    st["decryption"]="none"
                if net=="ws":
                    ss={"network":"ws","wsSettings":{"path":"/"+p}}
                    tag,port=p+"-"+m,PORTS[(p,m)]
                else:
                    ss={"network":"grpc","grpcSettings":{"serviceName":p+"-grpc"}}
                    tag,port=p+"-"+m+"-grpc",GPORTS[(p,m)]
                inb.append({"tag":tag,"listen":"127.0.0.1","port":port,"protocol":p,"settings":st,"streamSettings":ss})
    return {
        "log":{"access":"none","loglevel":"warning"},
        "stats":{},
        "api":{"tag":"api","services":["StatsService","HandlerService","RoutingService"]},
        "policy":{"levels":{"0":{"statsUserUplink":True,"statsUserDownlink":True}}},
        "inbounds":inb,
        "outbounds":[{"tag":"direct","protocol":"freedom"},{"tag":"block","protocol":"blackhole"}],
        "routing":{"domainStrategy":"IPIfNonMatch","rules":[
            {"type":"field","inboundTag":["api"],"outboundTag":"api"},
            {"type":"field","ip":["geoip:private"],"outboundTag":"block"}]}}
def read_cfg():
    try:
        with open(XCONF) as f:
            return json.load(f)
    except (OSError,ValueError):
        return None
def write_cfg_text(txt):
    try:
        with open(XCONF) as f:
            if f.read()==txt:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(XCONF),exist_ok=True)
    tmp=XCONF+".tmp"
    with open(tmp,"w") as f:
        f.write(txt)
    os.chmod(tmp,0o640)
    shutil.chown(tmp,"root","xray")
    os.replace(tmp,XCONF)
    return True
def write_xray_conf(c):
    return write_cfg_text(json.dumps(xray_conf(c),indent=1,sort_keys=True))
def cfg_clients(cfg):
    out={}
    for ib in cfg.get("inbounds",[]):
        cl=ib.get("settings",{}).get("clients")
        if cl is not None:
            out[ib["tag"]]={x["email"]:x for x in cl if not x["email"].startswith("placeholder-")}
    return out
def cfg_struct(cfg):
    o=json.loads(json.dumps(cfg))
    for ib in o.get("inbounds",[]):
        if "clients" in ib.get("settings",{}):
            ib["settings"]["clients"]=[]
    return o
def restart_xray(c):
    if not comp_on("xray"):
        return
    if xray_running():
        collect(c)
    sh(["systemctl","restart","xray"])
def hot(rm,add):
    return False
    for tag,emails in rm.items():
        r=sh([XBIN,"api","rmu","-s",XAPI,"-tag="+tag]+emails)
        if r.returncode:
            print("xray rmu failed:",r.stdout,r.stderr,file=sys.stderr)
            return False
    for tag,cl in add.items():
        p=tag.split("-")[0]
        st={"clients":cl}
        if p=="vless":
            st["decryption"]="none"
        fd,path=tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd,"w") as f:
            json.dump({"inbounds":[{"tag":tag,"protocol":p,"settings":st}]},f)
        r=sh([XBIN,"api","adu","-s",XAPI,path])
        os.unlink(path)
        if r.returncode:
            print("xray adu failed:",r.stdout,r.stderr,file=sys.stderr)
            return False
    return True
def xray_sync(c):
    global RUN
    with LOCK:
        if not comp_on("xray"):
            return
        cfg=xray_conf(c)
        old=read_cfg()
        run=xray_running()
        want=cfg_clients(cfg)
        if run and RUN is None and old is not None:
            RUN=cfg_clients(old)
        write_cfg_text(json.dumps(cfg,indent=1,sort_keys=True))
        if not run or old is None or RUN is None or cfg_struct(old)!=cfg_struct(cfg):
            restart_xray(c)
            RUN=want
            return
        rm={}
        add={}
        for tag,w in want.items():
            cur=RUN.get(tag,{})
            for e,x in cur.items():
                if w.get(e)!=x:
                    rm.setdefault(tag,[]).append(e)
            for e,x in w.items():
                if cur.get(e)!=x:
                    add.setdefault(tag,[]).append(x)
        if not rm and not add:
            return
        if not hot(rm,add):
            restart_xray(c)
        RUN=want
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
def apply_components(c):
    with LOCK:
        off=combos_off()
        for comp in ("wsbridge","udpcustom"):
            if not comp_installed(comp):
                continue
            u=COMP_UNIT[comp]
            if comp_enabled(comp,off):
                if not svc_active(u):
                    sh(["systemctl","enable","--now",u])
            else:
                sh(["systemctl","disable","--now",u])
        if comp_installed("xray"):
            if comp_enabled("xray",off):
                sh(["systemctl","enable","xray"])
                xray_sync(c)
            else:
                if xray_running():
                    collect(c)
                sh(["systemctl","disable","--now","xray"])
DAYS={"last":""}
def pnow():
    try:
        z=ZoneInfo(panel_tz())
    except Exception:
        z=timezone.utc
    return datetime.now(z)
def daily_add(drx,dtx):
    if drx<=0 and dtx<=0:
        return
    n=pnow()
    d=n.strftime("%Y-%m-%d")
    c=db()
    try:
        c.execute("INSERT INTO daily(d,rx,tx) VALUES(?,?,?) ON CONFLICT(d) DO UPDATE SET rx=rx+excluded.rx,tx=tx+excluded.tx",(d,max(0,drx),max(0,dtx)))
        if DAYS["last"]!=d:
            c.execute("DELETE FROM daily WHERE d<?",((n-timedelta(days=400)).strftime("%Y-%m-%d"),))
            DAYS["last"]=d
        c.commit()
    finally:
        c.close()
def month_days():
    n=pnow()
    dim=calendar.monthrange(n.year,n.month)[1]
    rx=[0]*dim
    tx=[0]*dim
    c=db()
    try:
        for r in c.execute("SELECT d,rx,tx FROM daily WHERE d LIKE ?",("%04d-%02d-%%"%(n.year,n.month),)):
            i=int(r["d"][8:10])-1
            if 0<=i<dim:
                rx[i]=r["rx"]
                tx[i]=r["tx"]
    finally:
        c.close()
    return {"y":n.year,"m":n.month,"today":n.day,"dim":dim,"rx":rx,"tx":tx}
def track_traffic():
    rx,tx=net_totals()
    s=gets("month","m_rx","m_tx","m_off","last_rx","last_tx")
    cur=time.strftime("%Y-%m",time.gmtime())
    m_rx=int(s.get("m_rx",0))
    m_tx=int(s.get("m_tx",0))
    off=int(s.get("m_off",0))
    if s.get("month")!=cur:
        m_rx=m_tx=off=0
    drx=dtx=0
    if "last_rx" in s:
        lr=int(s["last_rx"])
        lt=int(s["last_tx"])
        drx=rx-lr if rx>=lr else rx
        dtx=tx-lt if tx>=lt else tx
        m_rx+=drx
        m_tx+=dtx
    puts({"month":cur,"m_rx":m_rx,"m_tx":m_tx,"m_off":off,"last_rx":rx,"last_tx":tx})
    try:
        daily_add(drx,dtx)
    except Exception:
        traceback.print_exc()
def conn_cycle():
    global CONN
    now=time.time()
    c=db()
    try:
        rows=c.execute("SELECT name,proto,uid,status,conn_limit FROM accounts").fetchall()
    finally:
        c.close()
    new={}
    um={r["uid"]:r for r in rows if r["proto"]=="ssh" and r["uid"] is not None}
    for uid,l in sshconn.scan(um).items():
        r=um[uid]
        n=r["name"]
        new[n]={"n":len(l),"ips":[]}
        L=r["conn_limit"]
        if L and len(l)>L and r["status"]=="active":
            SSH_OVER[n]=SSH_OVER.get(n,0)+1
            if SSH_OVER[n]>=2:
                for st,pid in l[L:]:
                    sshconn.kill(pid)
        else:
            SSH_OVER.pop(n,None)
    names={r["name"] for r in rows if r["proto"]=="ssh"}
    for src,u in udp_sessions():
        if u in names:
            e=new.setdefault(u,{"n":0,"ips":[]})
            e["n"]+=1
            e["ips"].append(src.rpartition(":")[0].strip("[]"))
    for n in [n for n in SSH_OVER if n not in new]:
        SSH_OVER.pop(n,None)
    CONN=new
def conn_worker():
    while True:
        time.sleep(1)
        try:
            conn_cycle()
        except Exception:
            traceback.print_exc()
def worker():
    n=0
    while True:
        time.sleep(10)
        n+=1
        try:
            track_traffic()
            with LOCK:
                c=db()
                try:
                    collect(c)
                    if n%3==0:
                        reconcile(c)
                finally:
                    c.close()
        except Exception:
            traceback.print_exc()
def err(code,status=400,detail=None):
    return jsonify(error=code,detail=detail),status
TZ_AREAS=("Africa","America","Antarctica","Arctic","Asia","Atlantic","Australia","Europe","Indian","Pacific")
TZ_LIST=[]
def tz_ok(n):
    try:
        ZoneInfo(n)
        return True
    except Exception:
        return False
def tz_list():
    if not TZ_LIST:
        try:
            TZ_LIST.extend(sorted(n for n in available_timezones() if n.split("/")[0] in TZ_AREAS and "/" in n))
        except Exception:
            pass
    return TZ_LIST
def server_tz():
    v=""
    try:
        with open("/etc/timezone") as f:
            v=f.read().strip()
    except OSError:
        pass
    if not v:
        try:
            p=os.path.realpath("/etc/localtime")
            if "/zoneinfo/" in p:
                v=p.split("/zoneinfo/",1)[1]
        except OSError:
            pass
    return v if v and tz_ok(v) else "UTC"
def tz_region():
    v=get("tz","")
    return v if v and tz_ok(v) else server_tz()
def panel_tz():
    return "UTC" if get("tz_utc","0")=="1" else tz_region()
def midnight_exp():
    try:
        z=ZoneInfo(panel_tz())
    except Exception:
        z=timezone.utc
    m=(datetime.now(z)+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
    return int(m.timestamp())
def valid_session():
    h=get("admin_hash","")
    return bool(session.get("u")) and session.get("ph")==h[:16] and session.get("exp",0)>time.time()
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
        session["exp"]=midnight_exp()
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
    return render_template("index.html",csrf=session["csrf"],domain=get("domain",""),version=VERSION,tz=panel_tz())
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
def cpu_cores():
    out=[]
    last=CPU.get("c",{})
    cur={}
    with open("/proc/stat") as f:
        for l in f:
            p=l.split()
            if not p or not p[0].startswith("cpu") or not p[0][3:].isdigit():
                continue
            v=[int(x) for x in p[1:]]
            idle=v[3]+v[4]
            tot=sum(v)
            cur[p[0]]=(idle,tot)
            o=last.get(p[0])
            out.append(0.0 if not o or tot==o[1] else round(max(0.0,min(100.0,100*(1-(idle-o[0])/(tot-o[1])))),1))
    CPU["c"]=cur
    return out
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
def month_info():
    s=gets("m_rx","m_tx","m_off","cap_gb","cap_basis")
    rx=int(s.get("m_rx",0))
    tx=int(s.get("m_tx",0))
    off=int(s.get("m_off",0))
    basis=s.get("cap_basis","total")
    used=max(0,(tx if basis=="out" else rx+tx)+off)
    return {"month_rx":rx,"month_tx":tx,"month_used":used,"cap_gb":float(s.get("cap_gb",0) or 0),"cap_basis":basis}
SSHP={"v":None}
def ssh_port():
    if SSHP["v"] is None:
        p=22
        try:
            m=re.search(r"^port (\d+)",sh(["sshd","-T"]).stdout,re.M)
            if m:
                p=int(m.group(1))
        except Exception:
            pass
        SSHP["v"]=p
    return SSHP["v"]
def listening_ports():
    out=set()
    for f in ("/proc/net/tcp","/proc/net/tcp6"):
        try:
            with open(f) as fh:
                for l in list(fh)[1:]:
                    p=l.split()
                    if len(p)<4 or p[3]!="0A":
                        continue
                    a,_,pt=p[1].rpartition(":")
                    if a in ("0100007F","00000000000000000000000001000000"):
                        continue
                    out.add(int(pt,16))
        except OSError:
            pass
    return out
def listening_udp():
    out=set()
    for f in ("/proc/net/udp","/proc/net/udp6"):
        try:
            with open(f) as fh:
                for l in list(fh)[1:]:
                    p=l.split()
                    if len(p)<4 or p[3]!="07":
                        continue
                    a,_,pt=p[1].rpartition(":")
                    if a in ("0100007F","00000000000000000000000001000000"):
                        continue
                    out.add(int(pt,16))
        except OSError:
            pass
    return out
def ports_info():
    ls=listening_ports()
    t=tls_on()
    rows=[("ssh",ssh_port(),True,ls),("http",80,True,ls),("https",443,t,ls),("panel",2080,True,ls)]
    if comp_installed("udpcustom"):
        rows.append(("udp",udp_port(),comp_on("udpcustom"),listening_udp()))
    return [{"k":k,"port":p,"enabled":en,"listening":en and p in l} for k,p,en,l in rows]
@app.get("/api/stats")
@auth
def stats():
    mem={}
    with open("/proc/meminfo") as f:
        for l in f:
            k,v=l.split(":",1)
            mem[k]=int(v.split()[0])*1024
    du=shutil.disk_usage("/")
    off=combos_off()
    run=lambda u:"ok" if svc_active(u) else "warn"
    sv={"xray":block_state("xray",off),"nginx":run("nginx"),"vpnbridge":block_state("wsbridge",off),"vpnmux":run("vpnmux")}
    if tls_on():
        sv["vpnstunnel"]=run("vpnstunnel")
    sv["ssh"]="ok" if any(svc_active(s) for s in ("ssh","ssh.socket")) else "warn"
    sv["panel"]="ok"
    sv["udp-custom"]=block_state("udpcustom",off)
    with open("/proc/uptime") as f:
        up=float(f.read().split()[0])
    rx,tx=net_totals()
    o=dict(version=VERSION,cpu=cpu_pct(),core_pct=cpu_cores(),cores=os.cpu_count() or 1,load=list(os.getloadavg()),mem_total=mem.get("MemTotal",0),mem_used=mem.get("MemTotal",0)-mem.get("MemAvailable",0),disk_total=du.total,disk_used=du.used,uptime=up,net_rx=rx,net_tx=tx,ts=time.time(),services=sv,domain=get("domain",""),host=host(),tls_on=tls_on())
    o.update(month_info())
    o["ports"]=ports_info()
    o["days"]=month_days()
    return jsonify(o)
def cert_info(dom):
    p="/etc/letsencrypt/live/%s/fullchain.pem"%dom
    if not dom or not os.path.exists(p):
        return None
    r=sh(["openssl","x509","-enddate","-noout","-in",p])
    m=re.search(r"notAfter=(.+)",r.stdout)
    if not m:
        return None
    try:
        e=datetime.strptime(m.group(1).strip(),"%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return {"expires":int(e.timestamp()),"days_left":int((e-datetime.now(timezone.utc)).total_seconds()//86400)}
def dns_of(dom):
    try:
        return sorted({a[4][0] for a in socket.getaddrinfo(dom,None,socket.AF_INET)})
    except (socket.gaierror,UnicodeError):
        return []
@app.get("/api/settings")
@auth
def settings_get():
    s=gets("cap_gb","cap_basis")
    o={"domain":get("domain",""),"server_ip":get("server_ip",""),"tls_on":tls_on(),"public_page":public_on(),"banner":get("banner",""),"tz":panel_tz(),"tz_region":tz_region(),"tz_utc":get("tz_utc","0")=="1","tz_list":tz_list()}
    o.update(month_info())
    return jsonify(o)
@app.post("/api/settings")
@auth
def settings_set():
    d=request.get_json(silent=True) or {}
    upd={}
    try:
        if d.get("cap_gb") not in (None,""):
            v=float(d["cap_gb"])
            if not 0<=v<=10000000:
                return err("bad_values")
            upd["cap_gb"]=v
        if d.get("used_gb") not in (None,""):
            v=float(d["used_gb"])
            if not 0<=v<=10000000:
                return err("bad_values")
            m=month_info()
            basis=d.get("cap_basis") if d.get("cap_basis") in ("out","total") else m["cap_basis"]
            base=m["month_tx"] if basis=="out" else m["month_rx"]+m["month_tx"]
            upd["m_off"]=int(v*GB)-base
    except (TypeError,ValueError):
        return err("bad_values")
    if d.get("cap_basis") in ("out","total"):
        upd["cap_basis"]=d["cap_basis"]
    if d.get("reset"):
        upd.update({"m_rx":0,"m_tx":0,"m_off":0})
        n=pnow()
        c=db()
        c.execute("DELETE FROM daily WHERE d LIKE ?",("%04d-%02d-%%"%(n.year,n.month),))
        c.commit()
        c.close()
    if "tz" in d:
        v=str(d["tz"]).strip()
        if v and not (v.split("/")[0] in TZ_AREAS and tz_ok(v)):
            return err("bad_tz")
        upd["tz"]=v
    if "tz_utc" in d:
        upd["tz_utc"]="1" if d["tz_utc"] else "0"
    if "public_page" in d:
        upd["public_page"]="1" if d["public_page"] else "0"
    if "banner" in d:
        txt=clean_banner(d["banner"])
        if txt is None:
            return err("bad_values")
        e=apply_banner(txt)
        if e:
            return err("system",400,e)
        upd["banner"]=txt
    if upd:
        puts(upd)
    return jsonify(ok=True)
def clean_banner(v):
    if not isinstance(v,str):
        return None
    v=v.replace("\r\n","\n").replace("\r","\n")
    v="".join(ch for ch in v if ch in "\n\t" or ch>=" " and ch!="\x7f").strip()
    return v if len(v)<=BANNER_MAX else None
def apply_banner(txt):
    old=None
    try:
        with open(BANNER_CONF) as f:
            old=f.read()
    except OSError:
        pass
    try:
        if txt:
            os.makedirs(os.path.dirname(BANNER_TXT),exist_ok=True)
            with open(BANNER_TXT,"w",encoding="utf-8") as f:
                f.write(txt+"\n")
            os.chmod(BANNER_TXT,0o644)
            with open(BANNER_CONF,"w") as f:
                f.write("Match Group vpnusers\nBanner %s\n"%BANNER_TXT)
        else:
            for p in (BANNER_CONF,BANNER_TXT):
                if os.path.exists(p):
                    os.unlink(p)
    except OSError as e:
        return str(e)
    r=sh(["sshd","-t"])
    if r.returncode:
        try:
            if old is None:
                if os.path.exists(BANNER_CONF):
                    os.unlink(BANNER_CONF)
            else:
                with open(BANNER_CONF,"w") as f:
                    f.write(old)
        except OSError:
            pass
        return ((r.stderr or r.stdout or "").strip()[-300:]) or "sshd rejected the configuration"
    sh(["systemctl","reload","ssh"])
    return ""
def log_sources():
    out=[]
    for k,(kind,src) in LOGS.items():
        if kind=="file":
            try:
                out.append({"id":k,"kind":"file","size":os.path.getsize(src)})
            except OSError:
                pass
        elif k=="stunnel":
            if os.path.exists("/etc/vpnpanel/stunnel.conf") and os.path.getsize("/etc/vpnpanel/stunnel.conf")>0:
                out.append({"id":k,"kind":"unit"})
        elif k=="udpcustom":
            if comp_installed("udpcustom"):
                out.append({"id":k,"kind":"unit"})
        else:
            out.append({"id":k,"kind":"unit"})
    return out
def log_text(k,n,full=False):
    kind,src=LOGS[k]
    if kind=="file":
        lim=10*1024*1024 if full else 262144
        try:
            with open(src,"rb") as f:
                f.seek(0,2)
                size=f.tell()
                f.seek(max(0,size-lim))
                data=f.read()
        except OSError:
            return ""
        txt=data.decode("utf-8","replace")
        if size>lim:
            txt=txt.split("\n",1)[-1]
        if not full:
            txt="\n".join(txt.splitlines()[-n:])
        return txt
    args=["journalctl","--no-pager","-q","-o","short-iso","-n",str(n)]
    for u in src:
        args+=["-u",u]
    since=get("logclr_"+k)
    if since:
        args+=["--since",time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(int(since)))]
    try:
        r=subprocess.run(args,capture_output=True,text=True,errors="replace",timeout=40)
    except subprocess.TimeoutExpired:
        return ""
    return "\n".join(l for l in r.stdout.splitlines() if not l.startswith("-- "))
@app.get("/api/logs")
@auth
def logs_list():
    return jsonify(items=log_sources())
@app.get("/api/logs/<k>")
@auth
def logs_view(k):
    if k not in LOGS:
        return err("not_found",404)
    try:
        n=max(10,min(2000,int(request.args.get("n",500))))
    except ValueError:
        n=500
    return jsonify(text=log_text(k,n))
@app.get("/api/logs/<k>/download")
@auth
def logs_download(k):
    if k not in LOGS:
        return err("not_found",404)
    txt=log_text(k,50000,True)
    name="isile-%s-%s.log"%(k,time.strftime("%Y%m%d-%H%M%S"))
    return Response(txt+"\n",mimetype="text/plain; charset=utf-8",headers={"Content-Disposition":'attachment; filename="%s"'%name})
@app.post("/api/logs/<k>/clear")
@auth
def logs_clear(k):
    if k not in LOGS:
        return err("not_found",404)
    kind,src=LOGS[k]
    if kind=="file":
        try:
            open(src,"w").close()
        except OSError as e:
            return err("system",500,str(e))
    else:
        put("logclr_"+k,int(time.time()))
    return jsonify(ok=True)
@app.get("/api/domain")
@auth
def domain_get():
    cur=get("domain","")
    cand=str(request.args.get("d","")).strip().lower() or cur
    if cand and not DOMAIN_RE.match(cand):
        return err("bad_domain")
    ip=get("server_ip","")
    dns=dns_of(cand) if cand else []
    return jsonify(domain=cur,candidate=cand,server_ip=ip,dns=dns,match=bool(ip and ip in dns),cert=cert_info(cand))
def start_job(kind,cmd):
    if os.path.exists(RCF):
        os.unlink(RCF)
    with open(JOBF,"w") as f:
        json.dump({"kind":kind,"started":time.time()},f)
    r=sh(["systemd-run","--no-block","--collect","--quiet","bash","-c","%s; echo $? > %s"%(cmd,RCF)])
    if r.returncode:
        if os.path.exists(JOBF):
            os.unlink(JOBF)
        return ((r.stderr or r.stdout or "").strip()[-300:]) or "systemd-run failed"
    return ""
@app.post("/api/domain")
@auth
def domain_set():
    d=request.get_json(silent=True) or {}
    dom=str(d.get("domain","")).strip().lower()
    email=str(d.get("email","")).strip()
    if not DOMAIN_RE.match(dom):
        return err("bad_domain")
    if email and not EMAIL_RE.match(email):
        return err("bad_email")
    e=start_job("domain","bash %s/setdomain.sh %s %s"%(BASE,shq(dom),shq(email)))
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
LATEST_URL="https://raw.githubusercontent.com/tamaa-pro/isile/refs/heads/main/panel/VERSION"
@app.get("/api/system/latest")
@auth
def latest_version():
    v=""
    try:
        req=Request(LATEST_URL+"?t=%d"%int(time.time()*1000),headers={"User-Agent":"isile","Cache-Control":"no-cache, no-store","Pragma":"no-cache"})
        with urlopen(req,timeout=6) as r:
            v=r.read(256).decode("utf-8","replace").strip().splitlines()[0].strip()
    except Exception:
        v=""
    if not re.match(r"^[0-9A-Za-z .+_-]{1,32}$",v):
        return err("unavailable",502)
    return jsonify(latest=v)
@app.post("/api/system/restart")
@auth
def sys_restart():
    us=[u for c,u in (("xray","xray"),("wsbridge","vpnbridge"),("udpcustom","udp-custom")) if comp_on(c)]+["nginx","vpnmux"]
    e=start_job("restart","sleep 1; systemctl restart %s; if [ -s /etc/vpnpanel/stunnel.conf ]; then systemctl restart vpnstunnel; fi; systemctl restart vpnpanel"%" ".join(us))
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
@app.post("/api/system/update")
@auth
def sys_update():
    e=start_job("update","/usr/local/bin/isile 4")
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
@app.post("/api/system/uninstall")
@auth
def sys_uninstall():
    d=request.get_json(silent=True) or {}
    if not check_password_hash(get("admin_hash",""),str(d.get("password",""))):
        return err("wrong_password")
    e=start_job("uninstall","/usr/local/bin/isile 3 --yes")
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
@app.post("/api/system/reset")
@auth
def sys_reset():
    d=request.get_json(silent=True) or {}
    if not check_password_hash(get("admin_hash",""),str(d.get("password",""))):
        return err("wrong_password")
    with LOCK:
        c=db()
        try:
            for r in c.execute("SELECT name,proto FROM accounts").fetchall():
                if r["proto"]=="ssh":
                    ssh_del(r["name"])
            c.execute("DELETE FROM accounts")
            c.execute("DELETE FROM daily")
            c.execute("DELETE FROM settings WHERE k IN ('cap_gb','cap_basis','public_page','banner')")
            c.commit()
            puts({"m_rx":0,"m_tx":0,"m_off":0})
            apply_banner("")
            nft_apply(c)
            xray_sync(c)
        except Exception as e:
            traceback.print_exc()
            return err("system",500,str(e)[-300:])
        finally:
            c.close()
        for m in (CONN,ACTIVE,SPEED,SP_B,SSH_OVER):
            m.clear()
    return jsonify(ok=True)
@app.get("/api/system/job")
@auth
def sys_job():
    if not os.path.exists(JOBF):
        return jsonify(state="none")
    try:
        with open(JOBF) as f:
            j=json.load(f)
    except (OSError,ValueError):
        return jsonify(state="none")
    if os.path.exists(RCF):
        try:
            with open(RCF) as f:
                rc=int(f.read().strip() or 1)
        except (OSError,ValueError):
            rc=1
        try:
            with open(LOGF) as f:
                tail="".join(f.readlines()[-14:])
        except OSError:
            tail=""
        for p in (JOBF,RCF):
            if os.path.exists(p):
                os.unlink(p)
        return jsonify(state="done",kind=j.get("kind"),rc=rc,log=tail)
    if time.time()-j.get("started",0)>900:
        os.unlink(JOBF)
        return jsonify(state="none")
    return jsonify(state="running",kind=j.get("kind"))
def job_busy():
    if not os.path.exists(JOBF) or os.path.exists(RCF):
        return False
    try:
        with open(JOBF) as f:
            return time.time()-json.load(f).get("started",0)<900
    except (OSError,ValueError):
        return False
def comp_accounts(c,comp):
    q={"xray":"proto IN ('vless','vmess','trojan')","wsbridge":"proto='ssh' AND transport='ws'","udpcustom":"proto='ssh' AND transport='udp'"}.get(comp)
    if not q:
        return 0
    return c.execute("SELECT COUNT(*) n FROM accounts WHERE "+q).fetchone()["n"]
@app.get("/api/components")
@auth
def comps_get():
    off=combos_off()
    c=db()
    try:
        comps={}
        for k in COMP_UNIT:
            o={"installed":comp_installed(k),"removable":k in REMOVABLE,"state":block_state(k,off),"accounts":comp_accounts(c,k)}
            if k=="udpcustom":
                o["port"]=udp_port()
                o["info"]=udpc_info()
            comps[k]=o
    finally:
        c.close()
    return jsonify(combos=combo_info(off),comps=comps,tls_on=tls_on(),busy=job_busy())
@app.post("/api/components/combo")
@auth
def combo_set():
    d=request.get_json(silent=True) or {}
    k=str(d.get("key",""))
    if k not in {p+":"+m for p,m,c in COMBOS}:
        return err("bad_values")
    with LOCK:
        off=combos_off()
        if d.get("enabled"):
            off.discard(k)
        else:
            off.add(k)
        put("combos_off",",".join(sorted(off)))
        c=db()
        try:
            apply_components(c)
        finally:
            c.close()
    return jsonify(ok=True)
@app.post("/api/components/<comp>/<action>")
@auth
def comp_action(comp,action):
    if comp not in REMOVABLE or action not in ("install","uninstall"):
        return err("not_found",404)
    d=request.get_json(silent=True) or {}
    if comp=="udpcustom" and action=="install" and not d.get("ack"):
        return err("ack_required")
    if action=="install" and comp_installed(comp):
        return err("bad_values")
    if job_busy():
        return err("busy",409)
    if action=="install":
        off=combos_off()-set(comp_combos(comp))
        put("combos_off",",".join(sorted(off)))
    cmd=": > %s; bash %s/components.sh %s %s >>%s 2>&1"%(shq(LOGF),shq(BASE),action,comp,shq(LOGF))
    if comp=="xray" and action=="install":
        cmd+=" && systemctl restart vpnpanel"
    e=start_job("component",cmd)
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
@app.get("/api/accounts")
@auth
def lst():
    c=db()
    rows=[]
    for r in c.execute("SELECT * FROM accounts ORDER BY created DESC"):
        o={k:r[k] for k in ("name","proto","status","manual","created","expires","quota","up","down","note","tls","transport")}
        cn=CONN.get(r["name"],{})
        o["conn"]=cn.get("n",0)
        o["conn_limit"]=r["conn_limit"]
        o["active"]=r["status"]=="active" and (o["conn"]>0 or time.time()-ACTIVE.get(r["name"],0)<ACTIVE_TTL)
        o["sp_up"],o["sp_down"]=speed_of(r["name"]) if o["active"] else (0,0)
        rows.append(o)
    c.close()
    return jsonify(rows)
def vmess_link(n,s,dom,tls,grpc=False):
    o={"v":"2","ps":n+("-TLS" if tls else "-80"),"add":dom,"port":"443" if tls else "80","id":s,"aid":"0","scy":"auto","net":"grpc" if grpc else "ws","type":"gun" if grpc else "none","host":"" if grpc else dom,"path":"vmess-grpc" if grpc else "/vmess","tls":"tls" if tls else "","sni":dom if tls else "","alpn":"h2" if grpc and tls else ""}
    return "vmess://"+base64.b64encode(json.dumps(o,separators=(",",":")).encode()).decode()
@app.get("/api/accounts/<name>/info")
@auth
def info(name):
    c=db()
    r=c.execute("SELECT * FROM accounts WHERE name=?",(name,)).fetchone()
    c.close()
    if not r:
        return err("not_found",404)
    dom=host()
    t_on=tls_on()
    s=r["secret"]
    n=r["name"]
    h=quote(n,safe="")
    items=[]
    p=r["proto"]
    if p=="ssh" and r["transport"]=="udp":
        up=udp_port()
        items=[{"k":"udp_addr","value":"%s:%d@%s:%s"%(dom,up,n,s),"rows":2},{"k":"udp_port","value":str(up),"rows":1},{"k":"user","value":n,"rows":1},{"k":"pass","value":s,"rows":1}]
    elif p=="ssh" and r["transport"]=="ssl":
        want_tls=t_on and r["tls"] in ("tls","both")
        if want_tls:
            items.append({"k":"ssl_tls","value":"%s:443@%s:%s"%(dom,n,s),"rows":2})
        if r["tls"] in ("plain","both"):
            items.append({"k":"ssl_plain","value":"%s:80@%s:%s"%(dom,n,s),"rows":2})
        if want_tls:
            items.append({"k":"sni","value":dom,"rows":1})
        items+=[{"k":"user","value":n,"rows":1},{"k":"pass","value":s,"rows":1}]
    elif p=="ssh":
        items=[{"k":"payload","value":"GET / HTTP/1.1[crlf]Host: %s[crlf]Upgrade: websocket[crlf][crlf]"%dom,"rows":3},{"k":"user","value":n,"rows":1},{"k":"pass","value":s,"rows":1}]
        if r["tls"] in ("plain","both"):
            items.insert(0,{"k":"ssh_plain","value":"%s:80@%s:%s"%(dom,n,s),"rows":2})
        if t_on and r["tls"] in ("tls","both"):
            items.insert(0,{"k":"ssh_tls","value":"%s:443@%s:%s"%(dom,n,s),"rows":2})
    else:
        for m in (MODES if r["tls"]=="both" else (r["tls"],)):
            tls=m=="tls"
            if tls and not t_on:
                continue
            grpc=r["transport"]=="grpc"
            tail=h+("-TLS" if tls else "-80")
            sec="sni=%s&fp=chrome&%s"%(dom,"alpn=h2&" if grpc else "") if tls else ""
            if grpc:
                net="type=grpc&serviceName=%s-grpc&mode=gun"%p
            else:
                net="type=ws&host=%s&path=%%2F%s"%(dom,p)
            if p=="vmess":
                v=vmess_link(n,s,dom,tls,grpc)
            elif p=="vless":
                v="vless://%s@%s:%d?encryption=none&security=%s&%s%s#%s"%(s,dom,443 if tls else 80,"tls" if tls else "none",sec,net,tail)
            else:
                v="trojan://%s@%s:%d?security=%s&%s%s#%s"%(quote(s,safe=""),dom,443 if tls else 80,"tls" if tls else "none",sec,net,tail)
            items.append({"k":"link_tls" if tls else "link_plain","value":v,"rows":4})
        items.append({"k":"pass" if p=="trojan" else "uuid","value":s,"rows":1})
        if r["transport"]=="grpc":
            items.append({"k":"grpc_service","value":p+"-grpc","rows":1})
    if public_on():
        items.insert(0,{"k":"page","value":page_url(n),"rows":1})
    cn=CONN.get(n,{})
    act=r["status"]=="active" and (cn.get("n",0)>0 or time.time()-ACTIVE.get(n,0)<ACTIVE_TTL)
    spu,spd=speed_of(n) if act else (0,0)
    return jsonify(conn=cn.get("n",0),conn_limit=r["conn_limit"],items=items,active=act,sp_up=spu,sp_down=spd,status=r["status"],up=r["up"],down=r["down"],quota=r["quota"],created=r["created"],expires=r["expires"],proto=p,transport=r["transport"],tls=r["tls"],tls_on=t_on,note=r["note"])
def parse_common(d,creating):
    try:
        out={}
        now=int(time.time())
        if d.get("expires") not in (None,""):
            e=int(d["expires"])
            if e<0 or e>now+3650*86400:
                return None
            out["expires"]=e
        elif creating or d.get("days") not in (None,""):
            days=int(d.get("days") or 0)
            if not 0<=days<=3650:
                return None
            out["expires"]=now+days*86400 if days else 0
        if creating or d.get("quota_gb") not in (None,""):
            q=float(d.get("quota_gb") or 0)
            if not 0<=q<=100000:
                return None
            out["quota"]=int(q*GB)
        if creating or d.get("conn_limit") not in (None,""):
            cl=int(d.get("conn_limit") or 0)
            if not 0<=cl<=CONN_MAX:
                return None
            out["conn_limit"]=cl
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
    if name in RESERVED:
        return err("name_reserved")
    pc=parse_common(d,True)
    if pc is None:
        return err("bad_values")
    if proto!="ssh":
        pc["conn_limit"]=0
    if pc["expires"] and pc["expires"]<=int(time.time()):
        return err("past_date")
    tls=d.get("tls","both" if proto=="ssh" else "tls")
    if tls not in ("tls","plain","both"):
        return err("bad_values")
    transport=d.get("transport","ws")
    if transport not in TRANSPORTS:
        return err("bad_values")
    if proto!="ssh":
        transport="grpc" if transport=="grpc" else "ws"
    elif transport=="grpc":
        return err("bad_values")
    if transport=="udp":
        tls="plain"
    dk=keys_denied(acct_keys(proto,transport,tls))
    if dk:
        return err("combo_disabled",400,dk)
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
            c.execute("INSERT INTO accounts(name,proto,secret,uid,created,expires,quota,note,status,tls,transport,conn_limit) VALUES(?,?,?,?,?,?,?,?,'active',?,?,?)",(name,proto,sec,uid,now,pc["expires"],pc["quota"],note,tls,transport,pc["conn_limit"]))
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
            if "expires" in pc:
                sets["expires"]=pc["expires"]
            if "quota" in pc:
                sets["quota"]=pc["quota"]
            if "conn_limit" in pc and r["proto"]=="ssh":
                sets["conn_limit"]=pc["conn_limit"]
            if d.get("tls"):
                if d["tls"] not in ("tls","plain","both"):
                    return err("bad_values")
                sets["tls"]=d["tls"]
            if d.get("transport"):
                okt=V2NETS if r["proto"]!="ssh" else ("ws","ssl","udp")
                if d["transport"] not in okt:
                    return err("bad_values")
                sets["transport"]=d["transport"]
            ntr=sets.get("transport",r["transport"])
            if r["proto"]=="ssh" and ntr=="udp":
                sets["tls"]="plain"
            ntls=sets.get("tls",r["tls"])
            if (ntls,ntr)!=(r["tls"],r["transport"]):
                dk=keys_denied(acct_keys(r["proto"],ntr,ntls))
                if dk:
                    return err("combo_disabled",400,dk)
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
            if r["proto"]=="ssh":
                nft_apply(c)
            else:
                xray_sync(c)
        finally:
            c.close()
    return jsonify(ok=True)
GEO=[0,False]
def geo_lookup(ip):
    for url in ("https://ipwho.is/%s"%ip,"https://ipapi.co/%s/json/"%ip):
        try:
            with urlopen(Request(url,headers={"User-Agent":"isile"}),timeout=5) as r:
                cc=str(json.loads(r.read(65536).decode("utf-8","replace")).get("country_code","")).upper()
            if re.match(r"^[A-Z]{2}$",cc):
                return cc
        except Exception:
            pass
    return ""
def geo_job(ip):
    try:
        cc=geo_lookup(ip)
        if cc:
            puts({"geo_ip":ip,"geo_cc":cc})
    finally:
        GEO[0]=time.time()
        GEO[1]=False
def server_cc():
    ip=get("server_ip","")
    if not ip:
        return ""
    g=gets("geo_ip","geo_cc")
    if g.get("geo_ip")==ip and g.get("geo_cc"):
        return g["geo_cc"]
    if not GEO[1] and time.time()-GEO[0]>600:
        GEO[1]=True
        threading.Thread(target=geo_job,args=(ip,),daemon=True).start()
    return ""
@app.get("/api/public/<name>")
def public_api(name):
    name=name.lower()
    if not public_on() or not NAME_RE.match(name):
        return err("not_found",404)
    c=db()
    r=c.execute("SELECT * FROM accounts WHERE name=?",(name,)).fetchone()
    c.close()
    if not r:
        return err("not_found",404)
    cn=CONN.get(name,{})
    act=r["status"]=="active" and (cn.get("n",0)>0 or time.time()-ACTIVE.get(name,0)<ACTIVE_TTL)
    spu,spd=speed_of(name) if act else (0,0)
    return jsonify(conn=cn.get("n",0),conn_limit=r["conn_limit"],name=r["name"],proto=r["proto"],transport=r["transport"],tls=r["tls"],status=r["status"],active=act,up=r["up"],down=r["down"],quota=r["quota"],created=r["created"],expires=r["expires"],sp_up=spu,sp_down=spd,now=int(time.time()),cc=server_cc())
@app.get("/<name>")
def public_page(name):
    name=name.lower()
    if not public_on() or name in RESERVED or not NAME_RE.match(name):
        return "Not found",404
    return render_template("public.html",name=name,version=VERSION,tz=panel_tz())
def main():
    cmd=sys.argv[1] if len(sys.argv)>1 else "serve"
    init_db()
    if cmd=="setup":
        put("admin_user",os.environ["VPN_ADMIN_USER"])
        put("admin_hash",generate_password_hash(os.environ["VPN_ADMIN_PASS"]))
        puts({"domain":os.environ.get("VPN_DOMAIN",""),"server_ip":os.environ.get("VPN_SERVER_IP","")})
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
    if cmd=="setserver":
        if os.environ.get("VPN_SERVER_IP"):
            put("server_ip",os.environ["VPN_SERVER_IP"])
        return
    if cmd=="setdomain":
        put("domain",os.environ["VPN_DOMAIN"])
        return
    if cmd=="svcs":
        print(" ".join(expected_units()))
        return
    if cmd=="applycomps":
        c=db()
        try:
            apply_components(c)
        finally:
            c.close()
        return
    app.config.update(SECRET_KEY=get("secret_key"),SESSION_COOKIE_NAME="vpnsid",SESSION_COOKIE_SECURE=tls_on(),SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Strict",MAX_CONTENT_LENGTH=65536,PERMANENT_SESSION_LIFETIME=timedelta(hours=24))
    with LOCK:
        c=db()
        nft_apply(c)
        reconcile(c)
        try:
            apply_components(c)
        except Exception:
            traceback.print_exc()
        c.close()
    threading.Thread(target=worker,daemon=True).start()
    threading.Thread(target=conn_worker,daemon=True).start()
    threading.Thread(target=udp_follow,daemon=True).start()
    from waitress import serve
    serve(app,host="127.0.0.1",port=8000,threads=8)
if __name__=="__main__":
    main()
