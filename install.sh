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
die(){
echo
echo "=================================================="
if [ "$MODE" = update ]; then echo "  UPDATE FAILED"; else echo "  INSTALLATION FAILED"; fi
echo "=================================================="
echo " Step   : $STEP"
echo " Reason : $1"
if [ -s "$LOG" ]; then
echo " Last log lines ($LOG):"
tail -n 12 "$LOG" | sed 's/^/   /'
fi
echo " Fix the issue, then run the command again."
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
UDPC=no
VAYDNS=no
VAYDNS_DOM=""
WANT_XRAY=1
WANT_WS=1
SELFSIGNED=no
PANEL_PORT=2096
if [ "$MODE" = install ]; then
STEP="reading settings"
read -rp "Domain (press Enter to skip and use the server address without TLS): " DOMAIN </dev/tty
DOMAIN="$(echo "$DOMAIN" | tr 'A-Z' 'a-z' | tr -d ' ')"
EMAIL=""
if [ -n "$DOMAIN" ]; then
[[ "$DOMAIN" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || die "invalid domain: $DOMAIN"
read -rp "Email for certificate notices (optional): " EMAIL </dev/tty
else
echo "No domain: the panel will be served over plain HTTP unless you create a self-signed certificate."
echo "(A self-signed certificate encrypts the connection but the browser will show a warning.)"
read -rp "Create a self-signed certificate for the panel (HTTPS on the panel port)? [y/N]: " YN </dev/tty
if [[ "$YN" =~ ^[Yy]$ ]]; then SELFSIGNED=yes; fi
fi
if [ -n "${ISILE_PANEL_PORT:-}" ]; then
PANEL_PORT="${ISILE_PANEL_PORT}"
R="$(port_bad "$PANEL_PORT" nginx)"
[ -z "$R" ] || die "invalid panel port $PANEL_PORT: $R"
else
while true; do
read -rp "Panel port (press Enter for 2096; Cloudflare proxy supports 2053, 2083, 2087, 2096, 8443): " PANEL_PORT </dev/tty
PANEL_PORT="${PANEL_PORT:-2096}"
R="$(port_bad "$PANEL_PORT" nginx)"
[ -z "$R" ] && break
echo "Port $PANEL_PORT cannot be used: $R"
done
fi
PANEL_PORT=$((10#$PANEL_PORT))
read -rp "Admin username: " ADMIN_USER </dev/tty
[[ "$ADMIN_USER" =~ ^[A-Za-z0-9_.-]{3,32}$ ]] || die "username must be 3-32 chars of A-Za-z0-9_.-"
read -rsp "Admin password (min 10 chars): " ADMIN_PASS </dev/tty; echo
read -rsp "Confirm password: " ADMIN_PASS2 </dev/tty; echo
[ "$ADMIN_PASS" = "$ADMIN_PASS2" ] || die "passwords do not match"
[ "${#ADMIN_PASS}" -ge 10 ] || die "password is shorter than 10 characters"
STEP="detecting server address"
SERVER_IP="$(detect_ip)"
if [ -z "$SERVER_IP" ]; then read -rp "Server public IP address: " SERVER_IP </dev/tty; fi
[[ "$SERVER_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || die "cannot determine the server address"
if [ -n "$DOMAIN" ]; then
STEP="checking DNS"
DOM_IP="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)"
if [ "$SERVER_IP" != "$DOM_IP" ]; then
if python3 - "$DOM_IP" <<'PYCF' 2>/dev/null
import ipaddress,sys
N="173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22".split()
sys.exit(0 if any(ipaddress.ip_address(sys.argv[1]) in ipaddress.ip_network(n) for n in N) else 1)
PYCF
then
echo "Notice: $DOMAIN is behind the Cloudflare proxy (orange cloud), that is why it differs from this server ($SERVER_IP)."
echo "  - Certificate issuance can fail: if it does, switch the record to DNS only (grey cloud) and turn off Always Use HTTPS, then run the installer again."
echo "  - The panel port must be one Cloudflare proxies: 2053, 2083, 2087, 2096 or 8443."
echo "  - Direct SSH and the other ports do not go through the proxy: use a grey-cloud name for them."
read -rp "Continue? [y/N]: " YN </dev/tty
[[ "$YN" =~ ^[Yy]$ ]] || die "cancelled"
else
echo "Warning: $DOMAIN resolves to '${DOM_IP:-nothing}' but this server is $SERVER_IP"
read -rp "Continue anyway? [y/N]: " YN </dev/tty
[[ "$YN" =~ ^[Yy]$ ]] || die "domain does not point to this server"
fi
fi
fi
STEP="optional components"
# Optional components (UDP Custom, VayDNS, SlowDNS) are never asked about here: the installer sets up the essentials only and
# they are installed from the panel when needed (Settings > Components). Unattended installs can still request them with
# ISILE_UDPC=yes, ISILE_VAYDNS=yes and ISILE_VAYDNS_DOMAIN=t.example.com.
if [ "${ISILE_UDPC:-}" = yes ]; then UDPC=yes; fi
if [ "$UDPC" = yes ] && [ "$(uname -m)" != x86_64 ] && [ -z "${UDPC_URL:-}" ]; then
echo "UDP Custom has no default binary for $(uname -m), skipping it (set UDPC_URL to use your own)."
UDPC=no
fi
if [ "${ISILE_VAYDNS:-}" = yes ]; then VAYDNS=yes; fi
if [ "$VAYDNS" = yes ]; then
case "$(uname -m)" in x86_64|aarch64) ;; *) echo "VayDNS has no binary for $(uname -m), skipping it."; VAYDNS=no;; esac
fi
if [ "$VAYDNS" = yes ]; then
VAYDNS_DOM="$(echo "${ISILE_VAYDNS_DOMAIN:-}" | tr 'A-Z' 'a-z' | tr -d ' ')"
if [ -n "$VAYDNS_DOM" ]; then
[[ "$VAYDNS_DOM" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || die "invalid tunnel domain: $VAYDNS_DOM"
[ "$VAYDNS_DOM" != "$DOMAIN" ] || die "the VayDNS tunnel domain must be different from the panel domain"
fi
fi
else
STEP="reading current settings"
[ -f "$DATA/panel.db" ] || die "isile is not installed, run the install command instead"
if [ "$(dbget comp_xray)" = 0 ]; then WANT_XRAY=0; fi
if [ "$(dbget comp_wsbridge)" = 0 ]; then WANT_WS=0; fi
DOMAIN="$(dbget domain)"
PANEL_PORT="$(dbget port_panel)"
if ! [[ "$PANEL_PORT" =~ ^[0-9]{4,5}$ ]] || [ "$PANEL_PORT" -lt 1024 ] || [ "$PANEL_PORT" -gt 65535 ]; then PANEL_PORT=2080; python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1],timeout=30);c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",("port_panel","2080"));c.commit()' "$DATA/panel.db" || true; fi
SERVER_IP="$(detect_ip)"
EMAIL=""
fi
STEP="installing packages"
echo "[1/8] Installing packages"
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
echo "[2/8] Downloading panel files"
TMP="$(mktemp -d)"
curl -fsSL -o "$TMP/repo.tgz" "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" || die "cannot download github.com/$REPO (branch $BRANCH): check that the repository is public and the branch name is right"
tar -xz -C "$APP" --strip-components=1 -f "$TMP/repo.tgz" || die "downloaded archive is invalid"
[ -f "$APP/panel/app.py" ] || die "panel/app.py is missing in the repository"
[ -f "$APP/panel/isile.sh" ] || die "panel/isile.sh is missing in the repository"
echo "$REPO $BRANCH" > "$APP/.repo"
NEWV="$(cat "$APP/panel/VERSION" 2>/dev/null || echo unknown)"
STEP="creating python environment"
echo "[3/8] Installing Python libraries and icons"
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
echo "Warning: could not download Font Awesome, icons will be missing"
rm -rf "$FA_DIR"
fi
fi
STEP="installing Xray"
if [ "$WANT_XRAY" = 1 ]; then
echo "[4/8] Installing Xray"
bash "$APP/panel/components.sh" install xray >>"$LOG" 2>&1 || die "Xray installation failed"
else
echo "[4/8] Xray was removed from the panel, skipping"
fi
rm -rf "$TMP"
STEP="configuring SSH"
echo "[5/8] Configuring SSH"
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
if [ -n "$DOMAIN" ]; then echo "[6/8] TLS certificate"; else echo "[6/8] No domain, skipping TLS certificate"; fi
if [ -n "$DOMAIN" ]; then
if [ ! -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
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
CB=(certonly --webroot -w /var/www/certbot -d "$DOMAIN" --non-interactive --agree-tos --keep-until-expiring)
if [ -n "$EMAIL" ]; then CB+=(-m "$EMAIL"); else CB+=(--register-unsafely-without-email); fi
L certbot "${CB[@]}" || die "certificate issuance failed (check the DNS A record and that port 80 is open in the cloud firewall)"
[ -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ] || die "certificate file was not created"
fi
install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\nsystemctl try-restart vpnstunnel\n' > /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
systemctl enable --now certbot.timer >>"$LOG" 2>&1 || true
fi
STEP="creating services"
echo "[7/8] Creating services"
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
VPN_ADMIN_USER="$ADMIN_USER" VPN_ADMIN_PASS="$ADMIN_PASS" VPN_DOMAIN="$DOMAIN" VPN_SERVER_IP="$SERVER_IP" VPN_PANEL_PORT="$PANEL_PORT" "$APP/venv/bin/python" "$APP/panel/app.py" setup >>"$LOG" 2>&1 || die "panel initialization failed"
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
if [ "$UDPC" = yes ]; then
STEP="installing UDP Custom"
echo "Installing UDP Custom (optional)"
if ! bash "$APP/panel/components.sh" install udpcustom >>"$LOG" 2>&1; then
echo "Warning: UDP Custom could not be installed (see $LOG). Continuing without it."
fi
elif [ -x /usr/local/lib/isile/udp-custom/udp-custom ]; then
bash "$APP/panel/components.sh" refresh udpcustom >>"$LOG" 2>&1 || echo "Warning: could not refresh the UDP Custom service files (see $LOG)"
fi
if [ "$VAYDNS" = yes ]; then
STEP="installing VayDNS"
echo "Installing VayDNS (optional)"
if ! VAYDNS_DOMAIN="$VAYDNS_DOM" bash "$APP/panel/components.sh" install vaydns >>"$LOG" 2>&1; then
echo "Warning: VayDNS could not be installed (see $LOG). Continuing without it."
fi
elif [ -x /usr/local/lib/isile/vaydns/vaydns-server ]; then
bash "$APP/panel/components.sh" refresh vaydns >>"$LOG" 2>&1 || echo "Warning: could not refresh the VayDNS service files (see $LOG)"
fi
if [ -x /usr/local/lib/isile/slowdns/vaydns-server ]; then
bash "$APP/panel/components.sh" refresh slowdns >>"$LOG" 2>&1 || echo "Warning: could not refresh the SlowDNS service files (see $LOG)"
fi
STEP="starting services and firewall"
echo "[8/8] Starting services"
L ufw allow "$SSH_PORT/tcp"
L ufw allow 80/tcp
if [ -n "$DOMAIN" ]; then L ufw allow 443/tcp; fi
L ufw allow "$PANEL_PORT/tcp"
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
echo "Warning: UDP Custom is not running (optional component, see $LOG). You can remove it from Settings > Components."
fi
if [ "$VAYON" = yes ] && ! systemctl is-active --quiet vaydns; then
journalctl -u vaydns -n 12 --no-pager >>"$LOG" 2>&1 || true
echo "Warning: VayDNS is not running (optional component, see $LOG). You can remove it from Settings > Components."
fi
if [ "$SLOWON" = yes ] && ! systemctl is-active --quiet slowdns; then
journalctl -u slowdns -n 12 --no-pager >>"$LOG" 2>&1 || true
echo "Warning: SlowDNS is not running (optional component, see $LOG). You can remove it from Settings > Components."
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
[ "$SSHB" = "SSH-" ] || echo "Warning: direct SSH on port 80 did not answer, SSH SSL without TLS may not work (see $LOG)"
SSHB="$(timeout 8 bash -c 'exec 3<>/dev/tcp/127.0.0.1/10053; head -c 4 <&3' 2>/dev/null || true)"
[ "$SSHB" = "SSH-" ] || echo "Warning: direct SSH on the VayDNS upstream (127.0.0.1:10053) did not answer, SSH over VayDNS may not work (see $LOG)"
if [ -s /etc/vpnpanel/stunnel.conf ]; then
SSHB="$( (sleep 4) | timeout 10 openssl s_client -quiet -connect 127.0.0.1:443 -servername "$DOMAIN" 2>/dev/null | head -c 4 || true)"
[ "$SSHB" = "SSH-" ] || echo "Warning: direct SSH over TLS on port 443 did not answer, SSH SSL with TLS may not work (see $LOG)"
fi
if [ -n "$DOMAIN" ]; then SCHEME=https; PUB="$DOMAIN"
elif [ "$(dbget selfsigned)" = 1 ] && [ -s /etc/vpnpanel/selfsigned/cert.pem ]; then SCHEME=https; PUB="${SERVER_IP:-$(dbget server_ip)}"
else SCHEME=http; PUB="${SERVER_IP:-$(dbget server_ip)}"; fi
CODE=000
for i in $(seq 1 20); do
CODE="$(curl -ks -o /dev/null -w '%{http_code}' "$SCHEME://127.0.0.1:$PANEL_PORT/login" || true)"
[ "$CODE" = 200 ] && break
sleep 1
done
if [ "$CODE" != 200 ]; then
journalctl -u vpnpanel -n 12 --no-pager >>"$LOG" 2>&1 || true
die "the panel did not answer on port $PANEL_PORT (HTTP $CODE)"
fi
echo
echo "=================================================="
if [ "$MODE" = update ]; then
echo "  isile updated successfully ($OLDV -> $NEWV)"
echo "=================================================="
echo " Panel URL : $SCHEME://$PUB:$PANEL_PORT"
echo " Your admin credentials were not changed."
else
echo "  isile $NEWV installed successfully"
echo "=================================================="
echo " Panel URL : $SCHEME://$PUB:$PANEL_PORT"
echo " Username  : $ADMIN_USER"
echo " Password  : $ADMIN_PASS"
echo "--------------------------------------------------"
if [ -n "$DOMAIN" ]; then
echo " Open ports 80, 443, $PANEL_PORT and your SSH port in the cloud firewall."
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
echo " domain, panel port, services, reset, restart, update and uninstall)."
fi
echo "=================================================="
