import os,sys,re,io,gzip,struct,glob,json,time,uuid,hmac,base64,socket,calendar,secrets,shutil,sqlite3,tempfile,ipaddress,functools,threading,traceback,subprocess
from datetime import timedelta,datetime,timezone
from zoneinfo import ZoneInfo,available_timezones
from shlex import quote as shq
from urllib.parse import quote
from urllib.request import urlopen,Request
from flask import Flask,request,session,jsonify,render_template,redirect,Response,has_request_context
from werkzeug.security import generate_password_hash,check_password_hash
import sshconn
BASE=os.path.dirname(os.path.abspath(__file__))
APPDIR=os.path.dirname(BASE)
DATA="/var/lib/vpnpanel"
DBP=DATA+"/panel.db"
JOBF=DATA+"/job.json"
RCF=DATA+"/job.rc"
LOGF="/var/log/isile-install.log"
AUDIT="/var/log/isile-audit.log"
ARCH="/var/log/isile-archive"
ARCH_KEEP=5
SELFSIGNED_CERT="/etc/vpnpanel/selfsigned/cert.pem"
BANNER_TXT="/etc/vpnpanel/banner.txt"
BANNER_CONF="/etc/ssh/sshd_config.d/99-zvpnpanel-banner.conf"
BANNER_MAX=2000
DEFAULT_BANNER="<font color=\"#00FF00\">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nisile: The server has been contacted ᐠ( ᐢ ᵕ ᐢ )ᐟ\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</font>"
DECOY_RE=re.compile(r"^https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~%/?=&:@+-]*)?$")
DECOY_MAX=300
LOGS={"install":("file",LOGF),"audit":("file",AUDIT),"panel":("unit",["vpnpanel"]),"xray":("unit",["xray"]),"ssh":("unit",["ssh","sshd"]),"bridge":("unit",["vpnbridge"]),"mux":("unit",["vpnmux"]),"stunnel":("unit",["vpnstunnel"]),"nginx":("unit",["nginx"]),"nginx_err":("file","/var/log/nginx/error.log"),"nginx_acc":("file","/var/log/nginx/access.log"),"udpcustom":("unit",["udp-custom"]),"vaydns":("unit",["vaydns"]),"slowdns":("unit",["slowdns"])}
XCONF="/usr/local/etc/xray/config.json"
XBIN="/usr/local/bin/xray"
XAPI="127.0.0.1:10085"
UID0=20000
UID1=60000
GB=1073741824
V2=("vless","vmess","trojan")
PROTOS=("ssh",)+V2
MODES=("tls","plain")
TRANSPORTS=("ws","ssl","direct","udp","grpc","xhttp","dns","slowdns")
V2NETS=("ws","grpc","xhttp")
UNITDIR="/etc/systemd/system"
UDPC_DIR="/usr/local/lib/isile/udp-custom"
UDPC_BIN=UDPC_DIR+"/udp-custom"
UDPC_CONF=UDPC_DIR+"/config.json"
UDPC_INFO="/etc/vpnpanel/udp-custom.info"
UDPC_PORT=36712
VAYDNS_DIR="/usr/local/lib/isile/vaydns"
VAYDNS_BIN=VAYDNS_DIR+"/vaydns-server"
VAYDNS_PUB=VAYDNS_DIR+"/server.pub"
VAYDNS_ENV="/etc/vpnpanel/vaydns.env"
VAYDNS_INFO="/etc/vpnpanel/vaydns.info"
VAYDNS_PORT=53
VAYDNS_UDP=5300
VAYDNS_LOCAL=7000
SLOWDNS_DIR="/usr/local/lib/isile/slowdns"
SLOWDNS_BIN=SLOWDNS_DIR+"/vaydns-server"
SLOWDNS_PUB=SLOWDNS_DIR+"/server.pub"
SLOWDNS_ENV="/etc/vpnpanel/slowdns.env"
SLOWDNS_INFO="/etc/vpnpanel/slowdns.info"
SLOWDNS_UDP=5301
SLOWDNS_LOCAL=7001
DNS_ZONES="/etc/vpnpanel/dnszones"
COMBOS=(("sshws","tls","wsbridge"),("sshws","plain","wsbridge"),("sshssl","tls","sshssl"),("sshdirect","plain","sshdirect"),("sshudp","udp","udpcustom"),("vless","tls","xray"),("vless","plain","xray"),("vmess","tls","xray"),("vmess","plain","xray"),("trojan","tls","xray"),("trojan","plain","xray"),("sshdns","plain","vaydns"),("vlessdns","tls","vaydns"),("vlessdns","plain","vaydns"),("vmessdns","tls","vaydns"),("vmessdns","plain","vaydns"),("trojandns","tls","vaydns"),("trojandns","plain","vaydns"),("sshslowdns","plain","slowdns"))
COMBO_REQ={"vlessdns":"xray","vmessdns":"xray","trojandns":"xray"}
COMP_UNIT={"wsbridge":"vpnbridge","sshssl":"vpnmux","sshdirect":"ssh","udpcustom":"udp-custom","xray":"xray","vaydns":"vaydns","slowdns":"slowdns"}
REMOVABLE=("wsbridge","udpcustom","xray","vaydns","slowdns")
PORTS={("vless","tls"):10001,("trojan","tls"):10002,("vmess","tls"):10003,("vless","plain"):10011,("trojan","plain"):10012,("vmess","plain"):10013}
XPORTS={("vless","tls"):10201,("trojan","tls"):10202,("vmess","tls"):10203,("vless","plain"):10211,("trojan","plain"):10212,("vmess","plain"):10213}
GPORTS={("vless","tls"):10101,("trojan","tls"):10102,("vmess","tls"):10103,("vless","plain"):10111,("trojan","plain"):10112,("vmess","plain"):10113}
NAME_RE=re.compile(r"^[a-z][a-z0-9_]{2,19}$")
SECRET_RE=re.compile(r"^[A-Za-z0-9@#%_.+=-]{6,64}$")
UUID_RE=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DOMAIN_RE=re.compile(r"^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$")
EMAIL_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
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
TOKEN_RE=re.compile(r"^[0-9a-f]{24}$")
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
CREATE TABLE IF NOT EXISTS daily(d TEXT PRIMARY KEY,rx INTEGER NOT NULL DEFAULT 0,tx INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,created INTEGER NOT NULL,last INTEGER NOT NULL,exp INTEGER NOT NULL DEFAULT 0,ended INTEGER NOT NULL DEFAULT 0,why TEXT NOT NULL DEFAULT '',ip TEXT NOT NULL DEFAULT '',dev TEXT NOT NULL DEFAULT '',os TEXT NOT NULL DEFAULT '',br TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS login_log(ts INTEGER NOT NULL,ok INTEGER NOT NULL,ip TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS login_log_ts ON login_log(ts);""")
    cols={r["name"] for r in c.execute("PRAGMA table_info(accounts)")}
    if "tls" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN tls TEXT NOT NULL DEFAULT 'tls'")
    if "transport" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN transport TEXT NOT NULL DEFAULT 'ws'")
    if "conn_limit" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN conn_limit INTEGER NOT NULL DEFAULT 0")
    if "public" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN public INTEGER NOT NULL DEFAULT 0")
    if "ptoken" not in cols:
        c.execute("ALTER TABLE accounts ADD COLUMN ptoken TEXT NOT NULL DEFAULT ''")
    for r in c.execute("SELECT name FROM accounts WHERE ptoken=''").fetchall():
        c.execute("UPDATE accounts SET ptoken=? WHERE name=?",(new_token(),r["name"]))
    c.execute("UPDATE accounts SET transport='direct',tls='plain' WHERE proto='ssh' AND transport='ssl' AND tls='plain'")
    c.execute("UPDATE accounts SET tls='tls' WHERE proto='ssh' AND transport='ssl' AND tls!='tls'")
    c.execute("UPDATE accounts SET tls='plain' WHERE proto='ssh' AND transport IN ('dns','slowdns','direct') AND tls!='plain'")
    if not c.execute("SELECT 1 FROM settings WHERE k='banner_on'").fetchone():
        br=c.execute("SELECT v FROM settings WHERE k='banner'").fetchone()
        if br is not None and br["v"]=="":
            c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('banner',?)",(DEFAULT_BANNER,))
            c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('banner_on','0')")
        elif br is not None:
            c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('banner_on','1')")
    c.execute("DROP TABLE IF EXISTS v2block")
    c.execute("UPDATE accounts SET conn_limit=0 WHERE proto!='ssh' AND conn_limit!=0")
    c.commit()
    c.close()
    os.chmod(DBP,0o600)
    if not get("secret_key"):
        put("secret_key",secrets.token_hex(32))
    if not get("sess_ver"):
        rotate_sessions()
def new_token():
    return secrets.token_hex(12)
def rotate_sessions(why="password"):
    put("sess_ver",secrets.token_hex(16))
    end_sessions(why)
def end_sessions(why,sid=None):
    """Mark open sessions as ended (all of them, or only sid). Returns how many were closed."""
    now=int(time.time())
    c=db()
    try:
        if sid:
            n=c.execute("UPDATE sessions SET ended=?,why=? WHERE id=? AND ended=0",(now,why,sid)).rowcount
        else:
            n=c.execute("UPDATE sessions SET ended=?,why=? WHERE ended=0",(now,why)).rowcount
        c.commit()
    except sqlite3.Error:
        n=0
    finally:
        c.close()
    return n
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
def panel_https():
    return tls_on() or (get("selfsigned","0")=="1" and os.path.isfile(SELFSIGNED_CERT))
def panel_domain():
    """Optional subdomain that serves the panel on port 443 instead of the panel port ('' when not set)."""
    return get("panel_domain","")
def panel_domain_on():
    """True while the panel is really served from its subdomain (main domain set and the subdomain certificate present)."""
    pd=panel_domain()
    return bool(pd and tls_on() and pd!=get("domain","") and os.path.exists("/etc/letsencrypt/live/%s/fullchain.pem"%pd))
def under_tunnel(d):
    """True when d is a DNS tunnel domain or lives below one (its DNS answers belong to the tunnel server)."""
    for t in (vaydns_domain(),slowdns_domain()):
        if t and (d==t or d.endswith("."+t)):
            return True
    return False
def panel_port():
    """Panel port chosen at install or from the terminal menu (nginx listens on it). Default 2080."""
    v=get("port_panel","")
    return int(v) if re.fullmatch(r"[0-9]{2,5}",v or "") and 1024<=int(v)<=65535 else 2080
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
DNSSIG=[None]
def dns_servers():
    v4=["127.0.0.0/8"]
    v6=["::1"]
    try:
        with open("/etc/resolv.conf") as f:
            lines=f.read().splitlines()
    except OSError:
        lines=[]
    for l in lines:
        m=re.match(r"\s*nameserver\s+(\S+)",l)
        if not m or "%" in m.group(1):
            continue
        try:
            ip=ipaddress.ip_address(m.group(1))
        except ValueError:
            continue
        if ip.is_loopback or ip.is_link_local and ip.version==6:
            continue
        a=str(ip)
        if ip.version==4:
            if a not in v4:
                v4.append(a)
        elif a not in v6:
            v6.append(a)
    return v4,v6
def dns_sig():
    v4,v6=dns_servers()
    return (tuple(v4),tuple(v6))
def nft_apply(c):
    uids=[r["uid"] for r in c.execute("SELECT uid FROM accounts WHERE proto='ssh' AND uid IS NOT NULL")]
    rng="meta skuid >= %d meta skuid < %d"%(UID0,UID1)
    L=["table inet vpnacct","delete table inet vpnacct","table inet vpnacct {"]
    for u in uids:
        L.append(" counter cu%d { }"%u)
        L.append(" counter cd%d { }"%u)
    L.append(" chain out {")
    L.append("  type filter hook output priority -150; policy accept;")
    ns4,ns6=dns_servers()
    DNSSIG[0]=(tuple(ns4),tuple(ns6))
    L.append("  "+rng+" meta l4proto { tcp, udp } th dport 53 ip daddr { %s } accept"%", ".join(ns4))
    L.append("  "+rng+" meta l4proto { tcp, udp } th dport 53 ip6 daddr { %s } accept"%", ".join(ns6))
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
    if c=="vaydns":
        return unit_exists("vaydns") and os.path.exists(VAYDNS_BIN)
    if c=="slowdns":
        return unit_exists("slowdns") and os.path.exists(SLOWDNS_BIN)
    return True
def combos_off():
    return {x for x in get("combos_off","").split(",") if x}
def comp_combos(c):
    return [p+":"+m for p,m,k in COMBOS if k==c]
def comp_enabled(c,off=None):
    off=combos_off() if off is None else off
    ks=comp_combos(c)
    if c=="xray" and comp_installed("vaydns"):
        ks=ks+[p+":"+m for p,m,k in COMBOS if p in COMBO_REQ]
    return any(k not in off for k in ks)
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
def vaydns_domain():
    return get("vaydns_domain","")
def slowdns_domain():
    return get("slowdns_domain","")
def dns_pub(path):
    try:
        with open(path) as f:
            v=f.read().strip()
        return v if re.match(r"^[A-Za-z0-9+/=_-]{16,200}$",v) else ""
    except OSError:
        return ""
def vaydns_pub():
    return dns_pub(VAYDNS_PUB)
def slowdns_pub():
    return dns_pub(SLOWDNS_PUB)
def dns_info(path):
    o={}
    try:
        with open(path) as f:
            for l in f:
                k,_,v=l.partition("=")
                if k in ("url","sha256"):
                    o[k]=v.strip()
    except OSError:
        return None
    return o or None
def vaydns_info():
    return dns_info(VAYDNS_INFO)
def slowdns_info():
    return dns_info(SLOWDNS_INFO)
def dns_env_write(path,var,d):
    try:
        if d:
            txt="%s=%s\n"%(var,d)
            try:
                with open(path) as f:
                    if f.read()==txt:
                        return False
            except OSError:
                pass
            os.makedirs(os.path.dirname(path),exist_ok=True)
            tmp=path+".tmp"
            with open(tmp,"w") as f:
                f.write(txt)
            os.chmod(tmp,0o644)
            os.replace(tmp,path)
            return True
        if os.path.exists(path):
            os.unlink(path)
            return True
    except OSError:
        traceback.print_exc()
    return False
def vaydns_env_write():
    return dns_env_write(VAYDNS_ENV,"VAYDNS_DOMAIN",vaydns_domain())
def slowdns_env_write():
    return dns_env_write(SLOWDNS_ENV,"SLOWDNS_DOMAIN",slowdns_domain())
def dns_zones_write(off=None):
    """UDP 53 is shared: the DNS front in vpnmux routes each query to the tunnel server that owns its domain."""
    if not (comp_installed("vaydns") or comp_installed("slowdns")):
        return
    z=[]
    if comp_installed("vaydns") and comp_enabled("vaydns",off) and vaydns_domain():
        z.append("%s %d"%(vaydns_domain(),VAYDNS_UDP))
    if comp_installed("slowdns") and comp_enabled("slowdns",off) and slowdns_domain():
        z.append("%s %d"%(slowdns_domain(),SLOWDNS_UDP))
    txt="".join(x+"\n" for x in z)
    try:
        try:
            with open(DNS_ZONES) as f:
                if f.read()==txt:
                    return
        except OSError:
            pass
        os.makedirs(os.path.dirname(DNS_ZONES),exist_ok=True)
        tmp=DNS_ZONES+".tmp"
        with open(tmp,"w") as f:
            f.write(txt)
        os.chmod(tmp,0o644)
        os.replace(tmp,DNS_ZONES)
    except OSError:
        traceback.print_exc()
def dns_unit_sync(comp,ch,dom,off):
    if comp_enabled(comp,off) and dom:
        if not svc_active(comp):
            sh(["systemctl","enable","--now",comp])
        elif ch:
            sh(["systemctl","restart",comp])
    else:
        sh(["systemctl","disable","--now",comp])
def vaydns_sync(off=None):
    if not comp_installed("vaydns"):
        return
    dns_unit_sync("vaydns",vaydns_env_write(),vaydns_domain(),off)
def slowdns_sync(off=None):
    if not comp_installed("slowdns"):
        return
    dns_unit_sync("slowdns",slowdns_env_write(),slowdns_domain(),off)
def combo_info(off=None):
    off=combos_off() if off is None else off
    t=tls_on()
    tdoms={"vaydns":vaydns_domain(),"slowdns":slowdns_domain()}
    inst={c:comp_installed(c) for c in COMP_UNIT}
    out=[]
    for p,m,c in COMBOS:
        k=p+":"+m
        why=""
        if not inst[c] or (p in COMBO_REQ and not inst[COMBO_REQ[p]]):
            why="not_installed"
        elif k in off:
            why="disabled"
        elif m=="tls" and not t:
            why="no_tls"
        elif c in tdoms and not tdoms[c]:
            why="no_domain"
        out.append({"k":k,"p":p,"m":m,"c":c,"enabled":k not in off,"installed":inst[c],"avail":not why,"why":why})
    return out
def acct_keys(proto,transport,tls):
    if proto=="ssh":
        if transport=="udp":
            return ["sshudp:udp"]
        if transport=="direct":
            return ["sshdirect:plain"]
        if transport in ("dns","slowdns"):
            return [("sshdns" if transport=="dns" else "sshslowdns")+":plain"]
        if transport=="ssl":
            return ["sshssl:tls"]
        base="sshws" if transport=="ws" else "sshdns" if transport=="dns" else "sshslowdns" if transport=="slowdns" else "sshssl"
    else:
        base=proto+"dns" if transport=="dns" else proto
    return [base+":"+m for m in (MODES if tls=="both" else (tls,))]
def keys_denied(keys):
    off=combos_off()
    cm={p+":"+m:c for p,m,c in COMBOS}
    for k in keys:
        c=cm.get(k)
        if not c or not comp_installed(c) or k in off:
            return k
        if c=="vaydns":
            b=k.split(":")[0]
            if not vaydns_domain() or (b in COMBO_REQ and not comp_installed(COMBO_REQ[b])):
                return k
        if c=="slowdns" and not slowdns_domain():
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
    if comp_on("vaydns") and vaydns_domain():
        u.append("vaydns")
    if comp_on("slowdns") and slowdns_domain():
        u.append("slowdns")
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
            if u and RE_UNAME.fullmatch(u.group(1)):
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
def is_live(n,proto,status,conn):
    if status!="active":
        return False
    if proto=="ssh":
        return conn>0
    return time.time()-ACTIVE.get(n,0)<ACTIVE_TTL
def speed_of(n):
    sp=SPEED.get(n)
    if not sp or time.time()-sp[2]>SPEED_TTL:
        return 0,0
    return int(sp[0]),int(sp[1])
def page_url(key):
    if panel_domain_on():
        return "https://%s/%s"%(panel_domain(),key)
    return "%s://%s:%d/%s"%("https" if panel_https() else "http",host(),panel_port(),key)
def public_on():
    return get("public_page","0")=="1"
def token_mode():
    return get("public_token","0")=="1"
def public_row(key):
    key=(key or "").lower()
    c=db()
    try:
        if TOKEN_RE.fullmatch(key):
            r=c.execute("SELECT * FROM accounts WHERE ptoken=?",(key,)).fetchone()
        elif NAME_RE.fullmatch(key) and key not in RESERVED and not token_mode():
            r=c.execute("SELECT * FROM accounts WHERE name=?",(key,)).fetchone()
        else:
            r=None
    finally:
        c.close()
    if r and (public_on() or r["public"]):
        return r
    return None
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
                elif net=="grpc":
                    ss={"network":"grpc","grpcSettings":{"serviceName":p+"-grpc"}}
                    tag,port=p+"-"+m+"-grpc",GPORTS[(p,m)]
                else:
                    ss={"network":"xhttp","xhttpSettings":{"path":"/"+p+"-xhttp","mode":"auto"}}
                    tag,port=p+"-"+m+"-xhttp",XPORTS[(p,m)]
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
        dns_zones_write(off)
        vaydns_sync(off)
        slowdns_sync(off)
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
                    if dns_sig()!=DNSSIG[0]:
                        nft_apply(c)
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
SESS_MODES={"midnight":0,"24h":86400,"48h":172800,"7d":604800,"never":-1}
def sess_mode():
    v=get("sess_mode","midnight")
    return v if v in SESS_MODES else "midnight"
def session_exp():
    m=sess_mode()
    if m=="midnight":
        return midnight_exp()
    if m=="never":
        return 0
    return int(time.time())+SESS_MODES[m]
def ua_info(ua):
    ua=str(ua or "")[:400]
    l=ua.lower()
    if "ipad" in l or "tablet" in l or ("android" in l and "mobile" not in l):
        dev="tablet"
    elif "iphone" in l or "ipod" in l or "mobi" in l:
        dev="mobile"
    elif ua:
        dev="desktop"
    else:
        dev="unknown"
    if "windows" in l:
        o="Windows"
    elif "android" in l:
        o="Android"
    elif "iphone" in l or "ipad" in l or "ipod" in l:
        o="iOS"
    elif "cros" in l:
        o="ChromeOS"
    elif "mac os x" in l or "macintosh" in l:
        o="macOS"
    elif "linux" in l or "x11" in l:
        o="Linux"
    else:
        o=""
    br=""
    for key,name in (("edgios/","Edge"),("edga/","Edge"),("edg/","Edge"),("opr/","Opera"),("opios/","Opera"),("samsungbrowser/","Samsung Internet"),("fxios/","Firefox"),("firefox/","Firefox"),("crios/","Chrome"),("chrome/","Chrome"),("version/","Safari")):
        i=l.find(key)
        if i>=0:
            if name=="Safari" and "safari/" not in l:
                continue
            m=re.match(r"\d+",l[i+len(key):])
            br=name+(" "+m.group(0) if m else "")
            break
    if not br:
        if "curl/" in l:
            br="curl"
        elif ua:
            br=re.sub(r"[^A-Za-z0-9 ._/+-]","",ua.split(" ")[0])[:24]
    return dev,o,br
def log_login(ok,ip):
    try:
        now=int(time.time())
        c=db()
        c.execute("INSERT INTO login_log(ts,ok,ip) VALUES(?,?,?)",(now,1 if ok else 0,ip[:45]))
        c.execute("DELETE FROM login_log WHERE ts<?",(now-30*86400,))
        c.commit()
        c.close()
    except sqlite3.Error:
        pass
def create_session(sid,ip):
    now=int(time.time())
    dev,o,br=ua_info(request.headers.get("User-Agent",""))
    c=db()
    c.execute("DELETE FROM sessions WHERE created<? AND (ended>0 OR (exp>0 AND exp<?))",(now-30*86400,now))
    c.execute("INSERT INTO sessions(id,created,last,exp,ended,why,ip,dev,os,br) VALUES(?,?,?,?,0,'',?,?,?,?)",(sid,now,now,session_exp(),ip[:45],dev,o,br))
    c.commit()
    c.close()
def valid_session():
    sid=session.get("sid")
    sv=get("sess_ver","")
    if not (session.get("u") and sid and sv and hmac.compare_digest(str(session.get("sv","")),sv)):
        return False
    now=int(time.time())
    c=db()
    try:
        r=c.execute("SELECT exp,ended,last FROM sessions WHERE id=?",(str(sid),)).fetchone()
        if not r or r["ended"] or (r["exp"] and r["exp"]<=now):
            return False
        if now-r["last"]>=30:
            c.execute("UPDATE sessions SET last=? WHERE id=?",(now,str(sid)))
            c.commit()
    finally:
        c.close()
    return True
# ---- two-step verification (TOTP, RFC 6238: SHA-1, 6 digits, 30 s) ----
TOTP_PENDING={}
def totp_secret():
    return get("totp_secret","")
def totp_at(secret,counter):
    key=base64.b32decode(secret)
    h=hmac.new(key,struct.pack(">Q",counter),"sha1").digest()
    o=h[-1]&15
    return "%06d"%((struct.unpack(">I",h[o:o+4])[0]&0x7fffffff)%1000000)
def totp_verify(secret,code,last=0):
    code=re.sub(r"\s","",str(code or ""))
    if not re.fullmatch(r"[0-9]{6}",code):
        return None
    c=int(time.time()//30)
    hit=None
    for k in (-1,0,1):
        if hmac.compare_digest(totp_at(secret,c+k),code) and c+k>last:
            hit=c+k
    return hit
def code_check(code):
    """Second factor for sensitive actions. Returns '' when 2FA is off or the code is right."""
    sec=totp_secret()
    if not sec:
        return ""
    key="2fa:"+client_ip()
    if blocked(key):
        return "too_many"
    if totp_verify(sec,code) is None:
        fail(key)
        audit("2fa-check-failed")
        return "bad_code"
    FAILS.pop(key,None)
    return ""
def qr_uri(text):
    try:
        import segno
        buf=io.BytesIO()
        segno.make(text,error="m").save(buf,kind="svg",scale=5,border=2,dark="#000000",light="#ffffff",xmldecl=False)
        return "data:image/svg+xml;base64,"+base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""
def audit(ev,detail=""):
    try:
        ip=client_ip() if has_request_context() else "-"
        line="%s ip=%s %s %s"%(time.strftime("%Y-%m-%d %H:%M:%S%z"),re.sub(r"[^0-9A-Fa-f:.\-]","",ip)[:45] or "-",ev,re.sub(r"[\x00-\x1f\x7f]"," ",str(detail))[:200])
        try:
            if os.path.getsize(AUDIT)>10*1024*1024:
                os.replace(AUDIT,AUDIT+".1")
        except OSError:
            pass
        fd=os.open(AUDIT,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        with os.fdopen(fd,"a",encoding="utf-8") as f:
            f.write(line+"\n")
    except Exception:
        pass
def pw_check(pw):
    key="pw:"+client_ip()
    if blocked(key):
        return "too_many"
    if check_password_hash(get("admin_hash",""),pw):
        FAILS.pop(key,None)
        return ""
    fail(key)
    audit("password-check-failed")
    return "wrong_password"
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
def login_page(step=1,e="",code=200):
    return render_template("login.html",csrf=session["csrf"],err=e,version=VERSION,step=step),code
def finish_login(ip,u=""):
    FAILS.pop(ip,None)
    session.clear()
    session.permanent=True
    sid=secrets.token_hex(16)
    session["u"]=1
    session["sid"]=sid
    session["csrf"]=secrets.token_hex(16)
    session["sv"]=get("sess_ver","")
    create_session(sid,ip)
    log_login(True,ip)
    audit("login-ok",u[:32])
    return redirect("/")
@app.route("/login",methods=["GET","POST"])
def login():
    if not session.get("csrf"):
        session["csrf"]=secrets.token_hex(16)
    if request.method=="GET":
        session.pop("p2",None)
        return login_page()
    ip=client_ip()
    step2=request.form.get("step")=="2"
    if blocked(ip):
        return login_page(2 if step2 and session.get("p2") else 1,"too_many",429)
    if not hmac.compare_digest(request.form.get("csrf",""),session["csrf"]):
        return login_page(1,"session_expired",403)
    if step2:
        p=session.get("p2")
        sec=totp_secret()
        if not p or p.get("exp",0)<time.time() or not sec:
            session.pop("p2",None)
            return login_page(1,"session_expired",403)
        n=totp_verify(sec,request.form.get("code",""),int(get("totp_last","0") or 0))
        if n is None:
            fail(ip)
            log_login(False,ip)
            audit("login-2fa-failed")
            p["n"]=p.get("n",0)+1
            time.sleep(0.5)
            if p["n"]>=5:
                session.pop("p2",None)
                return login_page(1,"bad_code",401)
            session["p2"]=p
            return login_page(2,"bad_code",401)
        put("totp_last",n)
        session.pop("p2",None)
        return finish_login(ip,"2fa")
    u=request.form.get("username","")
    p=request.form.get("password","")
    ok_u=hmac.compare_digest(u.encode(),get("admin_user","").encode())
    ok_p=check_password_hash(get("admin_hash",""),p)
    if ok_u and ok_p:
        if totp_secret():
            session["p2"]={"exp":time.time()+300,"n":0}
            return login_page(2)
        return finish_login(ip,u)
    fail(ip)
    log_login(False,ip)
    audit("login-failed",u[:32])
    time.sleep(0.5)
    return login_page(1,"bad_login",401)
@app.get("/")
def index():
    if not valid_session():
        return redirect("/login")
    return render_template("index.html",csrf=session["csrf"],domain=get("domain",""),version=VERSION,tz=panel_tz())
@app.post("/api/logout")
@auth
def logout():
    audit("logout")
    end_sessions("logout",session.get("sid"))
    session.clear()
    return jsonify(ok=True)
@app.post("/api/password")
@auth
def change_password():
    d=request.get_json(silent=True) or {}
    old=str(d.get("old",""))
    new=str(d.get("new",""))
    e=pw_check(old) or code_check(d.get("code"))
    if e:
        return err(e,429 if e=="too_many" else 400)
    if len(new)<10 or len(new)>128:
        return err("short_password")
    put("admin_hash",generate_password_hash(new))
    rotate_sessions()
    audit("password-changed")
    session.clear()
    return jsonify(ok=True)
@app.get("/api/sessions")
@auth
def sessions_get():
    rng=request.args.get("range")
    span=7*86400 if rng=="7d" else 86400
    now=int(time.time())
    cut=now-span
    cur=session.get("sid")
    c=db()
    try:
        rows=c.execute("SELECT * FROM sessions WHERE created>=? OR last>=? OR (ended=0 AND (exp=0 OR exp>?)) ORDER BY created DESC LIMIT 200",(cut,cut,now)).fetchall()
        st=c.execute("SELECT SUM(ok=1) AS a,SUM(ok=0) AS b FROM login_log WHERE ts>=?",(cut,)).fetchone()
    finally:
        c.close()
    out=[]
    for r in rows:
        live=not r["ended"] and (not r["exp"] or r["exp"]>now)
        out.append({"id":r["id"],"created":r["created"],"last":r["last"],"exp":r["exp"],"ended":r["ended"],"why":r["why"] if r["ended"] else ("expired" if not live else ""),"live":live,"current":r["id"]==cur,"ip":r["ip"],"dev":r["dev"],"os":r["os"],"br":r["br"]})
    return jsonify(sessions=out,ok_n=int(st["a"] or 0),fail_n=int(st["b"] or 0),now=now,mode=sess_mode(),totp_on=bool(totp_secret()))
@app.post("/api/sessions/close")
@auth
def sessions_close():
    d=request.get_json(silent=True) or {}
    sid=str(d.get("id",""))
    if not re.fullmatch(r"[0-9a-f]{32}",sid):
        return err("bad_values")
    if not end_sessions("closed",sid):
        return err("not_found",404)
    audit("session-closed","current" if sid==session.get("sid") else "other")
    if sid==session.get("sid"):
        session.clear()
    return jsonify(ok=True)
@app.post("/api/sessions/clear")
@auth
def sessions_clear():
    c=db()
    try:
        n=c.execute("DELETE FROM sessions WHERE id!=?",(str(session.get("sid")),)).rowcount
        c.commit()
    finally:
        c.close()
    audit("sessions-cleared",str(n))
    return jsonify(ok=True,n=n)
@app.post("/api/2fa/setup")
@auth
def tfa_setup():
    if totp_secret():
        return err("tfa_on")
    sec=base64.b32encode(secrets.token_bytes(20)).decode()
    sid=session.get("sid")
    now=time.time()
    for k in [k for k,v in TOTP_PENDING.items() if v[1]<now]:
        TOTP_PENDING.pop(k,None)
    TOTP_PENDING[sid]=(sec,now+600)
    issuer="isile"+((" "+host()) if host() else "")
    label=quote(issuer+":"+get("admin_user","admin"))
    uri="otpauth://totp/%s?secret=%s&issuer=%s&algorithm=SHA1&digits=6&period=30"%(label,sec,quote(issuer))
    return jsonify(secret=sec,uri=uri,qr=qr_uri(uri))
@app.post("/api/2fa/enable")
@auth
def tfa_enable():
    d=request.get_json(silent=True) or {}
    p=TOTP_PENDING.get(session.get("sid"))
    if totp_secret():
        return err("tfa_on")
    if not p or p[1]<time.time():
        return err("session_expired")
    key="2fa:"+client_ip()
    if blocked(key):
        return err("too_many",429)
    n=totp_verify(p[0],d.get("code"))
    if n is None:
        fail(key)
        return err("bad_code")
    FAILS.pop(key,None)
    puts({"totp_secret":p[0],"totp_last":n})
    TOTP_PENDING.pop(session.get("sid"),None)
    audit("2fa-enabled")
    return jsonify(ok=True)
@app.post("/api/2fa/disable")
@auth
def tfa_disable():
    d=request.get_json(silent=True) or {}
    e=pw_check(str(d.get("password","")))
    if e:
        return err(e,429 if e=="too_many" else 400)
    c=db()
    c.execute("DELETE FROM settings WHERE k IN ('totp_secret','totp_last')")
    c.commit()
    c.close()
    audit("2fa-disabled")
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
    rows=[("ssh",ssh_port(),True,ls),("http",80,True,ls),("https",443,t,ls)]
    if not panel_domain_on():
        rows.append(("panel",panel_port(),True,ls))
    if comp_installed("udpcustom"):
        rows.append(("udp",udp_port(),comp_on("udpcustom"),listening_udp()))
    if comp_installed("vaydns") or comp_installed("slowdns"):
        v_on=comp_on("vaydns") and bool(vaydns_domain())
        s_on=comp_on("slowdns") and bool(slowdns_domain())
        lu=listening_udp()
        up=(v_on and VAYDNS_UDP in lu) or (s_on and SLOWDNS_UDP in lu)
        rows.append(("dns",VAYDNS_PORT,v_on or s_on,{VAYDNS_PORT} if up else set()))
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
    sv["vaydns"]=block_state("vaydns",off)
    sv["slowdns"]=block_state("slowdns",off)
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
CF_NETS=['173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22', '141.101.64.0/18', '108.162.192.0/18', '190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22', '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13', '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22']
CF_HTTPS_PORTS=(443,2053,2083,2087,2096,8443)
def is_cf(ips):
    """True when any of the addresses belongs to Cloudflare (the domain is behind its orange-cloud proxy)."""
    import ipaddress
    nets=[ipaddress.ip_network(n) for n in CF_NETS]
    for a in ips:
        try:
            if any(ipaddress.ip_address(a) in n for n in nets):
                return True
        except ValueError:
            pass
    return False
def dns_of(dom):
    try:
        return sorted({a[4][0] for a in socket.getaddrinfo(dom,None,socket.AF_INET)})
    except (socket.gaierror,UnicodeError):
        return []
@app.get("/api/settings")
@auth
def settings_get():
    s=gets("cap_gb","cap_basis")
    o={"domain":get("domain",""),"panel_domain":panel_domain(),"panel_domain_on":panel_domain_on(),"server_ip":get("server_ip",""),"tls_on":tls_on(),"public_page":public_on(),"public_token":token_mode(),"banner":get("banner",DEFAULT_BANNER),"banner_on":get("banner_on","1")=="1","banner_default":DEFAULT_BANNER,"decoy_on":get("decoy_on","0")=="1","decoy_url":get("decoy_url",""),"tz":panel_tz(),"tz_region":tz_region(),"tz_utc":get("tz_utc","0")=="1","tz_list":tz_list(),"totp_on":bool(totp_secret()),"sess_mode":sess_mode()}
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
    if "sess_mode" in d:
        if d["sess_mode"] not in SESS_MODES:
            return err("bad_values")
        upd["sess_mode"]=d["sess_mode"]
    if "public_page" in d:
        upd["public_page"]="1" if d["public_page"] else "0"
    if "public_token" in d:
        upd["public_token"]="1" if d["public_token"] else "0"
    dy={}
    if "decoy_on" in d:
        dy["decoy_on"]="1" if d["decoy_on"] else "0"
    if "decoy_url" in d:
        u=str(d["decoy_url"] or "").strip()
        if u and (len(u)>DECOY_MAX or not DECOY_RE.fullmatch(u)):
            return err("bad_decoy_url")
        dy["decoy_url"]=u
    if "banner" in d or "banner_on" in d:
        on=bool(d["banner_on"]) if "banner_on" in d else get("banner_on","1")=="1"
        txt=clean_banner(d["banner"]) if "banner" in d else get("banner",DEFAULT_BANNER)
        if txt is None:
            return err("bad_values")
        e=apply_banner(txt if on else "")
        if e:
            return err("system",400,e)
        upd["banner"]=txt
        upd["banner_on"]="1" if on else "0"
    if upd:
        puts(upd)
        audit("settings",",".join(sorted(upd)))
    if dy:
        old={k:get(k,"") for k in dy}
        puts(dy)
        e=decoy_apply()
        if e:
            puts(old)
            decoy_apply()
            return err("system",400,e)
    return jsonify(ok=True)
def decoy_apply():
    """Re-render the nginx config (it reads decoy_on / decoy_url from the database) and reload nginx."""
    try:
        r=sh(["bash",BASE+"/setdomain.sh","--render",get("domain","")])
        if r.returncode:
            return ((r.stderr or r.stdout or "nginx").strip()[-300:])
        r=sh(["systemctl","reload","nginx"])
        if r.returncode:
            return ((r.stderr or r.stdout or "nginx reload").strip()[-300:])
    except Exception as e:
        return str(e)[:300]
    return ""
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
def banner_boot():
    on=get("banner_on","1")=="1"
    txt=get("banner",DEFAULT_BANNER) if on else ""
    try:
        if txt:
            with open(BANNER_TXT,encoding="utf-8") as f:
                same=f.read()==txt+"\n" and os.path.exists(BANNER_CONF)
        else:
            same=not os.path.exists(BANNER_CONF)
    except OSError:
        same=False
    if not same:
        apply_banner(txt)
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
        elif k in ("udpcustom","vaydns","slowdns"):
            if comp_installed(k):
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
def archive_log(k,src):
    try:
        if os.path.getsize(src)==0:
            return ""
        os.makedirs(ARCH,mode=0o700,exist_ok=True)
        os.chmod(ARCH,0o700)
        dst="%s/%s-%s.log.gz"%(ARCH,k,time.strftime("%Y%m%d-%H%M%S"))
        with open(src,"rb") as a,gzip.open(dst,"wb",compresslevel=6) as b:
            shutil.copyfileobj(a,b)
        os.chmod(dst,0o600)
        for p in sorted(glob.glob("%s/%s-*.log.gz"%(ARCH,k)))[:-ARCH_KEEP]:
            os.unlink(p)
    except OSError as e:
        return str(e)
    return ""
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
        ae=archive_log(k,src)
        audit("log-clear",k+(" (archive failed: %s)"%ae if ae else " (archived)"))
        try:
            open(src,"w").close()
        except OSError as e:
            return err("system",500,str(e))
    else:
        audit("log-clear",k+" (journal hidden from panel only)")
        put("logclr_"+k,int(time.time()))
    return jsonify(ok=True)
@app.get("/api/domain")
@auth
def domain_get():
    cur=get("domain","")
    cand=str(request.args.get("d","")).strip().lower() or cur
    if cand and not DOMAIN_RE.fullmatch(cand):
        return err("bad_domain")
    ip=get("server_ip","")
    dns=dns_of(cand) if cand else []
    pp=panel_port()
    pcur=panel_domain()
    pcand=str(request.args.get("p","")).strip().lower() or pcur
    if pcand and not DOMAIN_RE.fullmatch(pcand):
        return err("bad_domain")
    pdns=dns_of(pcand) if pcand else []
    pd=dict(domain=pcur,on=panel_domain_on(),candidate=pcand,dns=pdns,match=bool(ip and ip in pdns),cf=is_cf(pdns),cert=cert_info(pcand))
    return jsonify(domain=cur,candidate=cand,server_ip=ip,dns=dns,match=bool(ip and ip in dns),cert=cert_info(cand),cf=is_cf(dns),panel_port=pp,cf_port_ok=pp in CF_HTTPS_PORTS,pd=pd)
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
    if not DOMAIN_RE.fullmatch(dom):
        return err("bad_domain")
    if email and not EMAIL_RE.fullmatch(email):
        return err("bad_email")
    if dom in (vaydns_domain(),slowdns_domain(),panel_domain()):
        return err("domain_same")
    if job_busy():
        return err("busy",409)
    audit("domain-set",dom)
    e=start_job("domain","bash %s/setdomain.sh %s %s"%(BASE,shq(dom),shq(email)))
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
@app.post("/api/panel-domain")
@auth
def panel_domain_set():
    """Set (or clear with an empty value) the panel subdomain. Issues its own certificate and moves the panel from the port to 443."""
    d=request.get_json(silent=True) or {}
    dom=str(d.get("domain","")).strip().lower()
    email=str(d.get("email","")).strip()
    if job_busy():
        return err("busy",409)
    if not dom:
        if not panel_domain():
            return jsonify(ok=True)
        audit("panel-domain-off",panel_domain())
        e=start_job("paneldomain","bash %s/setdomain.sh --panel-off"%shq(BASE))
        if e:
            return err("system",500,e)
        return jsonify(ok=True)
    if not DOMAIN_RE.fullmatch(dom):
        return err("bad_domain")
    if email and not EMAIL_RE.fullmatch(email):
        return err("bad_email")
    if not tls_on():
        return err("pd_need_domain")
    if dom==get("domain","") or under_tunnel(dom):
        return err("pd_same")
    audit("panel-domain-set",dom)
    e=start_job("paneldomain","bash %s/setdomain.sh --panel %s %s"%(shq(BASE),shq(dom),shq(email)))
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
def port_problem(p):
    """Returns the error code explaining why p cannot be the panel port, or '' when it can."""
    if not isinstance(p,int) or not 1024<=p<=65535:
        return "bad_port"
    if p==panel_port():
        return "port_same"
    if p==ssh_port():
        return "port_ssh"
    if 10000<=p<=10299 or p in (8000,7000,7001,5300,5301,5302,36712):
        return "port_reserved"
    sk=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        sk.bind(("0.0.0.0",p))
    except OSError:
        return "port_used"
    finally:
        sk.close()
    return ""
@app.post("/api/panel-port")
@auth
def panel_port_set():
    d=request.get_json(silent=True) or {}
    try:
        p=int(str(d.get("port","")).strip())
    except ValueError:
        return err("bad_port")
    if panel_domain_on():
        return err("pd_active")
    e=port_problem(p)
    if e:
        return err(e)
    audit("panel-port",str(p))
    e=start_job("port",": > %s; /usr/local/bin/isile port %d >>%s 2>&1"%(LOGF,p,LOGF))
    if e:
        return err("system",500,e)
    return jsonify(ok=True,port=p)
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
    if not re.fullmatch(r"^[0-9A-Za-z .+_-]{1,32}$",v):
        return err("unavailable",502)
    return jsonify(latest=v)
@app.post("/api/system/restart")
@auth
def sys_restart():
    us=[u for c,u in (("xray","xray"),("wsbridge","vpnbridge"),("udpcustom","udp-custom"),("vaydns","vaydns"),("slowdns","slowdns")) if comp_on(c) and (c!="vaydns" or vaydns_domain()) and (c!="slowdns" or slowdns_domain())]+["nginx","vpnmux"]
    audit("system-restart")
    e=start_job("restart","sleep 1; systemctl restart %s; if [ -s /etc/vpnpanel/stunnel.conf ]; then systemctl restart vpnstunnel; fi; systemctl restart vpnpanel"%" ".join(us))
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
@app.post("/api/system/update")
@auth
def sys_update():
    audit("system-update")
    e=start_job("update","/usr/local/bin/isile update")
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
@app.post("/api/system/uninstall")
@auth
def sys_uninstall():
    d=request.get_json(silent=True) or {}
    e=pw_check(str(d.get("password",""))) or code_check(d.get("code"))
    if e:
        return err(e,429 if e=="too_many" else 400)
    audit("system-uninstall")
    e=start_job("uninstall","/usr/local/bin/isile uninstall --yes")
    if e:
        return err("system",500,e)
    return jsonify(ok=True)
def do_reset():
    """Delete every account and reset usage and settings. Returns '' or an error text."""
    with LOCK:
        c=db()
        try:
            for r in c.execute("SELECT name,proto FROM accounts").fetchall():
                if r["proto"]=="ssh":
                    ssh_del(r["name"])
            c.execute("DELETE FROM accounts")
            c.execute("DELETE FROM daily")
            c.execute("DELETE FROM settings WHERE k IN ('cap_gb','cap_basis','public_page','public_token','banner','banner_on')")
            c.commit()
            puts({"m_rx":0,"m_tx":0,"m_off":0})
            apply_banner(DEFAULT_BANNER)
            nft_apply(c)
            xray_sync(c)
        except Exception as e:
            traceback.print_exc()
            return str(e)[-300:] or "error"
        finally:
            c.close()
        for m in (CONN,ACTIVE,SPEED,SP_B,SSH_OVER):
            m.clear()
    return ""
@app.post("/api/system/reset")
@auth
def sys_reset():
    d=request.get_json(silent=True) or {}
    e=pw_check(str(d.get("password",""))) or code_check(d.get("code"))
    if e:
        return err(e,429 if e=="too_many" else 400)
    audit("system-reset")
    e=do_reset()
    if e:
        return err("system",500,e)
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
    q={"xray":"proto IN ('vless','vmess','trojan')","wsbridge":"proto='ssh' AND transport='ws'","udpcustom":"proto='ssh' AND transport='udp'","vaydns":"transport='dns'","slowdns":"transport='slowdns'"}.get(comp)
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
            if k=="vaydns":
                o["domain"]=vaydns_domain()
                o["pubkey"]=vaydns_pub()
                o["port"]=VAYDNS_PORT
                o["server_ip"]=get("server_ip","")
                o["info"]=vaydns_info()
            if k=="slowdns":
                o["domain"]=slowdns_domain()
                o["pubkey"]=slowdns_pub()
                o["port"]=VAYDNS_PORT
                o["server_ip"]=get("server_ip","")
                o["info"]=slowdns_info()
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
@app.post("/api/vaydns/config")
@auth
def vaydns_config():
    d=request.get_json(silent=True) or {}
    dom=str(d.get("domain","")).strip().lower()
    if dom and not DOMAIN_RE.fullmatch(dom):
        return err("bad_domain")
    if dom and (dom in (get("domain",""),slowdns_domain(),panel_domain()) or (panel_domain() and panel_domain().endswith("."+dom))):
        return err("domain_same")
    if not comp_installed("vaydns"):
        return err("not_found",404)
    with LOCK:
        put("vaydns_domain",dom)
        c=db()
        try:
            apply_components(c)
        finally:
            c.close()
    return jsonify(ok=True)
@app.post("/api/slowdns/config")
@auth
def slowdns_config():
    d=request.get_json(silent=True) or {}
    dom=str(d.get("domain","")).strip().lower()
    if dom and not DOMAIN_RE.fullmatch(dom):
        return err("bad_domain")
    if dom and (dom in (get("domain",""),vaydns_domain(),panel_domain()) or (panel_domain() and panel_domain().endswith("."+dom))):
        return err("domain_same")
    if not comp_installed("slowdns"):
        return err("not_found",404)
    with LOCK:
        put("slowdns_domain",dom)
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
    if comp in ("xray","vaydns","slowdns") and action=="install":
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
        o={k:r[k] for k in ("name","proto","status","manual","created","expires","quota","up","down","note","tls","transport","public")}
        cn=CONN.get(r["name"],{})
        o["conn"]=cn.get("n",0)
        o["conn_limit"]=r["conn_limit"]
        o["active"]=is_live(r["name"],r["proto"],r["status"],o["conn"])
        o["sp_up"],o["sp_down"]=speed_of(r["name"]) if o["active"] else (0,0)
        rows.append(o)
    c.close()
    return jsonify(rows)
def dns_head():
    td=vaydns_domain()
    pub=vaydns_pub()
    ip=get("server_ip","") or host()
    return [{"k":"dns_domain","value":td or "-","rows":1},{"k":"dns_pubkey","value":pub or "-","rows":2},{"k":"dns_cmd","value":"vaydns-client -udp %s:%d -pubkey %s -domain %s -listen 127.0.0.1:%d"%(ip,VAYDNS_PORT,pub or "PUBKEY",td or "DOMAIN",VAYDNS_LOCAL),"rows":4}]
def slowdns_head():
    td=slowdns_domain()
    pub=slowdns_pub()
    ip=get("server_ip","") or host()
    return [{"k":"dns_domain","value":td or "-","rows":1},{"k":"dns_pubkey","value":pub or "-","rows":2},{"k":"sdns_cmd","value":"dnstt-client -udp %s:%d -pubkey %s %s 127.0.0.1:%d"%(ip,VAYDNS_PORT,pub or "PUBKEY",td or "DOMAIN",SLOWDNS_LOCAL),"rows":4}]
def vmess_link(n,s,dom,tls,grpc=False,dns=False,xhttp=False):
    o={"v":"2","ps":n+("-DNS" if dns else "")+("-TLS" if tls else "-80"),"add":"127.0.0.1" if dns else dom,"port":str(VAYDNS_LOCAL) if dns else "443" if tls else "80","id":s,"aid":"0","scy":"auto","net":"grpc" if grpc else "xhttp" if xhttp else "ws","type":"gun" if grpc else "auto" if xhttp else "none","host":"" if grpc else dom,"path":"vmess-grpc" if grpc else "/vmess-xhttp" if xhttp else "/vmess","tls":"tls" if tls else "","sni":dom if tls else "","alpn":"h2" if (grpc or xhttp) and tls else ""}
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
    elif p=="ssh" and r["transport"]=="dns":
        items=dns_head()
        items.append({"k":"dns_ssh","value":"127.0.0.1:%d@%s:%s"%(VAYDNS_LOCAL,n,s),"rows":2})
        if t_on:
            items.append({"k":"sni","value":dom,"rows":1})
        items+=[{"k":"user","value":n,"rows":1},{"k":"pass","value":s,"rows":1}]
    elif p=="ssh" and r["transport"]=="slowdns":
        items=slowdns_head()
        items.append({"k":"sdns_ssh","value":"127.0.0.1:%d@%s:%s"%(SLOWDNS_LOCAL,n,s),"rows":2})
        if t_on:
            items.append({"k":"sni","value":dom,"rows":1})
        items+=[{"k":"user","value":n,"rows":1},{"k":"pass","value":s,"rows":1}]
    elif p=="ssh" and r["transport"]=="direct":
        items=[{"k":"direct_addr","value":"%s:%d@%s:%s"%(dom,ssh_port(),n,s),"rows":2},{"k":"user","value":n,"rows":1},{"k":"pass","value":s,"rows":1}]
    elif p=="ssh" and r["transport"]=="ssl":
        if t_on:
            items.append({"k":"ssl_tls","value":"%s:443@%s:%s"%(dom,n,s),"rows":2})
            items.append({"k":"sni","value":dom,"rows":1})
        items+=[{"k":"user","value":n,"rows":1},{"k":"pass","value":s,"rows":1}]
    elif p=="ssh":
        items=[{"k":"payload","value":"GET / HTTP/1.1[crlf]Host: %s[crlf]Upgrade: websocket[crlf][crlf]"%dom,"rows":3},{"k":"user","value":n,"rows":1},{"k":"pass","value":s,"rows":1}]
        if r["tls"] in ("plain","both"):
            items.insert(0,{"k":"ssh_plain","value":"%s:80@%s:%s"%(dom,n,s),"rows":2})
        if t_on and r["tls"] in ("tls","both"):
            items.insert(0,{"k":"ssh_tls","value":"%s:443@%s:%s"%(dom,n,s),"rows":2})
    else:
        dns=r["transport"]=="dns"
        if dns:
            items=dns_head()
        for m in (MODES if r["tls"]=="both" else (r["tls"],)):
            tls=m=="tls"
            if tls and not t_on:
                continue
            grpc=r["transport"]=="grpc"
            xhttp=r["transport"]=="xhttp"
            tail=h+("-DNS" if dns else "")+("-TLS" if tls else "-80")
            addr="127.0.0.1" if dns else dom
            port=VAYDNS_LOCAL if dns else 443 if tls else 80
            sec="sni=%s&fp=chrome&%s"%(dom,"alpn=h2&" if (grpc or xhttp) else "") if tls else ""
            if grpc:
                net="type=grpc&serviceName=%s-grpc&mode=gun"%p
            elif xhttp:
                net="type=xhttp&host=%s&path=%%2F%s-xhttp&mode=auto"%(dom,p)
            else:
                net="type=ws&host=%s&path=%%2F%s"%(dom,p)
            if p=="vmess":
                v=vmess_link(n,s,dom,tls,grpc,dns,xhttp)
            elif p=="vless":
                v="vless://%s@%s:%d?encryption=none&security=%s&%s%s#%s"%(s,addr,port,"tls" if tls else "none",sec,net,tail)
            else:
                v="trojan://%s@%s:%d?security=%s&%s%s#%s"%(quote(s,safe=""),addr,port,"tls" if tls else "none",sec,net,tail)
            items.append({"k":("dns_link_" if dns else "link_")+("tls" if tls else "plain"),"value":v,"rows":4})
        items.append({"k":"pass" if p=="trojan" else "uuid","value":s,"rows":1})
        if r["transport"]=="grpc":
            items.append({"k":"grpc_service","value":p+"-grpc","rows":1})
        if r["transport"]=="xhttp":
            items.append({"k":"xhttp_path","value":"/"+p+"-xhttp","rows":1})
    if public_on() or r["public"]:
        items.insert(0,{"k":"page","value":page_url(r["ptoken"] if token_mode() else n),"rows":1})
    cn=CONN.get(n,{})
    act=is_live(n,r["proto"],r["status"],cn.get("n",0))
    spu,spd=speed_of(n) if act else (0,0)
    return jsonify(conn=cn.get("n",0),conn_limit=r["conn_limit"],items=items,active=act,sp_up=spu,sp_down=spd,status=r["status"],up=r["up"],down=r["down"],quota=r["quota"],created=r["created"],expires=r["expires"],proto=p,transport=r["transport"],tls=r["tls"],tls_on=t_on,host=dom,server_ip=get("server_ip",""),note=r["note"],dns_ok=bool(slowdns_domain() and slowdns_pub()) if r["transport"]=="slowdns" else bool(vaydns_domain() and vaydns_pub()))
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
    if not NAME_RE.fullmatch(name):
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
    if proto!="ssh" and transport=="slowdns":
        return err("bad_values")
    if proto!="ssh":
        transport=transport if transport in ("grpc","xhttp","dns") else "ws"
    elif transport in ("grpc","xhttp"):
        return err("bad_values")
    if transport in ("udp","direct") or (proto=="ssh" and transport in ("dns","slowdns")):
        tls="plain"
    elif transport=="ssl":
        tls="tls"
        if not tls_on():
            return err("combo_disabled",400,"sshssl:tls")
    dk=keys_denied(acct_keys(proto,transport,tls))
    if dk:
        return err("combo_disabled",400,dk)
    sec=str(d.get("secret") or "").strip()
    if proto in ("vless","vmess"):
        sec=sec.lower() or str(uuid.uuid4())
        if not UUID_RE.fullmatch(sec):
            return err("bad_uuid")
    else:
        sec=sec or gen_pass()
        if not SECRET_RE.fullmatch(sec):
            return err("bad_secret")
    note=str(d.get("note") or "")[:100]
    pub=1 if d.get("public") else 0
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
            c.execute("INSERT INTO accounts(name,proto,secret,uid,created,expires,quota,note,status,tls,transport,conn_limit,public,ptoken) VALUES(?,?,?,?,?,?,?,?,'active',?,?,?,?,?)",(name,proto,sec,uid,now,pc["expires"],pc["quota"],note,tls,transport,pc["conn_limit"],pub,new_token()))
            c.commit()
            audit("account-create","%s %s"%(name,proto))
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
                    if not UUID_RE.fullmatch(sec):
                        return err("bad_uuid")
                elif not SECRET_RE.fullmatch(sec):
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
                okt=V2NETS+("dns",) if r["proto"]!="ssh" else ("ws","ssl","direct","udp","dns","slowdns")
                if d["transport"] not in okt:
                    return err("bad_values")
                sets["transport"]=d["transport"]
            ntr=sets.get("transport",r["transport"])
            if r["proto"]=="ssh" and ntr in ("udp","direct","dns","slowdns"):
                sets["tls"]="plain"
            elif r["proto"]=="ssh" and ntr=="ssl":
                sets["tls"]="tls"
                if ntr!=r["transport"] and not tls_on():
                    return err("combo_disabled",400,"sshssl:tls")
            ntls=sets.get("tls",r["tls"])
            if (ntls,ntr)!=(r["tls"],r["transport"]):
                dk=keys_denied(acct_keys(r["proto"],ntr,ntls))
                if dk:
                    return err("combo_disabled",400,dk)
            if "note" in d:
                sets["note"]=str(d.get("note") or "")[:100]
            if "manual" in d:
                sets["manual"]=1 if d["manual"] else 0
            if "public" in d:
                sets["public"]=1 if d["public"] else 0
            if d.get("reset"):
                sets["up"]=0
                sets["down"]=0
            if sets:
                c.execute("UPDATE accounts SET "+",".join(k+"=?" for k in sets)+" WHERE name=?",list(sets.values())+[name])
                c.commit()
            if sets:
                audit("account-edit","%s %s"%(name,",".join(k for k in sorted(sets) if k not in ("up","down"))))
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
            audit("account-delete",name)
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
            if re.fullmatch(r"^[A-Z]{2}$",cc):
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
    r=public_row(name)
    if not r:
        return err("not_found",404)
    name=r["name"]
    cn=CONN.get(name,{})
    act=is_live(name,r["proto"],r["status"],cn.get("n",0))
    spu,spd=speed_of(name) if act else (0,0)
    return jsonify(conn=cn.get("n",0),conn_limit=r["conn_limit"],name=r["name"],proto=r["proto"],transport=r["transport"],tls=r["tls"],status=r["status"],active=act,up=r["up"],down=r["down"],quota=r["quota"],created=r["created"],expires=r["expires"],sp_up=spu,sp_down=spd,now=int(time.time()),cc=server_cc())
@app.get("/<name>")
def public_page(name):
    name=name.lower()
    if name in RESERVED or not public_row(name):
        return "Not found",404
    return render_template("public.html",name=name,version=VERSION,tz=panel_tz())
def main():
    cmd=sys.argv[1] if len(sys.argv)>1 else "serve"
    init_db()
    if cmd=="setup":
        put("admin_user",os.environ["VPN_ADMIN_USER"])
        put("admin_hash",generate_password_hash(os.environ["VPN_ADMIN_PASS"]))
        puts({"domain":os.environ.get("VPN_DOMAIN",""),"server_ip":os.environ.get("VPN_SERVER_IP","")})
        pdv=os.environ.get("VPN_PANEL_DOMAIN","").strip().lower()
        if pdv and DOMAIN_RE.fullmatch(pdv) and os.environ.get("VPN_DOMAIN","") and pdv!=os.environ.get("VPN_DOMAIN",""):
            put("panel_domain",pdv)
        if re.fullmatch(r"[0-9]{4,5}",os.environ.get("VPN_PANEL_PORT","")) and 1024<=int(os.environ["VPN_PANEL_PORT"])<=65535:
            put("port_panel",os.environ["VPN_PANEL_PORT"])
        c=db()
        write_xray_conf(c)
        c.close()
        return
    if cmd=="setadmin":
        if os.environ.get("VPN_ADMIN_USER"):
            put("admin_user",os.environ["VPN_ADMIN_USER"])
        if os.environ.get("VPN_ADMIN_PASS"):
            put("admin_hash",generate_password_hash(os.environ["VPN_ADMIN_PASS"]))
        if os.environ.get("VPN_ADMIN_USER") or os.environ.get("VPN_ADMIN_PASS"):
            rotate_sessions()
        return
    if cmd=="rm2fa":
        c=db()
        c.execute("DELETE FROM settings WHERE k IN ('totp_secret','totp_last')")
        c.commit()
        c.close()
        audit("2fa-disabled-terminal")
        return
    if cmd=="tfa-gen":
        sec=base64.b32encode(secrets.token_bytes(20)).decode()
        issuer="isile"+((" "+host()) if host() else "")
        print(sec)
        print("otpauth://totp/%s?secret=%s&issuer=%s&algorithm=SHA1&digits=6&period=30"%(quote(issuer+":"+get("admin_user","admin")),sec,quote(issuer)))
        return
    if cmd=="tfa-on":
        sec=os.environ.get("TFA_SECRET","")
        if not re.fullmatch(r"[A-Z2-7]{32}",sec):
            sys.exit(2)
        n=totp_verify(sec,os.environ.get("TFA_CODE",""))
        if n is None:
            sys.exit(1)
        puts({"totp_secret":sec,"totp_last":n})
        audit("2fa-enabled-terminal")
        return
    if cmd=="cfip":
        sys.exit(0 if is_cf(sys.argv[2:]) else 1)
    if cmd=="comps":
        c=db()
        try:
            for k in REMOVABLE:
                print(k,int(comp_installed(k)),block_state(k),comp_accounts(c,k))
        finally:
            c.close()
        return
    if cmd=="combos-on":
        k=sys.argv[2] if len(sys.argv)>2 else ""
        if k not in REMOVABLE:
            sys.exit(2)
        put("combos_off",",".join(sorted(combos_off()-set(comp_combos(k)))))
        return
    if cmd=="reset":
        e=do_reset()
        if e:
            print(e,file=sys.stderr)
            sys.exit(1)
        audit("system-reset-terminal")
        return
    if cmd=="setselfsigned":
        put("selfsigned","1")
        return
    if cmd=="setserver":
        if os.environ.get("VPN_SERVER_IP"):
            put("server_ip",os.environ["VPN_SERVER_IP"])
        return
    if cmd=="setdomain":
        put("domain",os.environ["VPN_DOMAIN"])
        return
    if cmd=="setpaneldomain":
        v=os.environ.get("VPN_PANEL_DOMAIN","").strip().lower()
        if v and not DOMAIN_RE.fullmatch(v):
            sys.exit(2)
        put("panel_domain",v)
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
    app.config.update(SECRET_KEY=get("secret_key"),SESSION_COOKIE_NAME="vpnsid",SESSION_COOKIE_SECURE=panel_https(),SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Strict",MAX_CONTENT_LENGTH=65536,PERMANENT_SESSION_LIFETIME=timedelta(days=360))
    with LOCK:
        c=db()
        nft_apply(c)
        reconcile(c)
        try:
            apply_components(c)
        except Exception:
            traceback.print_exc()
        try:
            banner_boot()
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
