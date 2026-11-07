#!/usr/bin/env bash
APP=/opt/vpnpanel
DATA=/var/lib/vpnpanel
PY="$APP/venv/bin/python"
LOG=/var/log/isile-install.log
[ "$(id -u)" -eq 0 ] || { echo "Run as root: sudo isile"; exit 1; }
[ -f "$DATA/panel.db" ] || { echo "isile is not installed"; exit 1; }
DOMAIN_RE='^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$'
EMAIL_RE='^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
dbget(){ python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);r=c.execute("SELECT v FROM settings WHERE k=?",(sys.argv[2],)).fetchone();print(r[0] if r else "")' "$DATA/panel.db" "$1"; }
dbq(){ python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);[print(*r) for r in c.execute(sys.argv[2])]' "$DATA/panel.db" "$1"; }
dbset(){ python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1],timeout=30);c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(sys.argv[2],sys.argv[3]));c.commit()' "$DATA/panel.db" "$1" "$2"; }

# ---------- look and feel ----------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ -n "${TERM:-}" ] && [ "$TERM" != dumb ]; then
c_rs=$'\e[0m'; c_b=$'\e[1m'; c_d=$'\e[2m'; c_y=$'\e[33m'; c_c=$'\e[36m'
c_br=$'\e[1;31m'; c_bg=$'\e[1;32m'; c_by=$'\e[1;33m'; c_bc=$'\e[1;36m'; c_bm=$'\e[1;35m'; c_r=$'\e[31m'; c_g=$'\e[32m'
else
c_rs=""; c_b=""; c_d=""; c_y=""; c_c=""; c_br=""; c_bg=""; c_by=""; c_bc=""; c_bm=""; c_r=""; c_g=""
fi
case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
*[Uu][Tt][Ff]-8*|*[Uu][Tt][Ff]8*)
g_h='─'; g_tl='╭'; g_tr='╮'; g_bl='╰'; g_br='╯'; g_v='│'; g_dot='●'; g_ring='○'; g_up='▲'; g_ok='✔'; g_no='✘'; g_arr='›'
g_sp=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏');;
*)
g_h='-'; g_tl='+'; g_tr='+'; g_bl='+'; g_br='+'; g_v='|'; g_dot='*'; g_ring='o'; g_up='^'; g_ok='+'; g_no='x'; g_arr='>'
g_sp=('|' '/' '-' '\');;
esac
W=60
if [ -t 1 ]; then
cols="$(tput cols 2>/dev/null || echo 80)"
[[ "$cols" =~ ^[0-9]+$ ]] || cols=80
W=$((cols-4)); [ "$W" -gt 60 ] && W=60; [ "$W" -lt 40 ] && W=40
fi
ALT=0; WTMP=""; WOUT=""; NOTE=""
cleanup(){
if [ "$ALT" = 1 ]; then printf '\e[?25h\e[?1049l'; ALT=0; fi
[ -z "$WTMP" ] || rm -f "$WTMP"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP
rep(){ local o="" i; for ((i=0;i<$2;i++)); do o+="$1"; done; printf '%s' "$o"; }
banner(){
local t="$1" ver pad
ver="v$(head -n1 "$APP/panel/VERSION" 2>/dev/null)"
pad=$((W-12-${#t}-${#ver}-2)); [ "$pad" -lt 1 ] && pad=1
printf '\e[H\e[2J'
printf ' %s%s%s%s\n' "$c_c" "$g_tl" "$(rep "$g_h" "$W")" "$g_tr$c_rs"
printf ' %s%s%s  %sisile%s  %s%s%s  %s%s%s%*s%s%s%s  %s%s%s\n' "$c_c" "$g_v" "$c_rs" "$c_bc" "$c_rs" "$c_d" "$g_arr" "$c_rs" "$c_b" "$t" "$c_rs" "$pad" "" "$c_d" "$ver" "$c_rs" "$c_c" "$g_v" "$c_rs"
printf ' %s%s%s%s%s\n' "$c_c" "$g_bl" "$(rep "$g_h" "$W")" "$g_br" "$c_rs"
}
screen(){ banner "$1"; printf '\n'; }
kv(){ printf '  %s%-11s%s %s\n' "$c_d" "$1" "$c_rs" "$2"; }
ok(){ printf '  %s%s%s %s\n' "$c_bg" "$g_ok" "$c_rs" "$1"; }
bad(){ printf '  %s%s%s %s\n' "$c_br" "$g_no" "$c_rs" "$1"; }
warn(){ printf '  %s!%s %s\n' "$c_by" "$c_rs" "$1"; }
info(){ printf '  %s%s%s\n' "$c_d" "$1" "$c_rs"; }
ask(){ printf '  %s%s%s ' "$c_b" "$1" "$c_rs"; read -r "$2" || exit 0; }
asks(){ printf '  %s%s%s ' "$c_b" "$1" "$c_rs"; read -rs "$2" || exit 0; echo; }
yn(){ local a; printf '  %s%s%s %s[y/N]%s ' "$c_b" "$1" "$c_rs" "$c_d" "$c_rs"; read -r a || exit 0; [[ "$a" =~ ^[Yy]$ ]]; }
pause(){ printf '\n  %sPress Enter to go back%s ' "$c_d" "$c_rs"; read -r _ || exit 0; }
cancelled(){ info "Cancelled, nothing was changed."; pause; }
work(){
local msg="$1" pid i=0 n=${#g_sp[@]} rc
shift
WTMP="$(mktemp)"
trap '' INT
"$@" >"$WTMP" 2>&1 &
pid=$!
printf '\e[?25l'
while kill -0 "$pid" 2>/dev/null; do
printf '\r  %s%s%s %s ' "$c_c" "${g_sp[i%n]}" "$c_rs" "$msg"
i=$((i+1))
sleep 0.12
done
wait "$pid"; rc=$?
printf '\r\e[K\e[?25h'
trap 'exit 130' INT
WOUT="$(cat "$WTMP")"
rm -f "$WTMP"; WTMP=""
return "$rc"
}
tail_log(){ tail -n "${1:-10}" "$LOG" 2>/dev/null | sed "s/^/    /" | cut -c1-$((W+2)); }
job_busy(){ [ -f "$DATA/job.json" ] && [ ! -f "$DATA/job.rc" ] && [ -n "$(find "$DATA/job.json" -mmin -15 2>/dev/null)" ]; }
busy_msg(){ screen "Please wait"; warn "A job started from the web panel is still running."; info "Try again in a minute."; pause; }

# ---------- state ----------
load(){
mapfile -t _S < <(python3 -c 'import sqlite3,sys
c=sqlite3.connect(sys.argv[1],timeout=10)
for k in sys.argv[2:]:
    r=c.execute("SELECT v FROM settings WHERE k=?",(k,)).fetchone()
    v=r[0] if r else ""
    if k=="totp_secret": v="1" if v else ""
    print(v)' "$DATA/panel.db" domain server_ip admin_user selfsigned port_panel totp_secret vaydns_domain slowdns_domain)
DOMAIN="${_S[0]}"; IP="${_S[1]}"; ADMIN="${_S[2]}"; SELF="${_S[3]}"; PORT="${_S[4]}"; TFA="${_S[5]}"; VDOM="${_S[6]}"; SDOM="${_S[7]}"
if ! [[ "$PORT" =~ ^[0-9]{4,5}$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then PORT=2080; fi
if [ -n "$DOMAIN" ]; then SCHEME=https; HOSTN="$DOMAIN"
elif [ "$SELF" = 1 ] && [ -s /etc/vpnpanel/selfsigned/cert.pem ]; then SCHEME=https; HOSTN="${IP:-server-address}"
else SCHEME=http; HOSTN="${IP:-server-address}"; fi
URL="$SCHEME://$HOSTN:$PORT"
}
latest_ver(){
local r="tamaa-pro/isile" b="main"
[ -f "$APP/.repo" ] && read -r r b <"$APP/.repo"
[ -n "$r" ] || r="tamaa-pro/isile"
[ -n "$b" ] || b="main"
curl -fsSL --max-time 6 -H 'Cache-Control: no-cache' "https://raw.githubusercontent.com/$r/$b/panel/VERSION?t=$(date +%s)" 2>/dev/null | head -n1
}
check_update(){
local re='^[0-9A-Za-z .+_-]{1,32}$'
work "Checking for updates..." latest_ver
LATEST="$(printf '%s' "$WOUT" | head -n1 | tr -d '\r')"
[[ "$LATEST" =~ $re ]] || LATEST=""
CUR="$(head -n1 "$APP/panel/VERSION" 2>/dev/null)"
if [ -z "$LATEST" ]; then UPD=none
elif [ "$LATEST" = "$CUR" ]; then UPD=same
elif [ "$(printf '%s\n%s\n' "$CUR" "$LATEST" | sort -V | tail -n1)" = "$LATEST" ]; then UPD=newer
else UPD=older; fi
}
port_bad(){
# prints why $1 cannot be the new panel port (nothing when it is fine)
local p="$1" sp lst
[[ "$p" =~ ^[0-9]{1,5}$ ]] || { echo "it is not a number"; return 0; }
p=$((10#$p))
if [ "$p" -lt 1024 ] || [ "$p" -gt 65535 ]; then echo "it must be between 1024 and 65535"; return 0; fi
if [ "$p" = "$PORT" ]; then echo "it is already the panel port"; return 0; fi
sp="$(sshd -T 2>/dev/null | awk '/^port /{print $2; exit}')"
sp="${sp:-22}"
if [ "$p" = "$sp" ]; then echo "it is the SSH port"; return 0; fi
if { [ "$p" -ge 10000 ] && [ "$p" -le 10299 ]; } || [ "$p" = 8000 ] || [ "$p" = 7000 ] || [ "$p" = 7001 ] || [ "$p" = 5300 ] || [ "$p" = 5301 ] || [ "$p" = 5302 ] || [ "$p" = 36712 ]; then echo "it is reserved for an internal service"; return 0; fi
lst=""
if command -v ss >/dev/null 2>&1; then lst="$(ss -H -ltn "sport = :$p" 2>/dev/null)"
elif timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$p" 2>/dev/null; then lst=busy; fi
if [ -n "$lst" ]; then echo "another program is already listening on it"; return 0; fi
}

# ---------- actions ----------
show_info(){
local s st svcs svc_col
load
local d="$DOMAIN" ip="$IP"
kv "Version" "$(head -n1 "$APP/panel/VERSION" 2>/dev/null)"
kv "Panel URL" "${c_bc}$URL${c_rs}"
kv "Username" "$ADMIN"
kv "Password" "${c_d}stored hashed, use option 1 to set a new one${c_rs}"
if [ -n "$TFA" ]; then kv "2-step" "${c_bg}enabled${c_rs}"; else kv "2-step" "${c_d}disabled${c_rs}"; fi
kv "Domain" "${d:-${c_d}not set (server address, no TLS)${c_rs}}"
kv "Server IP" "${ip:-unknown}"
if [ -n "$d" ]; then kv "Ports" "80 (no TLS) | 443 (TLS) | $PORT (panel, HTTPS)"; else kv "Ports" "80 (no TLS) | $PORT (panel, $([ "$SCHEME" = https ] && echo HTTPS || echo HTTP))"; fi
if [ -n "$d" ]; then kv "SSH SSL" "direct SSH on 80 (no TLS) and 443 (TLS via stunnel)"; else kv "SSH SSL" "direct SSH on 80 (no TLS)"; fi
kv "Paths" "/vless /vmess /trojan (WS), *-grpc, *-xhttp"
kv "" "any other path = SSH WebSocket"
if [ -f /etc/systemd/system/vaydns.service ]; then kv "VayDNS" "UDP 53 | tunnel domain: ${VDOM:-not set (set it in the panel)}"; fi
if [ -f /etc/systemd/system/slowdns.service ]; then kv "SlowDNS" "UDP 53 | tunnel domain: ${SDOM:-not set (set it in the panel)}"; fi
echo
printf '  %sServices%s\n' "$c_b" "$c_rs"
svcs="vpnpanel vpnmux nginx vpnbridge xray udp-custom vaydns slowdns"
[ -z "$d" ] || svcs="$svcs vpnstunnel"
for s in $svcs; do
if [ -f "/etc/systemd/system/$s.service" ] || [ "$s" = nginx ]; then
if systemctl is-active --quiet "$s" 2>/dev/null; then st="${c_bg}${g_dot} running${c_rs}"; else st="${c_br}${g_dot} stopped${c_rs}"; fi
else st="${c_d}${g_ring} not installed${c_rs}"; fi
printf '    %-11s %s\n' "$s" "$st"
done
echo
printf '  %sAccounts%s\n' "$c_b" "$c_rs"
dbq "SELECT CASE WHEN proto='ssh' THEN 'ssh-'||transport ELSE proto END AS k,COUNT(*) FROM accounts GROUP BY k" | sed 's/^/    /'
}
edit_admin(){
local nu np np2
load
kv "Username" "$ADMIN"
echo
info "Press Enter to keep a value as it is."
echo
ask "New username:" nu
[ -z "$nu" ] || [[ "$nu" =~ ^[A-Za-z0-9_.-]{3,32}$ ]] || { bad "Username: 3-32 chars of A-Za-z0-9_.-"; return; }
asks "New password (min 10 chars):" np
if [ -n "$np" ]; then
[ "${#np}" -ge 10 ] || { bad "Password too short"; return; }
asks "Confirm password:" np2
[ "$np" = "$np2" ] || { bad "Passwords do not match"; return; }
fi
[ -n "$nu$np" ] || { info "Nothing changed."; return; }
VPN_ADMIN_USER="$nu" VPN_ADMIN_PASS="$np" "$PY" "$APP/panel/app.py" setadmin || { bad "Update failed"; return; }
echo
ok "Admin account updated. Open panel sessions were closed."
kv "Username" "$(dbget admin_user)"
[ -z "$np" ] || kv "Password" "$np"
}
two_step(){
local out sec uri code issuer rc
load
if [ -n "$TFA" ]; then
printf '  Status  %s%s ON%s\n\n' "$c_bg" "$g_dot" "$c_rs"
info "Panel sign-in currently asks for a code from your authenticator app."
echo
yn "Disable two-step verification?" || { cancelled; return 9; }
"$PY" "$APP/panel/app.py" rm2fa || { bad "Update failed"; return; }
echo
ok "Two-step verification is now disabled."
info "You can enable it again from this menu or from the panel settings."
return
fi
out="$("$PY" "$APP/panel/app.py" tfa-gen 2>/dev/null)"
sec="$(printf '%s\n' "$out" | sed -n 1p)"
uri="$(printf '%s\n' "$out" | sed -n 2p)"
[[ "$sec" =~ ^[A-Z2-7]{32}$ ]] || { bad "Could not generate a key"; return; }
issuer="isile${HOSTN:+ $HOSTN}"
printf '  Status  %s%s OFF%s\n\n' "$c_d" "$g_ring" "$c_rs"
printf '  %s1.%s In your authenticator app add an account by entering a key\n' "$c_bc" "$c_rs"
printf '     (time based, 6 digits) and copy this key:\n\n'
printf '       %s%s%s\n\n' "$c_by" "$sec" "$c_rs"
kv "Name" "$issuer ($ADMIN)"
echo
printf '  %s2.%s Type the 6-digit code the app shows to turn it on.\n' "$c_bc" "$c_rs"
info "Press Enter on an empty line to cancel."
echo
while true; do
ask "Code:" code
code="${code//[[:space:]]/}"
[ -n "$code" ] || { echo; cancelled; return 9; }
if ! [[ "$code" =~ ^[0-9]{6}$ ]]; then bad "Enter the 6 digits shown in the app."; continue; fi
TFA_SECRET="$sec" TFA_CODE="$code" "$PY" "$APP/panel/app.py" tfa-on; rc=$?
if [ "$rc" = 0 ]; then
echo
ok "Two-step verification is now enabled."
info "From now on the panel asks for a code at sign-in."
return
fi
if [ "$rc" = 1 ]; then bad "Wrong code. Codes change every 30 seconds, try the next one."; else bad "Could not enable it."; return; fi
done
}
change_domain(){
local d mail dip
load
kv "Domain" "${DOMAIN:-${c_d}not set${c_rs}}"
kv "Server IP" "${IP:-unknown}"
echo
info "Use this when the domain is lost, expired or blocked. A TLS certificate"
info "is issued for the new domain and the panel switches to it."
echo
ask "New domain (Enter to cancel):" d
d="$(printf '%s' "$d" | tr 'A-Z' 'a-z' | tr -d ' ')"
[ -n "$d" ] || { cancelled; return 9; }
[[ "$d" =~ $DOMAIN_RE ]] || { bad "Invalid domain name"; return; }
if [ "$d" = "$VDOM" ] || [ "$d" = "$SDOM" ]; then bad "That name is a DNS tunnel domain, choose a different one"; return; fi
dip="$(getent ahostsv4 "$d" 2>/dev/null | awk 'NR==1{print $1}')"
kv "Resolves to" "${dip:-nothing}"
if [ -n "$dip" ] && "$PY" "$APP/panel/app.py" cfip $dip; then
warn "Cloudflare proxy detected (orange cloud): that is why it differs from this server."
info "Direct SSH and the other ports do not go through it: use a DNS only"
info "(grey cloud) name for those. If the certificate fails, switch to grey"
info "cloud for a moment and turn off Always Use HTTPS."
case "$PORT" in 443|2053|2083|2087|2096|8443) ;; *) warn "Panel port $PORT is not supported by the proxy: use option 4 (2053, 2083, 2087, 2096 or 8443).";; esac
yn "Continue?" || { cancelled; return 9; }
elif [ -n "$IP" ] && [ "$dip" = "$IP" ]; then ok "The domain points to this server."
else
warn "The domain does not point to this server ($IP). The certificate will fail until its A record is fixed."
yn "Continue anyway?" || { cancelled; return 9; }
fi
ask "Email for certificate notices (optional):" mail
[ -z "$mail" ] || [[ "$mail" =~ $EMAIL_RE ]] || { bad "Invalid email address"; return; }
echo
yn "Apply $d now? It takes up to a minute." || { cancelled; return 9; }
echo
if work "Issuing the certificate and applying the domain..." bash "$APP/panel/setdomain.sh" "$d" "$mail"; then
load
ok "Domain changed to $d"
kv "Panel URL" "${c_bc}$URL${c_rs}"
warn "Open TCP 443 in the cloud firewall if it is not open yet."
else
bad "Changing the domain failed. Nothing else was touched. Last log lines:"
tail_log 10
fi
}
apply_port(){
local old="$1" new="$2" code="" i
dbset port_panel "$new" || return 1
ufw allow "$new/tcp" >/dev/null 2>&1
if ! bash "$APP/panel/setdomain.sh" --render "$DOMAIN" || ! systemctl reload nginx; then
dbset port_panel "$old"
bash "$APP/panel/setdomain.sh" --render "$DOMAIN" >/dev/null 2>&1
systemctl reload nginx >/dev/null 2>&1
ufw delete allow "$new/tcp" >/dev/null 2>&1
echo "nginx rejected the new configuration, the old port was kept"
return 1
fi
for i in $(seq 1 15); do
code="$(curl -ks -o /dev/null -w '%{http_code}' --max-time 4 "$SCHEME://127.0.0.1:$new/login")"
[ "$code" = 200 ] && break
sleep 1
done
if [ "$code" != 200 ]; then
dbset port_panel "$old"
bash "$APP/panel/setdomain.sh" --render "$DOMAIN" >/dev/null 2>&1
systemctl reload nginx >/dev/null 2>&1
ufw delete allow "$new/tcp" >/dev/null 2>&1
echo "the panel did not answer on port $new (HTTP $code), the old port was kept"
return 1
fi
ufw delete allow "$old/tcp" >/dev/null 2>&1
return 0
}
change_port(){
local p why old
load
old="$PORT"
kv "Panel port" "${c_bc}$PORT${c_rs}"
kv "Panel URL" "$URL"
echo
info "Allowed: 1024-65535, not used by SSH, another program or an internal service."
echo
ask "New port (Enter to cancel):" p
[ -n "$p" ] || { cancelled; return 9; }
why="$(port_bad "$p")"
[ -z "$why" ] || { bad "Port $p cannot be used: $why"; return; }
p=$((10#$p))
echo
yn "Change the panel port from $old to $p?" || { cancelled; return 9; }
echo
if work "Applying the new port..." apply_port "$old" "$p"; then
load
ok "Panel port changed from $old to $p"
kv "New URL" "${c_bc}$URL${c_rs}"
warn "Open TCP $p in the cloud firewall and close $old there."
else
bad "The port was not changed."
[ -z "$WOUT" ] || info "$(printf '%s' "$WOUT" | tail -n 3)"
fi
}
declare -A INST STT ACC
CK=(wsbridge udpcustom vaydns slowdns xray)
declare -A CN=([wsbridge]="SSH WebSocket" [udpcustom]="UDP Custom" [vaydns]="VayDNS" [slowdns]="SlowDNS" [xray]="Xray")
declare -A CD=([wsbridge]="SSH over a WebSocket bridge" [udpcustom]="SSH over UDP, third-party closed-source binary" [vaydns]="SSH and V2Ray through a DNS tunnel, open source" [slowdns]="SSH through a DNS tunnel for SlowDNS apps" [xray]="Runs VLESS, VMess and Trojan")
comp_state(){
local k i s a
INST=(); STT=(); ACC=()
while read -r k i s a; do INST[$k]="$i"; STT[$k]="$s"; ACC[$k]="$a"; done < <("$PY" "$APP/panel/app.py" comps 2>/dev/null)
}
svc_run(){
local act="$1" k="$2" rc
if [ "$act" = install ]; then "$PY" "$APP/panel/app.py" combos-on "$k" >/dev/null 2>&1; fi
if work "$([ "$act" = install ] && echo Installing || echo Removing) ${CN[$k]}..." bash -c ': > "$1"; bash "$2" "$3" "$4" >>"$1" 2>&1' _ "$LOG" "$APP/panel/components.sh" "$act" "$k"; then
work "Applying the change..." bash -c '"$1" "$2" applycomps; systemctl restart vpnpanel' _ "$PY" "$APP/panel/app.py"
echo
if [ "$act" = install ]; then ok "${CN[$k]} installed"; else ok "${CN[$k]} removed"; fi
else
echo
bad "The operation failed. Last log lines:"
tail_log 10
fi
}
svc_toggle(){
local k="$1" n="${CN[$k]}"
screen "$n"
if [ "${INST[$k]}" = 1 ]; then
warn "Remove $n?"
info "Its service stops for good. The accounts that use it (${ACC[$k]}) will not"
info "work until it is installed again. The accounts themselves are kept."
echo
yn "Remove $n?" || { cancelled; return; }
echo
svc_run uninstall "$k"
else
case "$k" in
udpcustom)
warn "Security warning"
info "It is a third-party closed-source binary: its code cannot be reviewed."
info "It is downloaded from an external address with no official checksum,"
info "so you trust whoever controls that address. You can remove it any time."
echo
yn "I understand the risks and want to install it" || { cancelled; return; };;
vaydns|slowdns)
info "Before installing, prepare a tunnel domain (such as t.example.com) you can"
info "add an NS record for, and open UDP 53 in the cloud firewall. The tunnel"
info "domain itself is set later from the panel, Settings > Components."
echo
yn "Install $n? It may take a minute." || { cancelled; return; };;
*)
yn "Install $n? It may take a minute." || { cancelled; return; };;
esac
echo
svc_run install "$k"
fi
pause
}
manage_services(){
local k i c st act
while true; do
comp_state
screen "Panel services"
i=0
for k in "${CK[@]}"; do
i=$((i+1))
if [ "${INST[$k]}" = 1 ]; then
case "${STT[$k]}" in
ok) st="${c_bg}${g_dot} running${c_rs}";;
warn) st="${c_by}${g_dot} not running${c_rs}";;
*) st="${c_d}${g_dot} disabled${c_rs}";;
esac
[ "${ACC[$k]:-0}" = 0 ] || st="$st ${c_d}(${ACC[$k]} acc)${c_rs}"
act="${c_r}remove${c_rs}"
else
st="${c_d}${g_ring} not installed${c_rs}"
act="${c_g}install${c_rs}"
fi
printf '   %s%2s%s   %-14s %s   %s\n' "$c_bc" "$i" "$c_rs" "${CN[$k]}" "$act" "$st"
printf '         %s%s%s\n' "$c_d" "${CD[$k]}" "$c_rs"
done
echo
info "SSH SSL is a core service and cannot be removed."
[ -z "$NOTE" ] || { printf '  %s%s%s\n' "$c_br" "$NOTE" "$c_rs"; NOTE=""; }
printf '\n  %sEnter%s  Back\n\n' "$c_by" "$c_rs"
printf '  %sSelect%s %s%s%s ' "$c_b" "$c_rs" "$c_c" "$g_arr" "$c_rs"
read -r c || exit 0
c="${c//[[:space:]]/}"
[ -n "$c" ] || return
if [[ "$c" =~ ^[0-9]+$ ]] && [ "$((10#$c))" -ge 1 ] && [ "$((10#$c))" -le "${#CK[@]}" ]; then
if job_busy; then busy_msg; else svc_toggle "${CK[$((10#$c-1))]}"; fi
else NOTE="Invalid choice: $c"; fi
done
}
reset_run(){
systemctl stop vpnpanel
"$PY" "$APP/panel/app.py" reset
local rc=$?
systemctl start vpnpanel
return "$rc"
}
reset_panel(){
local a
printf '  %sThis deletes every VPN account%s (and its system user), resets the usage\n' "$c_br" "$c_rs"
printf '  counters, and clears the public page, server message and monthly cap.\n\n'
info "Kept: admin account, domain and certificate, installed services."
echo
ask "Type YES to reset (Enter to cancel):" a
[ "$a" = YES ] || { cancelled; return 9; }
echo
if work "Resetting the panel..." reset_run; then ok "The panel was reset."; else bad "Reset failed."; [ -z "$WOUT" ] || info "$(printf '%s' "$WOUT" | tail -n 4)"; fi
}
restart_run(){
local list u others="" rc=0
list="$("$PY" "$APP/panel/app.py" svcs 2>/dev/null)"
[ -n "$list" ] || list="vpnpanel nginx vpnmux"
for u in $list; do case "$u" in vpnpanel|vpnstunnel) ;; *) others="$others $u";; esac; done
systemctl restart $others || rc=1
case " $list " in *" vpnstunnel "*) systemctl restart vpnstunnel || rc=1;; esac
systemctl restart vpnpanel || rc=1
echo "$list"
return "$rc"
}
restart_panel(){
local list u st
info "Restarts the panel, nginx, the multiplexer, stunnel and every active service."
info "Open VPN connections drop for a moment and reconnect."
echo
yn "Restart now?" || { cancelled; return 9; }
echo
if work "Restarting services..." restart_run; then ok "Services restarted."; else bad "Some services failed to restart."; fi
sleep 1
list="$(printf '%s' "$WOUT" | tail -n 1)"
echo
for u in $list; do
if systemctl is-active --quiet "$u"; then st="${c_bg}${g_dot} running${c_rs}"; else st="${c_br}${g_dot} stopped${c_rs}"; fi
printf '    %-11s %s\n' "$u" "$st"
done
}
update(){
local r b
r="tamaa-pro/isile"; b="main"
[ -f "$APP/.repo" ] && read -r r b <"$APP/.repo"
[ -n "$r" ] || r="tamaa-pro/isile"
[ -n "$b" ] || b="main"
echo "Updating from github.com/$r ($b) ..."
bash <(curl -fsSL "https://raw.githubusercontent.com/$r/$b/install.sh") --update
}
update_panel(){
local q
check_update
kv "Installed" "$CUR"
case "$UPD" in
newer) kv "Available" "${c_bg}$LATEST${c_rs}  ${c_bg}$g_up update available${c_rs}"; q="Update to $LATEST now? Accounts and settings are kept.";;
same) kv "Available" "$LATEST  ${c_d}(up to date)${c_rs}"; q="You are on the latest version. Reinstall it anyway?";;
older) kv "Available" "$LATEST  ${c_d}(older than the installed one)${c_rs}"; q="The repository has an older version. Install it anyway?";;
*) kv "Available" "${c_by}could not reach the repository${c_rs}"; q="Try the update anyway?";;
esac
echo
yn "$q" || { cancelled; return 9; }
echo
update
UPDATED=1
}
uninstall(){
local ans d n pp
if [ "${1:-}" = "--yes" ]; then ans=YES; else
echo "This removes the panel, Xray, the SSH bridge and SSL multiplexer, stunnel, UDP Custom, VayDNS and SlowDNS (if installed), all VPN accounts and the TLS certificate."
read -rp "Type YES to continue: " ans
fi
[ "$ans" = "YES" ] || { echo "Cancelled"; return 1; }
d="$(dbget domain)"
pp="$(dbget port_panel)"
local names
names="$(dbq "SELECT name FROM accounts WHERE proto='ssh'")"
systemctl disable --now vpnpanel vpnbridge vpnmux vpnstunnel xray udp-custom vpn-udpgw vaydns slowdns >/dev/null 2>&1
rm -f /etc/systemd/system/vaydns.service /etc/systemd/system/slowdns.service /etc/systemd/system/vpnpanel.service /etc/systemd/system/vpnbridge.service /etc/systemd/system/vpnmux.service /etc/systemd/system/vpnstunnel.service /etc/systemd/system/xray.service /etc/systemd/system/udp-custom.service /etc/systemd/system/vpn-udpgw.service /etc/vpnpanel/udpgw.nft
systemctl daemon-reload
if [ -d /usr/local/lib/isile/udp-custom ]; then
up="$(grep -oE '"listen"[^,]*' /usr/local/lib/isile/udp-custom/config.json 2>/dev/null | grep -oE '[0-9]{1,5}' | tail -1)"
ufw delete allow "${up:-36712}/udp" >/dev/null 2>&1
fi
nft delete table inet isile_udpc >/dev/null 2>&1
nft delete table inet isile_udpgw >/dev/null 2>&1
if [ -d /usr/local/lib/isile/vaydns ] || [ -d /usr/local/lib/isile/slowdns ]; then
nft delete table inet isile_vaydns >/dev/null 2>&1
nft delete table inet isile_dns >/dev/null 2>&1
ufw delete allow 53/udp >/dev/null 2>&1
ufw delete allow 5300/udp >/dev/null 2>&1
ufw delete allow 5301/udp >/dev/null 2>&1
ufw delete allow 5302/udp >/dev/null 2>&1
fi
rm -rf /usr/local/lib/isile /etc/vpnpanel/udp-custom.info
userdel udpc >/dev/null 2>&1
userdel udpgw >/dev/null 2>&1
userdel vaydns >/dev/null 2>&1
userdel slowdns >/dev/null 2>&1
groupdel udpc >/dev/null 2>&1
groupdel vaydns >/dev/null 2>&1
groupdel slowdns >/dev/null 2>&1
nft delete table inet vpnacct >/dev/null 2>&1
for n in $names; do
uid="$(id -u "$n" 2>/dev/null)"
if [ -n "$uid" ] && [ "$uid" -ge 20000 ] && [ "$uid" -lt 60000 ]; then
pkill -KILL -u "$n" >/dev/null 2>&1
userdel -f "$n" >/dev/null 2>&1
fi
done
groupdel vpnusers >/dev/null 2>&1
userdel xray >/dev/null 2>&1
rm -f /etc/ssh/sshd_config.d/99-vpnpanel.conf /etc/ssh/sshd_config.d/99-zvpnpanel-banner.conf
systemctl reload ssh >/dev/null 2>&1
rm -f /etc/nginx/conf.d/vpnpanel.conf
[ -e /etc/nginx/sites-available/default ] && ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
nginx -t >/dev/null 2>&1 && systemctl reload nginx >/dev/null 2>&1
[ -z "$d" ] || certbot delete --cert-name "$d" --non-interactive >/dev/null 2>&1
rm -f /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
for p in "${pp:-2080}" 2080 80 443; do ufw delete allow "$p/tcp" >/dev/null 2>&1; done
rm -rf "$APP" "$DATA" /etc/vpnpanel /usr/local/etc/xray /usr/local/share/xray /usr/local/bin/xray /var/log/xray /etc/logrotate.d/vpnpanel-xray /var/log/isile-install.log
echo "=================================================="
echo "  isile was uninstalled completely"
echo "=================================================="
echo " Installed packages (nginx, certbot, stunnel4, ufw, python3) were left in place."
rm -f /usr/local/bin/isile
return 0
}
delete_panel(){
local a
printf '  %sThis removes the panel completely:%s Xray, the SSH bridge and SSL\n' "$c_br" "$c_rs"
printf '  multiplexer, stunnel, UDP Custom, VayDNS and SlowDNS (if installed),\n'
printf '  all VPN accounts and the TLS certificate.\n\n'
info "Installed packages (nginx, certbot, stunnel4, ufw, python3) stay in place."
echo
ask "Type YES to delete (Enter to cancel):" a
[ "$a" = YES ] || { cancelled; return 9; }
echo
uninstall --yes
UPDATED=1
}

# ---------- menu ----------
item(){ printf '   %s%2s%s   %s%-30s%s %s\n' "$c_bc" "$1" "$c_rs" "$2" "$3" "$c_rs" "$4"; }
draw_menu(){
local run dom l2 up
load
if systemctl is-active --quiet vpnpanel 2>/dev/null; then run="${c_bg}${g_dot} running${c_rs}"; else run="${c_br}${g_dot} stopped${c_rs}"; fi
banner "Management menu"
printf '\n  %sPanel%s  %s%s%s   %s\n\n' "$c_d" "$c_rs" "$c_bc" "$URL" "$c_rs" "$run"
dom="${DOMAIN:-not set}"; [ "${#dom}" -le 22 ] || dom="${dom:0:21}~"
item 1 "" "Edit admin account" "${c_d}$ADMIN${c_rs}"
if [ -n "$TFA" ]; then item 2 "" "Disable two-step verification" "${c_bg}${g_dot} ON${c_rs}"; else item 2 "" "Enable two-step verification" "${c_d}${g_ring} OFF${c_rs}"; fi
item 3 "" "Change domain" "${c_d}$dom${c_rs}"
item 4 "" "Change port" "${c_d}$PORT${c_rs}"
item 5 "" "Show panel info" ""
item 6 "" "Manage panel services" ""
item 7 "$c_r" "Reset panel" ""
item 8 "$c_br" "Delete panel" ""
item 9 "$c_y" "Restart panel" ""
case "$UPD" in
newer) up="${c_bg}$g_up $LATEST available${c_rs}";;
same) up="${c_d}up to date${c_rs}";;
older) up="${c_d}up to date${c_rs}";;
*) up="${c_d}cannot check${c_rs}";;
esac
item 10 "$c_g" "Update panel" "$up"
echo
[ -z "$NOTE" ] || { printf '  %s%s%s\n' "$c_br" "$NOTE" "$c_rs"; NOTE=""; }
printf '  %sEnter%s  Close menu\n\n' "$c_by" "$c_rs"
printf '  %sSelect%s %s%s%s ' "$c_b" "$c_rs" "$c_c" "$g_arr" "$c_rs"
}
run_screen(){
# run_screen "Title" function: clears the terminal, runs the function, waits for Enter
local t="$1"
shift
if job_busy; then busy_msg; return; fi
screen "$t"
"$@"
local rc=$?
[ "$rc" = 9 ] && return
pause
}
menu(){
local c rc
UPDATED=0
ALT=1; printf '\e[?1049h'
banner "Management menu"
printf '\n'
check_update
while true; do
draw_menu
read -r c || break
c="${c//[[:space:]]/}"
[ -n "$c" ] || break
[[ "$c" =~ ^[0-9]+$ ]] && c=$((10#$c))
case "$c" in
1) run_screen "Edit admin account" edit_admin;;
2) if [ -n "$TFA" ]; then run_screen "Disable two-step verification" two_step; else run_screen "Enable two-step verification" two_step; fi;;
3) run_screen "Change domain" change_domain;;
4) run_screen "Change port" change_port;;
5) screen "Panel info"; show_info; pause;;
6) manage_services;;
7) run_screen "Reset panel" reset_panel;;
8) run_screen "Delete panel" delete_panel; [ "$UPDATED" = 1 ] && break;;
9) run_screen "Restart panel" restart_panel;;
10) if job_busy; then busy_msg; else screen "Update panel"; update_panel; rc=$?; [ "$rc" = 9 ] || pause; [ "$UPDATED" = 1 ] && break; check_update; fi;;
*) NOTE="Invalid choice: $c";;
esac
done
}
usage(){ echo "Usage: isile            open the management menu"; echo "       isile info       show panel information"; echo "       isile update     update to the latest version"; echo "       isile uninstall  remove the panel completely"; }
case "${1:-}" in
"") if [ -t 0 ] && [ -t 1 ]; then menu; else echo "The isile menu needs an interactive terminal (use: isile info)"; exit 1; fi;;
info) echo "=================================================="; echo "  isile panel info"; echo "=================================================="; show_info; echo "==================================================";;
update) update;;
uninstall) uninstall "${2:-}";;
4) update;;
3) if [ "${2:-}" = "--yes" ]; then uninstall --yes; else usage; exit 1; fi;;
*) usage; exit 1;;
esac
exit 0
