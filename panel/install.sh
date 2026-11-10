#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
REPO="${VPNPANEL_REPO:-tamaa-pro/isile}"
BRANCH="${VPNPANEL_BRANCH:-main}"
APP=/opt/vpnpanel
DATA=/var/lib/vpnpanel
LOG=/var/log/isile-install.log
STEP="starting"
FAILED_CMD=""
MODE=install
if [ "${1:-}" = "--update" ]; then MODE=update; fi
# ---------- terminal UI (only on an interactive terminal; otherwise plain text as before) ----------
UI=0
if [ -t 1 ] && [ -z "${ISILE_PLAIN:-}" ] && [ -n "${TERM:-}" ] && [ "$TERM" != dumb ]; then UI=1; fi
if [ "$UI" = 1 ] && [ -z "${NO_COLOR:-}" ]; then
c_rs=$'\e[0m'; c_b=$'\e[1m'; c_d=$'\e[2m'; c_c=$'\e[36m'; c_g=$'\e[32m'; c_r=$'\e[31m'; c_y=$'\e[33m'
c_br=$'\e[1;31m'; c_bg=$'\e[1;32m'; c_by=$'\e[1;33m'; c_bc=$'\e[1;36m'
else
c_rs=""; c_b=""; c_d=""; c_c=""; c_g=""; c_r=""; c_y=""; c_br=""; c_bg=""; c_by=""; c_bc=""
fi
case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
*[Uu][Tt][Ff]-8*|*[Uu][Tt][Ff]8*)
g_h='─'; g_tl='╭'; g_tr='╮'; g_bl='╰'; g_br='╯'; g_v='│'; g_ring='○'; g_ok='✔'; g_no='✘'; g_arr='›'; g_full='█'; g_empty='░'; g_skip='–'
g_sp=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏');;
*)
g_h='-'; g_tl='+'; g_tr='+'; g_bl='+'; g_br='+'; g_v='|'; g_ring='o'; g_ok='+'; g_no='x'; g_arr='>'; g_full='#'; g_empty='.'; g_skip='-'
g_sp=('|' '/' '-' '\');;
esac
W=60
if [ "$UI" = 1 ]; then
cols="$(tput cols 2>/dev/null || echo 80)"
[[ "$cols" =~ ^[0-9]+$ ]] || cols=80
W=$((cols-4)); [ "$W" -gt 60 ] && W=60; [ "$W" -lt 40 ] && W=40
ROWS="$(tput lines 2>/dev/null || echo 24)"
[[ "$ROWS" =~ ^[0-9]+$ ]] || ROWS=24
fi
ALT=0; TICK=""; UIDIR=""; STATEF=/dev/null; WARNF=/dev/null; T0=0; STEP_T=0; PRE_V=""; NEWV=""
STEPN=("" "Installing packages" "Downloading panel files" "Installing Python libraries and icons" "Installing Xray" "Configuring SSH" "TLS certificate" "Creating services" "Starting services")
declare -a STS SKN
rep(){ local o="" i; for ((i=0;i<$2;i++)); do o+="$1"; done; printf '%s' "$o"; }
ui_right(){
local n="${NEWV:-$PRE_V}"
if [ "$MODE" = update ]; then
if [ -n "$n" ] && [ "$n" != "${OLDV:-}" ]; then printf 'v%s %s v%s' "${OLDV:-?}" "$g_arr" "$n"; else printf 'v%s' "${OLDV:-?}"; fi
elif [ -n "$n" ]; then printf 'v%s' "$n"; fi
}
banner_s(){
local t="$1" r="$2" col="${3:-$c_c}" pad
pad=$((W-12-${#t}-${#r}-2)); [ "$pad" -lt 1 ] && pad=1
printf ' %s%s%s%s\n' "$col" "$g_tl" "$(rep "$g_h" "$W")" "$g_tr$c_rs"
printf ' %s%s%s  %sisile%s  %s%s%s  %s%s%s%*s%s%s%s  %s%s%s\n' "$col" "$g_v" "$c_rs" "$c_bc" "$c_rs" "$c_d" "$g_arr" "$c_rs" "$c_b" "$t" "$c_rs" "$pad" "" "$c_d" "$r" "$c_rs" "$col" "$g_v" "$c_rs"
printf ' %s%s%s%s%s\n' "$col" "$g_bl" "$(rep "$g_h" "$W")" "$g_br" "$c_rs"
}
ui_mode_title(){ if [ "$MODE" = update ]; then echo Updating; else echo Installing; fi; }
ui_init(){
[ "$UI" = 1 ] || return 0
UIDIR="$(mktemp -d)"; STATEF="$UIDIR/state"; WARNF="$UIDIR/warn"; : > "$WARNF"
exec 9>&1
ALT=1
printf '\e[?1049h' >&9
trap ui_cleanup EXIT
trap ui_interrupt INT TERM HUP
ui_msg "Checking the latest version..."
local re='^[0-9A-Za-z .+_-]{1,32}$'
PRE_V="$(curl -fsSL --max-time 6 -H 'Cache-Control: no-cache' "https://raw.githubusercontent.com/$REPO/$BRANCH/panel/VERSION?t=$(date +%s)" 2>/dev/null | head -n1 | tr -d '\r' || true)"
[[ "$PRE_V" =~ $re ]] || PRE_V=""
}
ui_msg(){
if [ "$UI" = 1 ]; then
{ printf '\e[H\e[2J'; banner_s "$(ui_mode_title)" "$(ui_right)"; printf '\n  %s%s%s\n' "$c_d" "$1" "$c_rs"; } >&9
else echo "$1"; fi
}
ui_stop(){
if [ -n "$TICK" ]; then kill "$TICK" 2>/dev/null || true; wait "$TICK" 2>/dev/null || true; TICK=""; fi
}
ui_leave(){
ui_stop
if [ "$ALT" = 1 ]; then printf '\e[?25h\e[?1049l' >&9; ALT=0; exec 1>&9 2>&9; fi
}
ui_cleanup(){ ui_leave; [ -z "$UIDIR" ] || rm -rf "$UIDIR"; }
ui_interrupt(){ trap - ERR; ui_leave; echo "Interrupted. The installation is incomplete (log: $LOG)."; exit 130; }
ui_abort(){ trap - ERR; ui_leave; echo "$1"; exit 1; }
warn_note(){ printf '%s\n' "$*" >>"$WARNF"; echo "Warning: $*"; }
# ----- questions -----
q_screen(){
local l
{
printf '\e[H\e[2J'; banner_s "$(ui_mode_title)" "$(ui_right)"
printf '\n  %s%s%s\n' "$c_b" "$1" "$c_rs"
printf '%s\n' "$2" | fold -s -w $((W-2)) | while IFS= read -r l; do printf '  %s%s%s\n' "$c_d" "$l" "$c_rs"; done
printf '\n'
[ -z "$3" ] || printf '  %s%s %s%s\n\n' "$c_br" "$g_no" "$3" "$c_rs"
printf '  %s%s%s ' "$c_bc" "$g_arr" "$c_rs"
} >&9
}
q_text(){
# q_text VAR "Title" "Help" "Default" validator filter: asks until the value passes the validator (which prints an error text)
local var="$1" title="$2" help="$3" def="${4:-}" val="${5:-}" flt="${6:-}" err="" v
while true; do
if [ "$UI" = 1 ]; then q_screen "$title" "$help" "$err"; IFS= read -r v </dev/tty || die "cannot read from the terminal"
else [ -z "$err" ] || echo "$err"; IFS= read -rp "$title${def:+ [$def]}: " v </dev/tty; fi
[ -n "$v" ] || v="$def"
[ -z "$flt" ] || v="$("$flt" "$v")"
err=""
if [ -n "$val" ]; then err="$("$val" "$v")"; [ -z "$err" ] || continue; fi
printf -v "$var" '%s' "$v"
return 0
done
}
q_secret(){
local var="$1" title="$2" help="$3" err="${4:-}" v
if [ "$UI" = 1 ]; then q_screen "$title" "$help" "$err"; IFS= read -rs v </dev/tty || die "cannot read from the terminal"
else [ -z "$err" ] || echo "$err"; IFS= read -rsp "$title: " v </dev/tty; echo; fi
printf -v "$var" '%s' "$v"
}
q_password(){
local var="$1" p1 p2 err=""
while true; do
q_secret p1 "Admin password" "At least 10 characters. What you type is hidden." "$err"
if [ "${#p1}" -lt 10 ]; then err="The password must be at least 10 characters."; continue; fi
q_secret p2 "Confirm password" "Type the same password again." ""
if [ "$p1" != "$p2" ]; then err="The passwords do not match, try again."; continue; fi
printf -v "$var" '%s' "$p1"
return 0
done
}
q_yn(){
local v err=""
while true; do
if [ "$UI" = 1 ]; then q_screen "$1" "$2"$'\n\n'"y = yes, Enter = no" "$err"; IFS= read -r v </dev/tty || die "cannot read from the terminal"
else [ -z "$err" ] || echo "$err"; echo "$2"; IFS= read -rp "$1 [y/N]: " v </dev/tty; fi
case "$v" in y|Y) return 0;; ""|n|N) return 1;; esac
err="Type y or n."
done
}
# ----- progress -----
ui_save(){
[ "$UI" = 1 ] || return 0
local i tmp="$STATEF.tmp"
{
for i in 1 2 3 4 5 6 7 8; do echo "S$i=${STS[i]:-pend}"; echo "K$i='${SKN[i]:-}'"; done
echo "STARTED=$STEP_T"; echo "BEGIN=$T0"; echo "RIGHT='$(ui_right)'"
} >"$tmp"
mv -f "$tmp" "$STATEF"
}
ui_draw(){
local f="$1" i s k lab now ndone=0 run=0 t frac pct bw fill buf st el rt="" mm ss
local S1 S2 S3 S4 S5 S6 S7 S8 K1 K2 K3 K4 K5 K6 K7 K8 STARTED BEGIN RIGHT
. "$STATEF" 2>/dev/null || return 0
now=$(printf '%(%s)T' -1)
for i in 1 2 3 4 5 6 7 8; do
eval "s=\$S$i"
case "$s" in done|skip) ndone=$((ndone+1));; run) run=$i;; esac
done
frac=0
if [ "$run" -gt 0 ]; then t=$((now-STARTED)); frac=$((t*90/(t+20))); fi
pct=$(((ndone*100+frac)/8)); [ "$pct" -gt 100 ] && pct=100
bw=$((W-18)); [ "$bw" -gt 40 ] && bw=40
fill=$((pct*bw/100))
el=$((now-BEGIN)); mm=$((el/60)); ss=$((el%60))
buf=$'\e[H'
buf+="$(banner_s "$(ui_mode_title)" "$RIGHT")"$'\n\n'
buf+="  ${c_c}$(rep "$g_full" "$fill")${c_d}$(rep "$g_empty" $((bw-fill)))${c_rs}  ${c_b}$(printf '%3d' "$pct")%${c_rs}  ${c_d}$(printf '%02d:%02d' "$mm" "$ss")${c_rs}"$'\e[K\n\n'
for i in 1 2 3 4 5 6 7 8; do
eval "s=\$S$i; k=\$K$i"
lab="${STEPN[i]}"
case "$s" in
done) st="  ${c_bg}${g_ok}${c_rs}  ${lab}";;
run) st="  ${c_bc}${g_sp[f%${#g_sp[@]}]}${c_rs}  ${c_b}${lab}${c_rs}  ${c_d}$((now-STARTED))s${c_rs}";;
skip) st="  ${c_d}${g_skip}  ${lab} (${k})${c_rs}";;
*) st="  ${c_d}${g_ring}  ${lab}${c_rs}";;
esac
buf+="$st"$'\e[K\n'
done
buf+=$'\n'"  ${c_d}This can take a few minutes. Keep this terminal open.${c_rs}"$'\e[K\n'
buf+="  ${c_d}Log: ${LOG}${c_rs}"$'\e[K\n'$'\e[J'
printf '%s' "$buf"
}
ui_ticker(){
trap - ERR INT TERM HUP EXIT
set +eEu
local f=0
while true; do ui_draw "$f"; f=$((f+1)); sleep 0.15; done
}
ui_progress_start(){
[ "$UI" = 1 ] || return 0
T0=$(printf '%(%s)T' -1); STEP_T=$T0
ui_save
exec 1>>"$LOG" 2>&1
printf '\e[?25l' >&9
ui_ticker >&9 &
TICK=$!
}
step(){
local n="$1" i
for i in 1 2 3 4 5 6 7 8; do if [ "${STS[i]:-}" = run ]; then STS[i]=done; fi; done
STS[n]=run; STEP_T=$(printf '%(%s)T' -1)
if [ "$UI" = 1 ]; then ui_save; else echo "[$n/8] ${STEPN[n]}"; fi
}
step_skip(){
local n="$1" i
for i in 1 2 3 4 5 6 7 8; do if [ "${STS[i]:-}" = run ]; then STS[i]=done; fi; done
STS[n]=skip; SKN[n]="$3"
if [ "$UI" = 1 ]; then ui_save; else echo "[$n/8] $2"; fi
}
step_end(){
local i
for i in 1 2 3 4 5 6 7 8; do if [ "${STS[i]:-}" = run ]; then STS[i]=done; fi; done
ui_save
}
# ----- end screens -----
ui_wrap(){ printf '%s\n' "$1" | fold -s -w $((W-4)) | sed "1s/^/  $2/;1!s/^/    /"; }
ui_fail(){
local why="$1" room lines
ui_stop
room=$((ROWS-17)); [ "$room" -lt 4 ] && room=4; [ "$room" -gt 12 ] && room=12
lines=""
if [ -s "$LOG" ]; then lines="$(tail -n "$room" "$LOG" | cut -c1-$((W-2)) | sed 's/^/    /')"; fi
{
printf '\e[?25h\e[H\e[2J'
banner_s "Failed" "$(ui_right)" "$c_r"
printf '\n  %s%s  %s failed%s\n\n' "$c_br" "$g_no" "$([ "$MODE" = update ] && echo Update || echo Installation)" "$c_rs"
printf '  %s%-8s%s %s\n' "$c_d" "Step" "$c_rs" "$STEP"
printf '%s\n' "$why" | fold -s -w $((W-12)) | sed "1s/^/  ${c_d}Reason${c_rs}   /;1!s/^/            /"
if [ -n "$lines" ]; then printf '\n  %sLog%s  %s(%s)%s\n%s%s%s\n' "$c_b" "$c_rs" "$c_d" "$LOG" "$c_rs" "$c_d" "$lines" "$c_rs"; fi
printf '\n  %sFix the issue, then run the command again.%s\n' "$c_d" "$c_rs"
printf '\n  %sEnter%s  Close the installer\n' "$c_by" "$c_rs"
} >&9
IFS= read -r _ </dev/tty || true
ui_leave
echo "isile $(if [ "$MODE" = update ]; then echo update; else echo installation; fi) failed at step: $STEP"
echo "Reason: $why"
echo "Log: $LOG"
}
ui_success(){
local note l n=0 msg
ui_stop
step_end
if [ "$MODE" = update ]; then msg="isile updated successfully ($OLDV $g_arr $NEWV)"; else msg="isile $NEWV installed successfully"; fi
{
printf '\e[?25h\e[H\e[2J'
banner_s "$([ "$MODE" = update ] && echo Updated || echo Installed)" "v$NEWV" "$c_g"
printf '\n  %s%s  %s%s\n\n' "$c_bg" "$g_ok" "$msg" "$c_rs"
printf '  %s%-10s%s %s%s%s\n' "$c_d" "Panel URL" "$c_rs" "$c_bc" "$PANEL_URL" "$c_rs"
if [ "$MODE" = update ]; then
printf '  %s%-10s%s %s\n' "$c_d" "Accounts" "$c_rs" "admin credentials were not changed"
else
printf '  %s%-10s%s %s\n' "$c_d" "Username" "$c_rs" "$ADMIN_USER"
printf '  %s%-10s%s %s\n' "$c_d" "Password" "$c_rs" "$ADMIN_PASS"
fi
printf '\n'
if [ "$MODE" = install ]; then
if [ -n "$DOMAIN" ]; then
if [ "$PANEL_ACTIVE" = 1 ]; then ui_wrap "Open in the cloud firewall: TCP 80, 443 and your SSH port. The panel is served on 443 from its subdomain, so no panel port is needed." "${c_c}•${c_rs} "; else ui_wrap "Open in the cloud firewall: TCP 80, 443, $PANEL_PORT and your SSH port." "${c_c}•${c_rs} "; fi
ui_wrap "SSH SSL: direct SSH on 80 (no TLS) and 443 (TLS via stunnel)." "${c_c}•${c_rs} "
else
if [ "$SCHEME" = https ]; then ui_wrap "No domain: the panel uses a self-signed certificate (the browser warns once); connections use plain HTTP without TLS." "${c_c}•${c_rs} "; else ui_wrap "No domain: the panel and connections use plain HTTP without TLS." "${c_c}•${c_rs} "; fi
ui_wrap "Open in the cloud firewall: TCP 80, $PANEL_PORT and your SSH port. You can add a domain later from the panel Settings." "${c_c}•${c_rs} "
fi
fi
ui_wrap "Optional services (UDP Custom, VayDNS, SlowDNS) can be added from the panel: Settings > Components." "${c_c}•${c_rs} "
if systemctl is-active --quiet udp-custom 2>/dev/null; then ui_wrap "UDP Custom is running: also open its UDP port (default 36712)." "${c_c}•${c_rs} "; fi
if [ -f /etc/systemd/system/vaydns.service ]; then
if [ -s /etc/vpnpanel/vaydns.env ]; then ui_wrap "VayDNS: open UDP 53 and point the NS record of your tunnel domain at this server." "${c_c}•${c_rs} "
else ui_wrap "VayDNS has no tunnel domain yet: set it in Settings > Components, then add its NS record and open UDP 53." "${c_c}•${c_rs} "; fi
fi
if [ -s "$WARNF" ]; then
printf '\n'
while IFS= read -r l; do n=$((n+1)); [ "$n" -le 5 ] && ui_wrap "$l" "${c_by}!${c_rs} "; done <"$WARNF"
fi
printf '\n  %sEnter%s  Close the installer' "$c_by" "$c_rs"
if [ "$MODE" = install ]; then printf '   %s·%s   %sisile%s  Open the menu' "$c_d" "$c_rs" "$c_bc" "$c_rs"; fi
printf '\n'
} >&9
IFS= read -r _ </dev/tty || true
ui_leave
echo "$msg"
echo "Panel URL: $PANEL_URL"
echo "Type  isile  to open the management menu."
}
die(){
local why="$1"
trap - ERR
if [ "$UI" = 1 ] && [ "$ALT" = 1 ]; then
ui_fail "$why"
else
echo
echo "=================================================="
if [ "$MODE" = update ]; then echo "  UPDATE FAILED"; else echo "  INSTALLATION FAILED"; fi
echo "=================================================="
echo " Step   : $STEP"
echo " Reason : $why"
if [ -s "$LOG" ]; then
echo " Last log lines ($LOG):"
tail -n 12 "$LOG" | sed 's/^/   /'
fi
echo " Fix the issue, then run the command again."
fi
exit 1
}
on_err(){
local code=$?
trap - ERR
die "command failed (exit $code): ${FAILED_CMD:-$2} [line $1]"
}
trap 'on_err $LINENO "$BASH_COMMAND"' ERR
detect_ip(){
local ip
ip="$(curl -fsS4 --max-time 8 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)"
[[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || ip="$(curl -fsS4 --max-time 8 https://api.ipify.org 2>/dev/null | tr -d '[:space:]' || true)"
[[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || ip=""
echo "$ip"
}
dbget(){ python3 -c 'import sqlite3,sys;r=sqlite3.connect(sys.argv[1]).execute("SELECT v FROM settings WHERE k=?",(sys.argv[2],)).fetchone();print(r[0] if r else "")' "$DATA/panel.db" "$1"; }
port_bad(){
# Prints why $1 cannot be the panel port (nothing when it is fine). $2=nginx: a listener that is nginx does not count (re-install).
local p="$1" sp lst
[[ "$p" =~ ^[0-9]{1,5}$ ]] || { echo "it is not a number"; return 0; }
p=$((10#$p))
if [ "$p" -lt 1024 ] || [ "$p" -gt 65535 ]; then echo "it must be between 1024 and 65535"; return 0; fi
sp="$(sshd -T 2>/dev/null | awk '/^port /{print $2; exit}' || true)"
sp="${sp:-22}"
if [ "$p" = "$sp" ]; then echo "it is the SSH port"; return 0; fi
if { [ "$p" -ge 10000 ] && [ "$p" -le 10299 ]; } || [ "$p" = 8000 ] || [ "$p" = 7000 ] || [ "$p" = 7001 ] || [ "$p" = 5300 ] || [ "$p" = 5301 ] || [ "$p" = 5302 ] || [ "$p" = 36712 ]; then echo "it is reserved for an internal service"; return 0; fi
lst=""
if command -v ss >/dev/null 2>&1; then lst="$(ss -H -ltnp "sport = :$p" 2>/dev/null || true)"
elif timeout 2 bash -c "exec 3<>/dev/tcp/127.0.0.1/$p" 2>/dev/null; then lst=busy; fi
if [ "${2:-}" = nginx ]; then lst="$(echo "$lst" | grep -v '"nginx"' || true)"; fi
if [ -n "$lst" ]; then echo "another program is already listening on it"; return 0; fi
}
L(){
echo "+ $*" >>"$LOG"
if ! "$@" >>"$LOG" 2>&1; then FAILED_CMD="$*"; return 1; fi
}
[ "$(id -u)" -eq 0 ] || die "run this script as root"
: > "$LOG"
. /etc/os-release
[ "$ID" = "ubuntu" ] || die "Ubuntu only (found: $ID)"
OLDV="$(cat "$APP/panel/VERSION" 2>/dev/null || echo none)"
ui_init
UDPC=no
VAYDNS=no
VAYDNS_DOM=""
WANT_XRAY=1
WANT_WS=1
SELFSIGNED=no
PANEL_PORT=2096
PANEL_DOM=""
PANEL_CF=0
PANEL_ACTIVE=0
if [ "$MODE" = install ]; then
STEP="reading settings"
v_domain(){ [ -z "$1" ] || [[ "$1" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || echo "That is not a valid domain name."; }
f_lower(){ printf '%s' "$1" | tr 'A-Z' 'a-z' | tr -d ' '; }
v_port(){ local r; r="$(port_bad "$1" nginx)"; [ -z "$r" ] || echo "Port $1 cannot be used: $r."; }
v_user(){ [[ "$1" =~ ^[A-Za-z0-9_.-]{3,32}$ ]] || echo "Use 3-32 characters: letters, digits and _ . -"; }
v_ip(){ [[ "$1" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || echo "Enter an IPv4 address such as 203.0.113.10."; }
is_cf(){
python3 - "$1" <<'PYCF' 2>/dev/null
import ipaddress,sys
N="173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22".split()
sys.exit(0 if any(ipaddress.ip_address(sys.argv[1]) in ipaddress.ip_network(n) for n in N) else 1)
PYCF
}
q_text DOMAIN "Domain" "Enter a domain that points to this server to get HTTPS (TLS)."$'\n'"Press Enter to skip and use the server address without TLS." "" v_domain f_lower
v_pdom(){ local r; r="$(v_domain "$1")"; if [ -n "$r" ]; then echo "$r"; elif [ -n "$1" ] && [ "$1" = "$DOMAIN" ]; then echo "The panel subdomain must be different from the main domain."; fi; }
if [ -n "$DOMAIN" ]; then
if [ -n "${ISILE_PANEL_DOMAIN:-}" ]; then
PANEL_DOM="$(f_lower "$ISILE_PANEL_DOMAIN")"
R="$(v_pdom "$PANEL_DOM")"
[ -z "$R" ] || die "invalid panel subdomain $PANEL_DOM: $R"
else
q_text PANEL_DOM "Panel subdomain" "Optional: open the panel from its own subdomain (for example panel.$DOMAIN) over HTTPS on port 443 instead of a separate port."$'\n'"Create its DNS record first (the Cloudflare proxy works). The main domain used by the protocols is not changed."$'\n'"Press Enter to skip and use a panel port." "" v_pdom f_lower
fi
fi
EMAIL=""
if [ -n "$DOMAIN" ]; then
q_text EMAIL "Email for certificate notices" "Optional: Let's Encrypt sends expiry notices to this address."$'\n'"Press Enter to skip." ""
else
if q_yn "Self-signed certificate" "No domain: the panel is served over plain HTTP unless you create a self-signed certificate."$'\n'"It encrypts the connection, but the browser shows a warning once."$'\n'"Create one for the panel?"; then SELFSIGNED=yes; fi
fi
ask_port(){
if [ -n "${ISILE_PANEL_PORT:-}" ]; then
PANEL_PORT="${ISILE_PANEL_PORT}"
R="$(port_bad "$PANEL_PORT" nginx)"
[ -z "$R" ] || die "invalid panel port $PANEL_PORT: $R"
else
q_text PANEL_PORT "Panel port" "The port the panel listens on."$'\n'"Press Enter for 2096. The Cloudflare proxy supports 2053, 2083, 2087, 2096 and 8443." "2096" v_port
fi
PANEL_PORT=$((10#$PANEL_PORT))
}
# With a panel subdomain the panel is served on 443 and the port is only a fallback (kept at 2096 unless set with ISILE_PANEL_PORT).
if [ -z "$PANEL_DOM" ] || [ -n "${ISILE_PANEL_PORT:-}" ]; then ask_port; fi
q_text ADMIN_USER "Admin username" "The account you sign in to the panel with." "" v_user
q_password ADMIN_PASS
STEP="detecting server address"
ui_msg "Detecting the server address..."
SERVER_IP="$(detect_ip)"
if [ -z "$SERVER_IP" ]; then q_text SERVER_IP "Server public IP address" "The address could not be detected automatically." "" v_ip; fi
[[ "$SERVER_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || die "cannot determine the server address"
if [ -n "$DOMAIN" ]; then
STEP="checking DNS"
ui_msg "Checking DNS for $DOMAIN..."
DOM_IP="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)"
if [ "$SERVER_IP" != "$DOM_IP" ]; then
if is_cf "$DOM_IP"; then
q_yn "Cloudflare proxy detected" "$DOMAIN is behind the Cloudflare proxy (orange cloud), that is why it differs from this server ($SERVER_IP)."$'\n\n'"If certificate issuance fails, switch the record to DNS only (grey cloud), turn off Always Use HTTPS and run the installer again. The panel port must be one Cloudflare proxies: 2053, 2083, 2087, 2096 or 8443. Direct SSH and the other ports do not go through the proxy."$'\n\n'"Continue?" || ui_abort "Cancelled."
else
q_yn "Domain does not point to this server" "$DOMAIN resolves to '${DOM_IP:-nothing}' but this server is $SERVER_IP."$'\n'"The certificate will fail until the A record is fixed."$'\n\n'"Continue anyway?" || ui_abort "Cancelled: the domain does not point to this server."
fi
fi
fi
if [ -n "$PANEL_DOM" ]; then
STEP="checking DNS"
ui_msg "Checking DNS for $PANEL_DOM..."
PD_IP="$(getent ahostsv4 "$PANEL_DOM" | awk 'NR==1{print $1}' || true)"
if [ "$SERVER_IP" = "$PD_IP" ]; then
:
elif [ -n "$PD_IP" ] && is_cf "$PD_IP"; then
PANEL_CF=1
elif q_yn "Panel subdomain does not point to this server" "$PANEL_DOM resolves to '${PD_IP:-nothing}' but this server is $SERVER_IP."$'\n'"Its certificate cannot be issued until the DNS record is fixed."$'\n\n'"Continue anyway? If you answer no, the panel will use a port instead."; then
:
else
PANEL_DOM=""
ask_port
fi
fi
STEP="optional components"
# Optional components (UDP Custom, VayDNS, SlowDNS) are never asked about here: the installer sets up the essentials only and
# they are installed from the panel when needed (Settings > Components). Unattended installs can still request them with
# ISILE_UDPC=yes, ISILE_VAYDNS=yes and ISILE_VAYDNS_DOMAIN=t.example.com.
if [ "${ISILE_UDPC:-}" = yes ]; then UDPC=yes; fi
if [ "$UDPC" = yes ] && [ "$(uname -m)" != x86_64 ] && [ -z "${UDPC_URL:-}" ]; then
warn_note "UDP Custom has no default binary for $(uname -m), skipping it (set UDPC_URL to use your own)."
UDPC=no
fi
if [ "${ISILE_VAYDNS:-}" = yes ]; then VAYDNS=yes; fi
if [ "$VAYDNS" = yes ]; then
case "$(uname -m)" in x86_64|aarch64) ;; *) warn_note "VayDNS has no binary for $(uname -m), skipping it."; VAYDNS=no;; esac
fi
if [ "$VAYDNS" = yes ]; then
VAYDNS_DOM="$(echo "${ISILE_VAYDNS_DOMAIN:-}" | tr 'A-Z' 'a-z' | tr -d ' ')"
if [ -n "$VAYDNS_DOM" ]; then
[[ "$VAYDNS_DOM" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || die "invalid tunnel domain: $VAYDNS_DOM"
[ "$VAYDNS_DOM" != "$DOMAIN" ] || die "the VayDNS tunnel domain must be different from the panel domain"
if [ -n "$PANEL_DOM" ] && { [ "$VAYDNS_DOM" = "$PANEL_DOM" ] || [[ "$PANEL_DOM" == *".$VAYDNS_DOM" ]]; }; then die "the VayDNS tunnel domain must be different from the panel subdomain and cannot be a parent of it"; fi
fi
fi
else
STEP="reading current settings"
[ -f "$DATA/panel.db" ] || die "isile is not installed, run the install command instead"
if [ "$(dbget comp_xray)" = 0 ]; then WANT_XRAY=0; fi
if [ "$(dbget comp_wsbridge)" = 0 ]; then WANT_WS=0; fi
DOMAIN="$(dbget domain)"
PANEL_DOM="$(dbget panel_domain)"
PANEL_PORT="$(dbget port_panel)"
if ! [[ "$PANEL_PORT" =~ ^[0-9]{4,5}$ ]] || [ "$PANEL_PORT" -lt 1024 ] || [ "$PANEL_PORT" -gt 65535 ]; then PANEL_PORT=2080; python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1],timeout=30);c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",("port_panel","2080"));c.commit()' "$DATA/panel.db" || true; fi
SERVER_IP="$(detect_ip)"
EMAIL=""
fi
ui_progress_start
STEP="installing packages"
step 1
L apt-get update -y
L apt-get install -y nginx certbot python3 python3-venv python3-pip curl unzip nftables ufw openssl ca-certificates stunnel4
STUNNEL_BIN="$(command -v stunnel4 || command -v stunnel || true)"
[ -n "$STUNNEL_BIN" ] || die "stunnel was not installed (package stunnel4)"
STEP="creating users and directories"
getent group vpnusers >/dev/null || groupadd vpnusers
id xray >/dev/null 2>&1 || useradd -r -M -s /usr/sbin/nologin xray
install -d -m755 "$APP" /usr/local/etc/xray /var/www/certbot /etc/vpnpanel
install -d -o xray -g xray -m755 /var/log/xray
install -d -m700 "$DATA"
STEP="downloading panel files"
step 2
TMP="$(mktemp -d)"
curl -fsSL -o "$TMP/repo.tgz" "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" || die "cannot download github.com/$REPO (branch $BRANCH): check that the repository is public and the branch name is right"
tar -xz -C "$APP" --strip-components=1 -f "$TMP/repo.tgz" || die "downloaded archive is invalid"
[ -f "$APP/panel/app.py" ] || die "panel/app.py is missing in the repository"
[ -f "$APP/panel/isile.sh" ] || die "panel/isile.sh is missing in the repository"
echo "$REPO $BRANCH" > "$APP/.repo"
NEWV="$(cat "$APP/panel/VERSION" 2>/dev/null || echo unknown)"
STEP="creating python environment"
step 3
L python3 -m venv "$APP/venv"
L "$APP/venv/bin/pip" install -q --no-cache-dir -U -r "$APP/panel/requirements.txt"
STEP="downloading icons"
FA_DIR="$APP/panel/static/fa"
if [ ! -s "$FA_DIR/css/all.min.css" ] || [ ! -s "$FA_DIR/webfonts/fa-solid-900.woff2" ]; then
FA_BASE="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2"
mkdir -p "$FA_DIR/css" "$FA_DIR/webfonts"
if curl -fsSL -o "$FA_DIR/css/all.min.css" "$FA_BASE/css/all.min.css" && curl -fsSL -o "$FA_DIR/webfonts/fa-solid-900.woff2" "$FA_BASE/webfonts/fa-solid-900.woff2"; then
echo "Icons downloaded" >>"$LOG"
else
warn_note "could not download Font Awesome, icons will be missing"
rm -rf "$FA_DIR"
fi
fi
STEP="installing Xray"
if [ "$WANT_XRAY" = 1 ]; then
step 4
bash "$APP/panel/components.sh" install xray >>"$LOG" 2>&1 || die "Xray installation failed"
else
step_skip 4 "Xray was removed from the panel, skipping" "removed from the panel"
fi
rm -rf "$TMP"
STEP="configuring SSH"
step 5
mkdir -p /run/sshd
SSH_PORT="$(sshd -T 2>/dev/null | awk '/^port /{print $2; exit}' || true)"
SSH_PORT="${SSH_PORT:-22}"
SSHD_CONF=/etc/ssh/sshd_config.d/99-vpnpanel.conf
cat > "$SSHD_CONF" <<EOT
PerSourcePenaltyExemptList 127.0.0.1,::1
Match Group vpnusers
PasswordAuthentication yes
AllowTcpForwarding yes
PermitListen none
AllowStreamLocalForwarding no
AllowAgentForwarding no
X11Forwarding no
PermitTTY no
PermitTunnel no
GatewayPorts no
MaxAuthTries 3
ClientAliveInterval 60
ClientAliveCountMax 3
ForceCommand /usr/sbin/nologin
EOT
for OPT in PerSourcePenaltyExemptList PermitListen AllowStreamLocalForwarding; do
sshd -t >>"$LOG" 2>&1 && break
sed -i "/^$OPT/d" "$SSHD_CONF"
done
sshd -t >>"$LOG" 2>&1 || { rm -f "$SSHD_CONF"; die "sshd rejected the generated configuration"; }
systemctl reload ssh >>"$LOG" 2>&1 || true
STEP="issuing TLS certificate"
if [ -n "$DOMAIN" ]; then step 6; else step_skip 6 "No domain, skipping TLS certificate" "no domain"; fi
if [ -n "$DOMAIN" ]; then
NEEDCERT=0
[ -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ] || NEEDCERT=1
[ -z "$PANEL_DOM" ] || [ -s "/etc/letsencrypt/live/$PANEL_DOM/fullchain.pem" ] || NEEDCERT=1
if [ "$NEEDCERT" = 1 ]; then
systemctl stop vpnmux vpnstunnel >>"$LOG" 2>&1 || true
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/conf.d/vpnpanel.conf <<EOT
server {
listen 80 default_server;
listen [::]:80 default_server;
server_name _;
server_tokens off;
location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
location / { return 404; }
}
EOT
L nginx -t || die "nginx configuration test failed"
L systemctl enable nginx
L systemctl restart nginx || die "nginx failed to start (is another service using port 80?)"
if [ ! -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
CB=(certonly --webroot -w /var/www/certbot -d "$DOMAIN" --non-interactive --agree-tos --keep-until-expiring)
if [ -n "$EMAIL" ]; then CB+=(-m "$EMAIL"); else CB+=(--register-unsafely-without-email); fi
L certbot "${CB[@]}" || die "certificate issuance failed (check the DNS A record and that port 80 is open in the cloud firewall)"
[ -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ] || die "certificate file was not created"
fi
if [ -n "$PANEL_DOM" ] && [ ! -s "/etc/letsencrypt/live/$PANEL_DOM/fullchain.pem" ]; then
# The panel subdomain has its own certificate; if it cannot be issued the install goes on with the panel port instead.
CBP=(certonly --webroot -w /var/www/certbot -d "$PANEL_DOM" --non-interactive --agree-tos --keep-until-expiring)
if [ -n "$EMAIL" ]; then CBP+=(-m "$EMAIL"); else CBP+=(--register-unsafely-without-email); fi
if L certbot "${CBP[@]}" && [ -s "/etc/letsencrypt/live/$PANEL_DOM/fullchain.pem" ]; then
:
else
FAILED_CMD=""
warn_note "The certificate for the panel subdomain $PANEL_DOM could not be issued (check its DNS record and Cloudflare Always Use HTTPS). The panel uses port $PANEL_PORT instead: set the subdomain later from the isile menu or the panel Settings."
fi
fi
fi
install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\nsystemctl try-restart vpnstunnel\n' > /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
systemctl enable --now certbot.timer >>"$LOG" 2>&1 || true
fi
STEP="creating services"
step 7
rm -f /etc/logrotate.d/vpnpanel-xray /var/log/xray/access.log /var/lib/vpnpanel/v2claims.json /opt/vpnpanel/panel/v2conn.py
if [ "$WANT_WS" = 1 ]; then
SSH_PORT="$SSH_PORT" bash "$APP/panel/components.sh" install wsbridge >>"$LOG" 2>&1 || die "SSH WebSocket bridge installation failed"
fi
cat > /etc/systemd/system/vpnmux.service <<EOT
[Unit]
Description=SSH SSL multiplexer (ports 80 and 443)
After=network.target
[Service]
User=nobody
Group=nogroup
Environment=SSH_PORT=$SSH_PORT
ExecStart=/usr/bin/python3 $APP/panel/sshmux.py
Restart=always
RestartSec=3
LimitNOFILE=65535
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOT
cat > /etc/systemd/system/vpnstunnel.service <<EOT
[Unit]
Description=TLS front on port 443 (stunnel)
After=network.target vpnmux.service
ConditionPathExists=/etc/vpnpanel/stunnel.conf
[Service]
ExecStart=$STUNNEL_BIN /etc/vpnpanel/stunnel.conf
Restart=always
RestartSec=3
LimitNOFILE=65535
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOT
cat > /etc/systemd/system/vpnpanel.service <<EOT
[Unit]
Description=VPN Panel
After=network.target
[Service]
ExecStart=$APP/venv/bin/python $APP/panel/app.py serve
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
[Install]
WantedBy=multi-user.target
EOT
if [ "$MODE" = install ]; then
PD_ENV=""
if [ -n "$DOMAIN" ] && [ -n "$PANEL_DOM" ] && [ -s "/etc/letsencrypt/live/$PANEL_DOM/fullchain.pem" ]; then PD_ENV="$PANEL_DOM"; fi
VPN_ADMIN_USER="$ADMIN_USER" VPN_ADMIN_PASS="$ADMIN_PASS" VPN_DOMAIN="$DOMAIN" VPN_PANEL_DOMAIN="$PD_ENV" VPN_SERVER_IP="$SERVER_IP" VPN_PANEL_PORT="$PANEL_PORT" "$APP/venv/bin/python" "$APP/panel/app.py" setup >>"$LOG" 2>&1 || die "panel initialization failed"
else
if [ -n "$SERVER_IP" ]; then VPN_SERVER_IP="$SERVER_IP" "$APP/venv/bin/python" "$APP/panel/app.py" setserver >>"$LOG" 2>&1 || true; fi
fi
chmod 600 "$DATA/panel.db"
if [ "$MODE" = install ] && [ "$SELFSIGNED" = yes ]; then
STEP="creating the self-signed certificate"
install -d -m700 /etc/vpnpanel/selfsigned
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout /etc/vpnpanel/selfsigned/key.pem -out /etc/vpnpanel/selfsigned/cert.pem -subj "/CN=$SERVER_IP" -addext "subjectAltName=IP:$SERVER_IP" >>"$LOG" 2>&1 || die "could not create the self-signed certificate"
chmod 600 /etc/vpnpanel/selfsigned/key.pem
chmod 644 /etc/vpnpanel/selfsigned/cert.pem
"$APP/venv/bin/python" "$APP/panel/app.py" setselfsigned >>"$LOG" 2>&1 || die "could not save the self-signed certificate setting"
fi
install -m755 "$APP/panel/isile.sh" /usr/local/bin/isile
STEP="cleaning legacy port settings"
OLDP="$(dbget port_http) $(dbget port_https)"
python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1],timeout=30);[c.execute("DELETE FROM settings WHERE k=?",(k,)) for k in ("port_http","port_https")];c.commit()' "$DATA/panel.db" >>"$LOG" 2>&1 || true
rm -f /etc/vpnpanel/ports.env
for p in $OLDP; do
case "$p" in 80|443|"$PANEL_PORT"|"") ;; *) ufw delete allow "$p/tcp" >>"$LOG" 2>&1 || true;; esac
done
UCF=/usr/local/lib/isile/udp-custom/config.json
if [ -s "$UCF" ]; then
OU="$(grep -oE '"listen"[^,]*' "$UCF" | grep -oE '[0-9]{1,5}' | tail -1 || true)"
if [ -n "$OU" ] && [ "$OU" != 36712 ]; then
sed -i -E 's/("listen"[[:space:]]*:[[:space:]]*"[^"]*:)[0-9]+(")/\136712\2/' "$UCF"
ufw allow 36712/udp >>"$LOG" 2>&1 || true
ufw delete allow "$OU/udp" >>"$LOG" 2>&1 || true
fi
fi
STEP="configuring nginx"
bash "$APP/panel/setdomain.sh" --render "$DOMAIN" >>"$LOG" 2>&1 || die "nginx configuration failed"
PANEL_ACTIVE=0
if [ -n "$DOMAIN" ]; then
PDB="$(dbget panel_domain)"
if [ -n "$PDB" ] && [ "$PDB" != "$DOMAIN" ] && [ -s "/etc/letsencrypt/live/$PDB/fullchain.pem" ]; then PANEL_ACTIVE=1; PANEL_DOM="$PDB"; fi
fi
if [ "$PANEL_ACTIVE" = 1 ] && [ "$PANEL_CF" = 1 ]; then warn_note "The panel subdomain is behind the Cloudflare proxy: set Cloudflare SSL/TLS to Full (strict) or the panel will not open."; fi
if [ "$UDPC" = yes ]; then
STEP="installing UDP Custom"
echo "Installing UDP Custom (optional)"
if ! bash "$APP/panel/components.sh" install udpcustom >>"$LOG" 2>&1; then
warn_note "UDP Custom could not be installed (see $LOG). Continuing without it."
fi
elif [ -x /usr/local/lib/isile/udp-custom/udp-custom ]; then
bash "$APP/panel/components.sh" refresh udpcustom >>"$LOG" 2>&1 || warn_note "could not refresh the UDP Custom service files (see $LOG)"
fi
if [ "$VAYDNS" = yes ]; then
STEP="installing VayDNS"
echo "Installing VayDNS (optional)"
if ! VAYDNS_DOMAIN="$VAYDNS_DOM" bash "$APP/panel/components.sh" install vaydns >>"$LOG" 2>&1; then
warn_note "VayDNS could not be installed (see $LOG). Continuing without it."
fi
elif [ -x /usr/local/lib/isile/vaydns/vaydns-server ]; then
bash "$APP/panel/components.sh" refresh vaydns >>"$LOG" 2>&1 || warn_note "could not refresh the VayDNS service files (see $LOG)"
fi
if [ -x /usr/local/lib/isile/slowdns/vaydns-server ]; then
bash "$APP/panel/components.sh" refresh slowdns >>"$LOG" 2>&1 || warn_note "could not refresh the SlowDNS service files (see $LOG)"
fi
STEP="starting services and firewall"
step 8
L ufw allow "$SSH_PORT/tcp"
L ufw allow 80/tcp
if [ -n "$DOMAIN" ]; then L ufw allow 443/tcp; fi
if [ "$PANEL_ACTIVE" = 1 ]; then
ufw delete allow "$PANEL_PORT/tcp" >>"$LOG" 2>&1 || true
else
L ufw allow "$PANEL_PORT/tcp"
fi
L ufw --force enable
L systemctl daemon-reload
EN="vpnpanel vpnmux"
if [ -f /etc/systemd/system/vpnbridge.service ]; then EN="$EN vpnbridge"; fi
if [ -f /etc/systemd/system/xray.service ]; then EN="$EN xray"; fi
L systemctl enable $EN
if [ -f /etc/systemd/system/vpnbridge.service ]; then L systemctl restart vpnbridge; fi
L systemctl restart vpnpanel
sleep 3
if [ -f /etc/systemd/system/xray.service ]; then L systemctl restart xray; fi
L systemctl restart nginx
L systemctl restart vpnmux
if [ -f /etc/systemd/system/udp-custom.service ]; then L systemctl try-restart udp-custom; fi
if [ -f /etc/systemd/system/vaydns.service ]; then L systemctl try-restart vaydns; fi
if [ -f /etc/systemd/system/slowdns.service ]; then L systemctl try-restart slowdns; fi
if [ -s /etc/vpnpanel/stunnel.conf ]; then
L systemctl enable vpnstunnel
L systemctl restart vpnstunnel
else
systemctl disable --now vpnstunnel >>"$LOG" 2>&1 || true
fi
STEP="verifying services"
"$APP/venv/bin/python" "$APP/panel/app.py" applycomps >>"$LOG" 2>&1 || true
SVCS="$("$APP/venv/bin/python" "$APP/panel/app.py" svcs 2>>"$LOG" || true)"
[ -n "$SVCS" ] || SVCS="vpnpanel vpnmux nginx"
UDPON=no
case " $SVCS " in *" udp-custom "*) UDPON=yes;; esac
VAYON=no
case " $SVCS " in *" vaydns "*) VAYON=yes;; esac
SLOWON=no
case " $SVCS " in *" slowdns "*) SLOWON=yes;; esac
SVCS="$(echo " $SVCS " | sed 's/ udp-custom / /; s/ vaydns / /; s/ slowdns / /')"
for s in $SVCS; do
ok=0
for i in $(seq 1 20); do
if systemctl is-active --quiet "$s"; then ok=1; break; fi
sleep 1
done
if [ "$ok" != 1 ]; then
journalctl -u "$s" -n 12 --no-pager >>"$LOG" 2>&1 || true
die "service $s is not running"
fi
done
if [ "$UDPON" = yes ] && ! systemctl is-active --quiet udp-custom; then
journalctl -u udp-custom -n 12 --no-pager >>"$LOG" 2>&1 || true
warn_note "UDP Custom is not running (optional component, see $LOG). You can remove it from Settings > Components."
fi
if [ "$VAYON" = yes ] && ! systemctl is-active --quiet vaydns; then
journalctl -u vaydns -n 12 --no-pager >>"$LOG" 2>&1 || true
warn_note "VayDNS is not running (optional component, see $LOG). You can remove it from Settings > Components."
fi
if [ "$SLOWON" = yes ] && ! systemctl is-active --quiet slowdns; then
journalctl -u slowdns -n 12 --no-pager >>"$LOG" 2>&1 || true
warn_note "SlowDNS is not running (optional component, see $LOG). You can remove it from Settings > Components."
fi
STEP="verifying connection paths"
install -d /var/www/certbot
CODE=000
for i in $(seq 1 15); do
CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1/.well-known/acme-challenge/isile-probe || true)"
[ "$CODE" = 404 ] && break
sleep 1
done
if [ "$CODE" != 404 ]; then
journalctl -u vpnmux -n 12 --no-pager >>"$LOG" 2>&1 || true
die "port 80 does not answer through the multiplexer (HTTP $CODE)"
fi
if [ -s /etc/vpnpanel/stunnel.conf ]; then
CODE=000
for i in $(seq 1 15); do
CODE="$(curl -ks -o /dev/null -w '%{http_code}' --max-time 5 --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/.well-known/acme-challenge/isile-probe" || true)"
[ "$CODE" = 404 ] && break
sleep 1
done
if [ "$CODE" != 404 ]; then
journalctl -u vpnstunnel -n 12 --no-pager >>"$LOG" 2>&1 || true
die "port 443 does not answer through stunnel (HTTP $CODE)"
fi
fi
SSHB="$(timeout 8 bash -c 'exec 3<>/dev/tcp/127.0.0.1/80; head -c 4 <&3' 2>/dev/null || true)"
[ "$SSHB" = "SSH-" ] || warn_note "direct SSH on port 80 did not answer, SSH SSL without TLS may not work (see $LOG)"
SSHB="$(timeout 8 bash -c 'exec 3<>/dev/tcp/127.0.0.1/10053; head -c 4 <&3' 2>/dev/null || true)"
[ "$SSHB" = "SSH-" ] || warn_note "direct SSH on the VayDNS upstream (127.0.0.1:10053) did not answer, SSH over VayDNS may not work (see $LOG)"
if [ -s /etc/vpnpanel/stunnel.conf ]; then
SSHB="$( (sleep 4) | timeout 10 openssl s_client -quiet -connect 127.0.0.1:443 -servername "$DOMAIN" 2>/dev/null | head -c 4 || true)"
[ "$SSHB" = "SSH-" ] || warn_note "direct SSH over TLS on port 443 did not answer, SSH SSL with TLS may not work (see $LOG)"
fi
if [ -n "$DOMAIN" ]; then SCHEME=https; PUB="$DOMAIN"
elif [ "$(dbget selfsigned)" = 1 ] && [ -s /etc/vpnpanel/selfsigned/cert.pem ]; then SCHEME=https; PUB="${SERVER_IP:-$(dbget server_ip)}"
else SCHEME=http; PUB="${SERVER_IP:-$(dbget server_ip)}"; fi
PANEL_URL="$SCHEME://$PUB:$PANEL_PORT"
if [ "$PANEL_ACTIVE" = 1 ]; then PANEL_URL="https://$PANEL_DOM"; fi
CODE=000
for i in $(seq 1 20); do
if [ "$PANEL_ACTIVE" = 1 ]; then
CODE="$(curl -ks -o /dev/null -w '%{http_code}' --max-time 5 --resolve "$PANEL_DOM:443:127.0.0.1" "https://$PANEL_DOM/login" || true)"
else
CODE="$(curl -ks -o /dev/null -w '%{http_code}' "$SCHEME://127.0.0.1:$PANEL_PORT/login" || true)"
fi
[ "$CODE" = 200 ] && break
sleep 1
done
if [ "$CODE" != 200 ]; then
journalctl -u vpnpanel -n 12 --no-pager >>"$LOG" 2>&1 || true
if [ "$PANEL_ACTIVE" = 1 ]; then die "the panel did not answer on https://$PANEL_DOM (HTTP $CODE)"; fi
die "the panel did not answer on port $PANEL_PORT (HTTP $CODE)"
fi
if [ "$UI" = 1 ]; then
ui_success
else
echo
echo "=================================================="
if [ "$MODE" = update ]; then
echo "  isile updated successfully ($OLDV -> $NEWV)"
echo "=================================================="
echo " Panel URL : $PANEL_URL"
echo " Your admin credentials were not changed."
else
echo "  isile $NEWV installed successfully"
echo "=================================================="
echo " Panel URL : $PANEL_URL"
echo " Username  : $ADMIN_USER"
echo " Password  : $ADMIN_PASS"
echo "--------------------------------------------------"
if [ -n "$DOMAIN" ]; then
if [ "$PANEL_ACTIVE" = 1 ]; then echo " Open ports 80, 443 and your SSH port in the cloud firewall (the panel uses 443 through its subdomain)."; else echo " Open ports 80, 443, $PANEL_PORT and your SSH port in the cloud firewall."; fi
echo " SSH SSL: direct SSH on 80 (no TLS) and 443 (TLS via stunnel)."
else
if [ "$SCHEME" = https ]; then echo " No domain: the panel uses a self-signed certificate (the browser will warn once); connections use plain HTTP without TLS."; else echo " No domain: the panel and connections use plain HTTP without TLS."; fi
echo " Open ports 80, $PANEL_PORT and your SSH port in the cloud firewall."
echo " SSH SSL: direct SSH on 80 (no TLS). TLS needs a domain."
echo " You can add a domain later from the panel Settings."
fi
echo " Optional services (UDP Custom, VayDNS, SlowDNS, ...) are not installed by default: add them from the panel, Settings > Components."
if systemctl is-active --quiet udp-custom; then
echo " UDP Custom is running: also open its UDP port (default 36712) in the cloud firewall."
echo " It can be removed any time from Settings > Components in the panel."
fi
if [ -f /etc/systemd/system/vaydns.service ]; then
if [ -s /etc/vpnpanel/vaydns.env ]; then
echo " VayDNS is installed: open UDP 53 in the cloud firewall and make sure the NS record of your tunnel domain points at this server."
else
echo " VayDNS is installed but has no tunnel domain yet: set it in Settings > Components, then add its NS record and open UDP 53."
fi
fi
echo " Type  isile  to open the management menu (admin account, two-step verification,"
echo " domain, panel subdomain, panel port, services, reset, restart, update and uninstall)."
fi
echo "=================================================="
fi
