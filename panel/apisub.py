"""isile 1.9.7: API links and subscription links.

An API link is  <panel url>/<32 hex hash>  and returns the configs picked for it as JSON (a private VPN app can poll it).
A subscription link is  <panel url>/<32 hex hash>  per account and returns that account's configs as a base64 list of
share links (the usual subscription format of HTTP Custom, NetMod, v2rayNG...).

A "config" is one account plus the client-side settings chosen in the panel (TLS, payload, remote proxy, SNI, DNS options...).
Several configs can be made from the same account, and each one is delivered through the API, the subscription, both or none.
Only the values the admin changed are stored: everything else follows the panel (domain, ports, keys), so it stays correct later.

This file owns the tables, the admin endpoints (/api/apicfg/...) and the public hash endpoint. app.py only calls setup(globals())
once and a few small hooks (hash lookup, account info, account delete, reset).
"""
import re,json,time,base64,secrets
from urllib.parse import quote
from flask import request,jsonify,Response

A=None  # the namespace of app.py (set by setup)
class _NS:
    def __init__(s,g):
        s.__dict__["_g"]=g
    def __getattr__(s,k):
        try:
            return s._g[k]
        except KeyError:
            raise AttributeError(k)
HASH_RE=re.compile(r"^[0-9a-f]{32}$")
ID_RE=re.compile(r"^[0-9a-f]{10}$")
DELIVERY=("none","api","sub","both")
MISS={}  # ip -> [misses, last]: unknown hashes are throttled
TLSV=["Auto","TLSv1.0","TLSv1.1","TLSv1.2","TLSv1.3"]
FPS=["chrome","firefox","safari","ios","android","edge","360","qq","random","randomized",""]
NETS=["ws","grpc","xhttp","httpupgrade","tcp"]
DNS_TR=["udp","dot","doh"]
DNS_REC=["","txt","cname","null","a","aaaa","mx","ns","srv","caa"]
DNS_LOG=["","debug","info","warning","error"]
VMESS_SCY=["auto","aes-128-gcm","chacha20-poly1305","none","zero"]
FLOWS=["","xtls-rprx-vision"]
DEFAULT_PAYLOAD="GET / HTTP/1.1[crlf]Host: [host][crlf]Upgrade: websocket[crlf][crlf]"
# every field of the app's Profile with its default (Profile.kt), so the JSON can be read by Profile.fromJson
PROFILE={"uid":"","name":"","kind":"SSH","host":"","port":22,"user":"","pass":"","payloadOn":False,"payload":DEFAULT_PAYLOAD,"proxyHost":"","proxyPort":8080,
"secret":"","ws":False,"wsPath":"/","wsHost":"","tls":False,"sni":"","tlsVersion":"Auto","fingerprint":"chrome","alpn":"","insecure":False,"mux":False,
"network":"tcp","security":"","flow":"","pbk":"","sid":"","spx":"","alterId":0,"vmessScy":"auto","encryption":"none","serviceName":"",
"dns":"","dnsResolver":"8.8.8.8:53","dnsPubkey":"","dnsRecord":"","dnsCompat":False,"dnsListen":"","dnsTransport":"udp","forward":"socks5","auth":False,
"dnsIdle":"","dnsKeepalive":"","dnsUdpTimeout":"","dnsOpenStream":"","dnsWorkers":"","dnsRps":"","dnsMaxQname":"","dnsMaxLabels":"","dnsClientId":"",
"dnsUtls":"","dnsLogLevel":"","dnsExtra":"","locked":False}
# ---- which settings each kind of account can change (k, type, group, extra) ----
def _f(k,t,g,**x):
    o={"k":k,"t":t,"g":g}
    o.update(x)
    return o
TLS_F=[_f("tls","bool","tls"),_f("sni","text","tls",when={"tls":[True]}),_f("tlsVersion","select","tls",opts=TLSV,when={"tls":[True]}),_f("insecure","bool","tls",when={"tls":[True]})]
FIELDS_SSH=[_f("host","text","conn"),_f("port","int","conn",lo=1,hi=65535),
_f("ws","bool","ws"),_f("wsPath","text","ws",when={"ws":[True]}),_f("wsHost","text","ws",when={"ws":[True]}),
_f("payloadOn","bool","payload"),_f("payload","area","payload",mx=1500,when={"payloadOn":[True]}),
_f("proxyHost","text","payload"),_f("proxyPort","int","payload",lo=1,hi=65535)]+TLS_F
FIELDS_VAY=[_f("host","text","conn"),
_f("dnsTransport","select","dns",opts=DNS_TR),_f("dnsResolver","text","dns"),_f("dnsRecord","select","dns",opts=DNS_REC),_f("dnsListen","text","dns"),_f("dnsCompat","bool","dns")]+TLS_F+[
_f("dnsIdle","int","dnsadv",lo=1,hi=86400),_f("dnsKeepalive","int","dnsadv",lo=1,hi=86400),_f("dnsUdpTimeout","int","dnsadv",lo=1,hi=600000),
_f("dnsOpenStream","int","dnsadv",lo=1,hi=86400),_f("dnsWorkers","int","dnsadv",lo=1,hi=10000),_f("dnsRps","int","dnsadv",lo=0,hi=1000000),
_f("dnsMaxQname","int","dnsadv",lo=1,hi=253),_f("dnsMaxLabels","int","dnsadv",lo=1,hi=253),_f("dnsClientId","int","dnsadv",lo=1,hi=64),
_f("dnsUtls","text","dnsadv",mx=40),_f("dnsLogLevel","select","dnsadv",opts=DNS_LOG),_f("dnsExtra","text","dnsadv",mx=200)]
FIELDS_SLOW=[_f("host","text","conn"),_f("dnsResolver","text","dns"),_f("dnsListen","text","dns")]+TLS_F
_WSLIKE=["ws","xhttp","httpupgrade"]
FIELDS_V2=[_f("host","text","conn"),_f("port","int","conn",lo=1,hi=65535),_f("network","select","net",opts=NETS),
_f("wsPath","text","net",when={"network":_WSLIKE}),_f("wsHost","text","net",when={"network":_WSLIKE}),_f("serviceName","text","net",when={"network":["grpc"]}),
_f("mux","bool","net")]+[
_f("tls","bool","tls"),_f("sni","text","tls",when={"tls":[True]}),_f("fingerprint","select","tls",opts=FPS,when={"tls":[True]}),_f("alpn","text","tls",mx=60,when={"tls":[True]}),_f("insecure","bool","tls",when={"tls":[True]})]
FIELDS_V2_VLESS=[_f("flow","select","adv",opts=FLOWS),_f("encryption","text","adv",mx=20)]
FIELDS_V2_VMESS=[_f("alterId","int","adv",lo=0,hi=64),_f("vmessScy","select","adv",opts=VMESS_SCY)]
COMMON=[_f("label","text","id",mx=40),_f("locked","bool","id")]
def setup(g):
    global A
    A=_NS(g)
    init_tables()
    app=A.app
    def route(path,fn,methods):
        app.add_url_rule(path,"apisub_"+fn.__name__,A.auth(fn),methods=methods)
    route("/api/apicfg",admin_get,["GET"])
    route("/api/apicfg/settings",admin_settings,["POST"])
    route("/api/apicfg/keys",key_new,["POST"])
    route("/api/apicfg/keys/<kid>",key_edit,["PATCH"])
    route("/api/apicfg/keys/<kid>/delete",key_del,["POST"])
    route("/api/apicfg/fields/<account>",fields_get,["GET"])
    route("/api/apicfg/preview",preview,["POST"])
    route("/api/apicfg/configs",cfg_new,["POST"])
    route("/api/apicfg/configs/<cid>",cfg_edit,["PATCH"])
    route("/api/apicfg/configs/<cid>/delete",cfg_del,["POST"])
    route("/api/apicfg/sub/<account>",sub_get,["GET"])
    route("/api/apicfg/sub/<account>",sub_set,["PUT"])
# ---------------- storage ----------------
def init_tables():
    c=A.db()
    try:
        c.executescript("""CREATE TABLE IF NOT EXISTS api_keys(id TEXT PRIMARY KEY,name TEXT NOT NULL DEFAULT '',token TEXT NOT NULL UNIQUE,enabled INTEGER NOT NULL DEFAULT 1,created INTEGER NOT NULL,last INTEGER NOT NULL DEFAULT 0,hits INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS api_configs(id TEXT PRIMARY KEY,account TEXT NOT NULL,label TEXT NOT NULL DEFAULT '',delivery TEXT NOT NULL DEFAULT 'api',apis TEXT NOT NULL DEFAULT '[]',settings TEXT NOT NULL DEFAULT '{}',created INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS api_configs_acc ON api_configs(account);
CREATE TABLE IF NOT EXISTS api_subs(account TEXT PRIMARY KEY,token TEXT NOT NULL UNIQUE,enabled INTEGER NOT NULL DEFAULT 1,created INTEGER NOT NULL,hits INTEGER NOT NULL DEFAULT 0,last INTEGER NOT NULL DEFAULT 0);""")
        c.commit()
    finally:
        c.close()
def api_on():
    return A.get("api_on","0")=="1"
def sub_on():
    return A.get("sub_on","0")=="1"
def new_hash():
    return secrets.token_hex(16)
def new_id():
    return secrets.token_hex(5)
def eligible(r):
    """Accounts the Isile app can import: SSH (ws, ssl, direct, VayDNS, SlowDNS) and V2Ray over ws, grpc or xhttp."""
    p,t=r["proto"],r["transport"]
    if p=="ssh":
        return t in ("ws","ssl","direct","dns","slowdns")
    return p in A.V2 and t in ("ws","grpc","xhttp")
def family(r):
    if r["proto"]=="ssh":
        return {"dns":"vay","slowdns":"slow"}.get(r["transport"],"ssh")
    return "v2"
def fields_for(r):
    f=family(r)
    if f=="ssh":
        out=list(FIELDS_SSH)
    elif f=="vay":
        out=list(FIELDS_VAY)
    elif f=="slow":
        out=list(FIELDS_SLOW)
    else:
        out=list(FIELDS_V2)+(FIELDS_V2_VLESS if r["proto"]=="vless" else FIELDS_V2_VMESS if r["proto"]=="vmess" else [])
    return COMMON+out
# ---------------- defaults, validation, profile, link ----------------
def _ip():
    return A.get("server_ip","") or A.host()
def base_profile(r,tls=None,net=None):
    """The profile exactly as the panel itself would hand it out, for the given tls flag / network (None = the account's own)."""
    p=dict(PROFILE)
    dom=A.host()
    pr=r["proto"]
    tr=r["transport"]
    own_tls=bool(A.tls_on() and r["tls"] in ("tls","both"))
    if tr in ("direct","dns","slowdns"):
        own_tls=False
    if tr=="ssl":
        own_tls=True
    use=own_tls if tls is None else bool(tls)
    p["kind"]={"ssh":"SSH","vless":"VLESS","vmess":"VMESS","trojan":"TROJAN"}[pr]
    p["host"]=dom
    p["tls"]=use
    if use:
        p["sni"]=dom
    if pr=="ssh":
        p["user"]=r["name"]
        p["pass"]=r["secret"]
        if tr=="ws":
            p.update(ws=True,wsPath="/",wsHost=dom,port=443 if use else 80)
        elif tr=="ssl":
            p["port"]=443
        elif tr=="direct":
            p["port"]=A.ssh_port()
        elif tr=="dns":
            fl,rs,rt=A.vaydns_client_args(_ip())
            idle,keep,_=A.vaydns_adv()
            p.update(host=A.vaydns_domain(),port=22,dns="vaydns",dnsTransport=fl[1:],dnsResolver=rs,dnsRecord=rt,dnsPubkey=A.vaydns_pub() or "",
                     dnsIdle=str(idle) if idle else "",dnsKeepalive=str(keep) if keep else "")
        elif tr=="slowdns":
            ip=_ip()
            p.update(host=A.slowdns_domain(),port=22,dns="slowdns",dnsPubkey=A.slowdns_pub() or "",dnsResolver="%s:%d"%(ip,A.VAYDNS_PORT) if A.IPV4_RE.fullmatch(ip or "") else "")
        if tr in ("dns","slowdns"):
            p["sni"]=dom if use else ""
        return p
    net=net or tr
    p["secret"]=r["secret"]
    p["network"]=net
    p["ws"]=net=="ws"
    p["port"]=443 if use else 80
    p["security"]="tls" if use else "none"
    p["wsHost"]=dom
    p["wsPath"]="/"+pr+("-xhttp" if net=="xhttp" else "") if net in ("ws","xhttp") else "/"
    p["serviceName"]=pr+"-grpc" if net=="grpc" else ""
    p["alpn"]="h2" if use and net in ("grpc","xhttp") else ""
    return p
def _text(v,mx):
    v=str(v).replace("\x00","")
    return v if len(v)<=mx else None
def clean(r,ov):
    """Keep only known, valid settings for this account. Returns (settings, error field or None)."""
    spec={f["k"]:f for f in fields_for(r)}
    out={}
    if not isinstance(ov,dict):
        return {},None
    for k,v in ov.items():
        f=spec.get(k)
        if not f or v is None:
            continue
        t=f["t"]
        if t=="bool":
            if not isinstance(v,bool):
                return None,k
            out[k]=v
        elif t=="int":
            s=str(v).strip()
            if s=="":
                continue
            if not re.fullmatch(r"[0-9]{1,7}",s) or not f["lo"]<=int(s)<=f["hi"]:
                return None,k
            out[k]=int(s) if k in ("port","proxyPort","alterId") else s
        elif t=="select":
            s=str(v)
            if s=="" and "" not in f["opts"]:
                continue
            if s not in f["opts"]:
                return None,k
            out[k]=s
        else:
            s=_text(v,f.get("mx",253))
            if s is None:
                return None,k
            if t=="text":
                s=s.strip()
                if re.search(r"[\r\n\t]",s):
                    return None,k
            if s=="" and k!="proxyHost":
                continue
            if k in ("host","wsHost","sni","proxyHost") and s and not re.fullmatch(r"[A-Za-z0-9_.:\-\[\]]{1,253}",s):
                return None,k
            if k=="wsPath" and not s.startswith("/"):
                return None,k
            if k=="dnsListen" and not re.fullmatch(r"([0-9]{1,5}|(127\.0\.0\.1|localhost|0\.0\.0\.0):[0-9]{1,5})",s):
                return None,k
            if k=="dnsResolver" and not re.fullmatch(r"(https?://[^\s]{4,240}|[A-Za-z0-9_.\-\[\]:]{3,253})",s):
                return None,k
            if k in ("dnsUtls",) and not re.fullmatch(r"[A-Za-z0-9_*,.\-]+",s):
                return None,k
            if k=="dnsExtra" and not re.fullmatch(r"[A-Za-z0-9_ .,:/=*\-]*",s):
                return None,k
            if k=="alpn" and not re.fullmatch(r"[A-Za-z0-9/.,\-]*",s):
                return None,k
            out[k]=s
    return out,None
def build_profile(r,cfg_id,label,ov):
    """Full Profile JSON (Profile.fromJson compatible) for account r with the stored overrides."""
    ov=ov or {}
    p=base_profile(r,ov.get("tls"),ov.get("network"))
    for k,v in ov.items():
        if k in p and k!="label":
            p[k]=v
    if "tls" in ov and not ov["tls"]:
        p["sni"]=ov.get("sni","")
    if p["kind"]!="SSH":
        p["ws"]=p["network"]=="ws"
        p["security"]="tls" if p["tls"] else "none"
    if p["dns"]=="slowdns":
        p["dnsTransport"]="udp"
    p["uid"]=cfg_id
    p["name"]=ov.get("label") or label or r["name"]
    p["locked"]=bool(ov.get("locked",False))
    return p
def _enc(s):
    return quote(str(s),safe="_-!.~'()*")
def link_of(p):
    """Port of LinkGen.make() of the Isile app: the share link that the app (and other clients) import."""
    k=p["kind"]
    host=p["host"]
    hp="[%s]"%host if ":" in host and not host.startswith("[") else host
    def build(scheme,info,q):
        s="%s://%s@%s:%d"%(scheme,info,hp,int(p["port"]))
        if q:
            s+="?"+"&".join("%s=%s"%(a,_enc(b)) for a,b in q)
        if p["name"].strip():
            s+="#"+_enc(p["name"])
        return s
    def net():
        return "ws" if p["ws"] else (p["network"] if p["network"] in ("grpc","httpupgrade","xhttp") else "tcp")
    if k=="SSH":
        q=[]
        info=_enc(p["user"])+":"+_enc(p["pass"])
        if p["dns"]:
            q.append(("dns",p["dns"]))
            if p["dns"]=="vaydns" and p["dnsTransport"]!="udp":
                q.append(("transport",p["dnsTransport"]))
            q.append(("resolver",p["dnsResolver"]))
            q.append(("pubkey",p["dnsPubkey"]))
            if p["dns"]=="vaydns":
                if str(p["dnsRecord"]).strip():
                    q.append(("rtype",p["dnsRecord"]))
                if p["dnsCompat"]:
                    q.append(("compat","1"))
                for a,b in (("idle","dnsIdle"),("keepalive","dnsKeepalive"),("udptimeout","dnsUdpTimeout"),("openstream","dnsOpenStream"),("workers","dnsWorkers"),("rps","dnsRps"),
                            ("maxqname","dnsMaxQname"),("maxlabels","dnsMaxLabels"),("clientid","dnsClientId"),("utls","dnsUtls"),("loglevel","dnsLogLevel"),("extra","dnsExtra")):
                    if str(p[b]).strip():
                        q.append((a,p[b]))
            if str(p["dnsListen"]).strip():
                q.append(("listen",p["dnsListen"]))
        else:
            if p["payloadOn"]:
                q.append(("payload",p["payload"]))
            if str(p["proxyHost"]).strip():
                q.append(("proxy","%s:%d"%(p["proxyHost"].strip(),int(p["proxyPort"]))))
            if p["ws"]:
                q.append(("ws","1"))
                if p["wsPath"] and p["wsPath"]!="/":
                    q.append(("path",p["wsPath"]))
                if p["wsHost"]:
                    q.append(("host",p["wsHost"]))
        if p["tls"]:
            q.append(("tls","1"))
            if p["sni"]:
                q.append(("sni",p["sni"]))
            if p["tlsVersion"] and p["tlsVersion"]!="Auto":
                q.append(("tlsv",p["tlsVersion"]))
            if p["insecure"]:
                q.append(("insecure","1"))
        return build("ssh",info,q)
    if k=="VMESS":
        n=net()
        o={"v":"2","ps":p["name"],"add":host,"port":str(p["port"]),"id":p["secret"],"aid":str(p["alterId"]),"scy":p["vmessScy"] or "auto","net":n,"type":"none",
           "host":p["wsHost"],"path":p["serviceName"] if n=="grpc" else (p["wsPath"] or "/"),"tls":"tls" if p["tls"] else "","sni":p["sni"],"alpn":p["alpn"],"fp":p["fingerprint"]}
        if p["insecure"]:
            o["allowInsecure"]="1"
        return "vmess://"+base64.b64encode(json.dumps(o,separators=(",",":")).encode()).decode()
    n=net()
    q=[]
    if k=="VLESS":
        q.append(("encryption",p["encryption"] or "none"))
    if p["flow"]:
        q.append(("flow",p["flow"]))
    q.append(("security","tls" if p["tls"] else "none"))
    q.append(("type",n))
    if n in ("ws","httpupgrade","xhttp"):
        q.append(("path",p["wsPath"] or "/"))
        if p["wsHost"]:
            q.append(("host",p["wsHost"]))
    elif n=="grpc":
        q.append(("serviceName",p["serviceName"]))
        q.append(("mode","gun"))
    if n=="xhttp":
        q.append(("mode","auto"))
    if p["tls"]:
        if p["sni"]:
            q.append(("sni",p["sni"]))
        if p["fingerprint"]:
            q.append(("fp",p["fingerprint"]))
        if p["alpn"]:
            q.append(("alpn",p["alpn"]))
        if p["insecure"]:
            q.append(("allowInsecure","1"))
    return build("vless" if k=="VLESS" else "trojan",_enc(p["secret"]),q)
def type_line(p):
    if p["dns"]:
        return "SSH · %s%s"%("VayDNS" if p["dns"]=="vaydns" else "SlowDNS"," · TLS" if p["tls"] else "")
    parts=[{"SSH":"SSH","VLESS":"VLESS","VMESS":"VMess","TROJAN":"Trojan"}[p["kind"]]]
    if p["kind"]=="SSH":
        if p["ws"]:
            parts.append("WS")
        if p["payloadOn"]:
            parts.append("Payload")
    else:
        parts.append({"ws":"WS","grpc":"gRPC","xhttp":"XHTTP","httpupgrade":"HTTPUpgrade"}.get(p["network"],"TCP"))
    if p["tls"]:
        parts.append("TLS")
    return " · ".join(parts)
# ---------------- public side ----------------
def _acct(c,name):
    return c.execute("SELECT * FROM accounts WHERE name=?",(name,)).fetchone()
def _cfg_rows(c,where="",args=()):
    return c.execute("SELECT * FROM api_configs "+where+" ORDER BY created,rowid",args).fetchall()
def _item(r,row):
    try:
        ov=json.loads(row["settings"])
    except ValueError:
        ov={}
    ov=ov if isinstance(ov,dict) else {}
    p=build_profile(r,row["id"],row["label"],ov)
    return p,link_of(p)
def _miss(ip):
    now=time.time()
    for k in [k for k,v in MISS.items() if now-v[1]>900]:
        MISS.pop(k,None)
    m=MISS.get(ip,[0,now])
    MISS[ip]=[m[0]+1,now]
def handle(h):
    """Called by app.py for GET /<h>. Returns a Response for an API or subscription hash, None when h is not one."""
    h=(h or "").lower()
    if not HASH_RE.fullmatch(h):
        return None
    ip=A.client_ip()
    m=MISS.get(ip)
    if m and m[0]>=40 and time.time()-m[1]<900:
        return Response("Too many requests",429)
    now=int(time.time())
    c=A.db()
    try:
        k=c.execute("SELECT * FROM api_keys WHERE token=?",(h,)).fetchone()
        if k and k["enabled"] and api_on():
            rows=[]
            for row in _cfg_rows(c,"WHERE delivery IN ('api','both')"):
                try:
                    ids=json.loads(row["apis"])
                except ValueError:
                    ids=[]
                if ids and k["id"] not in ids:
                    continue
                r=_acct(c,row["account"])
                if not r or not eligible(r) or A.calc(r,now)!="active":
                    continue
                p,l=_item(r,row)
                rows.append({"id":row["id"],"name":p["name"],"account":r["name"],"type":type_line(p),"link":l,"profile":p,"expires":r["expires"],"quota":r["quota"],"used":r["up"]+r["down"]})
            c.execute("UPDATE api_keys SET hits=hits+1,last=? WHERE id=?",(now,k["id"]))
            c.commit()
            fmt=request.args.get("format","json")
            if fmt in ("links","raw"):
                return Response("\n".join(x["link"] for x in rows),mimetype="text/plain")
            if fmt=="base64":
                return Response(base64.b64encode("\n".join(x["link"] for x in rows).encode()).decode(),mimetype="text/plain")
            return jsonify(version=1,name=k["name"],updated=now,count=len(rows),configs=rows)
        s=c.execute("SELECT * FROM api_subs WHERE token=?",(h,)).fetchone()
        if s and s["enabled"] and sub_on():
            r=_acct(c,s["account"])
            if r and eligible(r) and A.calc(r,now)=="active":
                links=[]
                profs=[]
                for row in _cfg_rows(c,"WHERE account=? AND delivery IN ('sub','both')",(r["name"],)):
                    p,l=_item(r,row)
                    links.append(l)
                    profs.append(p)
                if links:
                    c.execute("UPDATE api_subs SET hits=hits+1,last=? WHERE account=?",(now,r["name"]))
                    c.commit()
                    fmt=request.args.get("format","base64")
                    if fmt=="json":
                        resp=jsonify(version=1,account=r["name"],count=len(links),links=links,profiles=profs)
                    elif fmt in ("raw","links"):
                        resp=Response("\n".join(links),mimetype="text/plain")
                    else:
                        resp=Response(base64.b64encode("\n".join(links).encode()).decode(),mimetype="text/plain")
                    ui="upload=%d; download=%d"%(r["up"],r["down"])
                    if r["quota"]:
                        ui+="; total=%d"%r["quota"]
                    if r["expires"]:
                        ui+="; expire=%d"%r["expires"]
                    resp.headers["Subscription-Userinfo"]=ui
                    resp.headers["Profile-Update-Interval"]="12"
                    resp.headers["Profile-Title"]=r["name"]
                    return resp
    finally:
        c.close()
    _miss(ip)
    return Response("Not found",404)
# ---------------- hooks used by app.py ----------------
def info_items(r):
    """Items for the account info dialog: the subscription link of the account."""
    if not sub_on() or not eligible(r):
        return []
    c=A.db()
    try:
        s=c.execute("SELECT token,enabled FROM api_subs WHERE account=?",(r["name"],)).fetchone()
        n=c.execute("SELECT COUNT(*) FROM api_configs WHERE account=? AND delivery IN ('sub','both')",(r["name"],)).fetchone()[0]
    finally:
        c.close()
    if not s or not s["enabled"]:
        return []
    return [{"k":"sub_link","value":A.page_url(s["token"]),"rows":2,"n":n}]
def on_delete(c,name):
    c.execute("DELETE FROM api_configs WHERE account=?",(name,))
    c.execute("DELETE FROM api_subs WHERE account=?",(name,))
def on_reset(c):
    c.execute("DELETE FROM api_configs")
    c.execute("DELETE FROM api_subs")
# ---------------- admin endpoints ----------------
def _key_json(c,k):
    n=0
    for row in _cfg_rows(c,"WHERE delivery IN ('api','both')"):
        try:
            ids=json.loads(row["apis"])
        except ValueError:
            ids=[]
        if not ids or k["id"] in ids:
            n+=1
    return {"id":k["id"],"name":k["name"],"enabled":bool(k["enabled"]),"url":A.page_url(k["token"]),"created":k["created"],"last":k["last"],"hits":k["hits"],"configs":n}
def _cfg_json(c,row,r):
    try:
        ov=json.loads(row["settings"])
    except ValueError:
        ov={}
    try:
        ids=json.loads(row["apis"])
    except ValueError:
        ids=[]
    p=build_profile(r,row["id"],row["label"],ov)
    return {"id":row["id"],"account":row["account"],"label":row["label"],"delivery":row["delivery"],"apis":ids,"settings":ov,"type":type_line(p),"host":p["host"],"port":p["port"],"status":A.calc(r,int(time.time())),"proto":r["proto"],"transport":r["transport"]}
def snapshot(c):
    now=int(time.time())
    accs={r["name"]:r for r in c.execute("SELECT * FROM accounts ORDER BY name")}
    for row in _cfg_rows(c):
        if row["account"] not in accs:
            c.execute("DELETE FROM api_configs WHERE id=?",(row["id"],))
    c.commit()
    keys=[_key_json(c,k) for k in c.execute("SELECT * FROM api_keys ORDER BY created,rowid")]
    cfgs=[_cfg_json(c,row,accs[row["account"]]) for row in _cfg_rows(c) if row["account"] in accs and eligible(accs[row["account"]])]
    subs={s["account"]:s for s in c.execute("SELECT * FROM api_subs")}
    elig=[{"name":r["name"],"proto":r["proto"],"transport":r["transport"],"tls":r["tls"],"status":A.calc(r,now),"sub":bool(subs.get(r["name"]) and subs[r["name"]]["enabled"])} for r in accs.values() if eligible(r)]
    return {"api_on":api_on(),"sub_on":sub_on(),"keys":keys,"configs":cfgs,"accounts":elig}
def admin_get():
    c=A.db()
    try:
        return jsonify(snapshot(c))
    finally:
        c.close()
def admin_settings():
    d=request.get_json(silent=True) or {}
    c=A.db()
    try:
        if "api_on" in d:
            on=bool(d["api_on"])
            A.put("api_on","1" if on else "0")
            if on and not c.execute("SELECT 1 FROM api_keys").fetchone():
                c.execute("INSERT INTO api_keys(id,name,token,enabled,created) VALUES(?,?,?,1,?)",(new_id(),"API 1",new_hash(),int(time.time())))
                c.commit()
        if "sub_on" in d:
            A.put("sub_on","1" if d["sub_on"] else "0")
        A.audit("api-settings","api=%s sub=%s"%(api_on(),sub_on()))
        return jsonify(snapshot(c))
    finally:
        c.close()
def key_new():
    d=request.get_json(silent=True) or {}
    c=A.db()
    try:
        if c.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]>=20:
            return A.err("too_many")
        n=c.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]+1
        name=str(d.get("name") or "").strip()[:40] or "API %d"%n
        c.execute("INSERT INTO api_keys(id,name,token,enabled,created) VALUES(?,?,?,1,?)",(new_id(),name,new_hash(),int(time.time())))
        c.commit()
        A.audit("api-key-new",name)
        return jsonify(snapshot(c))
    finally:
        c.close()
def key_edit(kid):
    d=request.get_json(silent=True) or {}
    c=A.db()
    try:
        k=c.execute("SELECT * FROM api_keys WHERE id=?",(kid,)).fetchone()
        if not k:
            return A.err("not_found",404)
        if "name" in d:
            c.execute("UPDATE api_keys SET name=? WHERE id=?",(str(d["name"]).strip()[:40],kid))
        if "enabled" in d:
            c.execute("UPDATE api_keys SET enabled=? WHERE id=?",(1 if d["enabled"] else 0,kid))
        if d.get("regen"):
            c.execute("UPDATE api_keys SET token=?,hits=0,last=0 WHERE id=?",(new_hash(),kid))
            A.audit("api-key-regen",k["name"])
        c.commit()
        return jsonify(snapshot(c))
    finally:
        c.close()
def key_del(kid):
    c=A.db()
    try:
        c.execute("DELETE FROM api_keys WHERE id=?",(kid,))
        # configs that named only this API would otherwise become "all APIs": make them stop being sent through the API
        for row in _cfg_rows(c,"WHERE delivery IN ('api','both')"):
            try:
                ids=json.loads(row["apis"])
            except ValueError:
                ids=[]
            if ids and kid in ids:
                ids=[i for i in ids if i!=kid]
                if ids:
                    c.execute("UPDATE api_configs SET apis=? WHERE id=?",(json.dumps(ids),row["id"]))
                else:
                    c.execute("UPDATE api_configs SET delivery=? WHERE id=?",("sub" if row["delivery"]=="both" else "none",row["id"]))
        c.commit()
        return jsonify(snapshot(c))
    finally:
        c.close()
def _need(c,name):
    r=_acct(c,str(name or ""))
    if not r:
        return None,A.err("not_found",404)
    if not eligible(r):
        return None,A.err("api_unsupported")
    return r,None
def fields_get(account):
    c=A.db()
    try:
        r,e=_need(c,account)
        if e:
            return e
        p=build_profile(r,"",r["name"],{})
        return jsonify(fields=fields_for(r),profile=p,link=link_of(p),type=type_line(p))
    finally:
        c.close()
def preview():
    d=request.get_json(silent=True) or {}
    c=A.db()
    try:
        r,e=_need(c,d.get("account"))
        if e:
            return e
        ov,bad=clean(r,d.get("settings"))
        if ov is None:
            return A.err("api_bad_field",400,bad)
        p=build_profile(r,"preview",str(d.get("label") or r["name"]),ov)
        return jsonify(profile=p,link=link_of(p),type=type_line(p))
    finally:
        c.close()
def _cfg_body(c,d,r):
    ov,bad=clean(r,d.get("settings"))
    if ov is None:
        return None,A.err("api_bad_field",400,bad)
    delivery=d.get("delivery","api")
    if delivery not in DELIVERY:
        return None,A.err("bad_values")
    ids=d.get("apis") or []
    if not isinstance(ids,list):
        return None,A.err("bad_values")
    have={k["id"] for k in c.execute("SELECT id FROM api_keys")}
    ids=[i for i in ids if i in have]
    return (ov,delivery,ids),None
def cfg_new():
    d=request.get_json(silent=True) or {}
    c=A.db()
    try:
        r,e=_need(c,d.get("account"))
        if e:
            return e
        if c.execute("SELECT COUNT(*) FROM api_configs").fetchone()[0]>=500:
            return A.err("too_many")
        b,e=_cfg_body(c,d,r)
        if e:
            return e
        ov,delivery,ids=b
        n=c.execute("SELECT COUNT(*) FROM api_configs WHERE account=?",(r["name"],)).fetchone()[0]
        label=str(d.get("label") or "").strip()[:40] or (r["name"] if n==0 else "%s-%d"%(r["name"],n+1))
        ov.pop("label",None)
        c.execute("INSERT INTO api_configs(id,account,label,delivery,apis,settings,created) VALUES(?,?,?,?,?,?,?)",(new_id(),r["name"],label,delivery,json.dumps(ids),json.dumps(ov),int(time.time())))
        c.commit()
        A.audit("api-config-new",r["name"])
        return jsonify(snapshot(c))
    finally:
        c.close()
def cfg_edit(cid):
    d=request.get_json(silent=True) or {}
    c=A.db()
    try:
        row=c.execute("SELECT * FROM api_configs WHERE id=?",(cid,)).fetchone()
        if not row:
            return A.err("not_found",404)
        r,e=_need(c,row["account"])
        if e:
            return e
        # a partial body (only the delivery switch, for example) keeps the rest as it is
        cur=json.loads(row["settings"] or "{}")
        body={"settings":d["settings"] if "settings" in d else cur,"delivery":d.get("delivery",row["delivery"]),"apis":d["apis"] if "apis" in d else json.loads(row["apis"] or "[]")}
        b,e=_cfg_body(c,body,r)
        if e:
            return e
        ov,delivery,ids=b
        label=str(d["label"]).strip()[:40] if "label" in d else row["label"]
        c.execute("UPDATE api_configs SET label=?,delivery=?,apis=?,settings=? WHERE id=?",(label or row["label"],delivery,json.dumps(ids),json.dumps(ov),cid))
        c.commit()
        return jsonify(snapshot(c))
    finally:
        c.close()
def cfg_del(cid):
    c=A.db()
    try:
        c.execute("DELETE FROM api_configs WHERE id=?",(cid,))
        c.commit()
        return jsonify(snapshot(c))
    finally:
        c.close()
def _sub_json(c,r):
    s=c.execute("SELECT * FROM api_subs WHERE account=?",(r["name"],)).fetchone()
    n=c.execute("SELECT COUNT(*) FROM api_configs WHERE account=? AND delivery IN ('sub','both')",(r["name"],)).fetchone()[0]
    return {"sub_on":sub_on(),"eligible":eligible(r),"enabled":bool(s and s["enabled"]),"url":A.page_url(s["token"]) if s else "","configs":n,"hits":s["hits"] if s else 0}
def sub_get(account):
    c=A.db()
    try:
        r=_acct(c,account)
        if not r:
            return A.err("not_found",404)
        return jsonify(_sub_json(c,r))
    finally:
        c.close()
def sub_set(account):
    d=request.get_json(silent=True) or {}
    c=A.db()
    try:
        r,e=_need(c,account)
        if e:
            return e
        s=c.execute("SELECT * FROM api_subs WHERE account=?",(r["name"],)).fetchone()
        if "enabled" in d:
            en=1 if d["enabled"] else 0
            if s:
                c.execute("UPDATE api_subs SET enabled=? WHERE account=?",(en,r["name"]))
            elif en:
                c.execute("INSERT INTO api_subs(account,token,enabled,created) VALUES(?,?,1,?)",(r["name"],new_hash(),int(time.time())))
        if d.get("regen") and (s or d.get("enabled")):
            c.execute("UPDATE api_subs SET token=?,hits=0,last=0 WHERE account=?",(new_hash(),r["name"]))
        c.commit()
        return jsonify(_sub_json(c,r))
    finally:
        c.close()
