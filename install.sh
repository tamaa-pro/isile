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
WANT_XRAY=1
WANT_WS=1
if [ "$MODE" = install ]; then
STEP="reading settings"
read -rp "Domain (press Enter to skip and use the server address without TLS): " DOMAIN </dev/tty
DOMAIN="$(echo "$DOMAIN" | tr 'A-Z' 'a-z' | tr -d ' ')"
EMAIL=""
if [ -n "$DOMAIN" ]; then
[[ "$DOMAIN" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || die "invalid domain: $DOMAIN"
read -rp "Email for certificate notices (optional): " EMAIL </dev/tty
fi
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
echo "Warning: $DOMAIN resolves to '${DOM_IP:-nothing}' but this server is $SERVER_IP"
read -rp "Continue anyway? [y/N]: " YN </dev/tty
[[ "$YN" =~ ^[Yy]$ ]] || die "domain does not point to this server"
fi
fi
STEP="optional components"
if [ "${ISILE_UDPC:-}" = yes ]; then
UDPC=yes
elif [ -z "${ISILE_UDPC:-}" ]; then
echo
echo "=================================================="
echo "  Optional: UDP Custom (SSH over UDP)"
echo "=================================================="
echo " SECURITY WARNING"
echo " UDP Custom is a third-party CLOSED-SOURCE binary (by ePro Dev Team). Its code"
echo " cannot be reviewed, and it is NOT part of this repository or written by it."
echo " It will be downloaded from the upstream repository (branch main, not pinned):"
echo "   ${UDPC_URL:-https://github.com/http-custom/udp-custom/raw/main/bin/udp-custom-linux-amd64}"
echo " The upstream publishes no checksum, so you are trusting whoever controls that"
echo " repository, and the binary may change over time. To limit the risk, it runs as an"
echo " unprivileged user, sandboxed, and any NEW outbound connection it tries to"
echo " open (except to the local SSH server) is blocked by the firewall."
echo " You can remove it at any time from the panel: Settings > Components."
read -rp "Install UDP Custom together with the other services? [y/N]: " YN </dev/tty
if [[ "$YN" =~ ^[Yy]$ ]]; then UDPC=yes; fi
fi
if [ "$UDPC" = yes ] && [ "$(uname -m)" != x86_64 ] && [ -z "${UDPC_URL:-}" ]; then
echo "UDP Custom has no default binary for $(uname -m), skipping it (set UDPC_URL to use your own)."
UDPC=no
fi
else
STEP="reading current settings"
[ -f "$DATA/panel.db" ] || die "isile is not installed, run the install command instead"
if [ "$(dbget comp_xray)" = 0 ]; then WANT_XRAY=0; fi
if [ "$(dbget comp_wsbridge)" = 0 ]; then WANT_WS=0; fi
DOMAIN="$(dbget domain)"
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
if ! sshd -t >>"$LOG" 2>&1; then
sed -i '/PerSourcePenaltyExemptList/d' "$SSHD_CONF"
sshd -t >>"$LOG" 2>&1 || { rm -f "$SSHD_CONF"; die "sshd rejected the generated configuration"; }
fi
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
VPN_ADMIN_USER="$ADMIN_USER" VPN_ADMIN_PASS="$ADMIN_PASS" VPN_DOMAIN="$DOMAIN" VPN_SERVER_IP="$SERVER_IP" "$APP/venv/bin/python" "$APP/panel/app.py" setup >>"$LOG" 2>&1 || die "panel initialization failed"
else
if [ -n "$SERVER_IP" ]; then VPN_SERVER_IP="$SERVER_IP" "$APP/venv/bin/python" "$APP/panel/app.py" setserver >>"$LOG" 2>&1 || true; fi
fi
chmod 600 "$DATA/panel.db"
install -m755 "$APP/panel/isile.sh" /usr/local/bin/isile
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
STEP="starting services and firewall"
echo "[8/8] Starting services"
L ufw allow "$SSH_PORT/tcp"
L ufw allow 80/tcp
if [ -n "$DOMAIN" ]; then L ufw allow 443/tcp; fi
L ufw allow 2080/tcp
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
SVCS="$(echo " $SVCS " | sed 's/ udp-custom / /')"
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
STEP="verifying connection paths"
CODE=000
for i in $(seq 1 15); do
CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1/ || true)"
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
CODE="$(curl -ks -o /dev/null -w '%{http_code}' --max-time 5 --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/" || true)"
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
if [ -s /etc/vpnpanel/stunnel.conf ]; then
SSHB="$( (sleep 4) | timeout 10 openssl s_client -quiet -connect 127.0.0.1:443 -servername "$DOMAIN" 2>/dev/null | head -c 4 || true)"
[ "$SSHB" = "SSH-" ] || echo "Warning: direct SSH over TLS on port 443 did not answer, SSH SSL with TLS may not work (see $LOG)"
fi
if [ -n "$DOMAIN" ]; then SCHEME=https; PUB="$DOMAIN"; else SCHEME=http; PUB="${SERVER_IP:-$(dbget server_ip)}"; fi
CODE=000
for i in $(seq 1 20); do
CODE="$(curl -ks -o /dev/null -w '%{http_code}' "$SCHEME://127.0.0.1:2080/login" || true)"
[ "$CODE" = 200 ] && break
sleep 1
done
if [ "$CODE" != 200 ]; then
journalctl -u vpnpanel -n 12 --no-pager >>"$LOG" 2>&1 || true
die "the panel did not answer on port 2080 (HTTP $CODE)"
fi
echo
echo "=================================================="
if [ "$MODE" = update ]; then
echo "  isile updated successfully ($OLDV -> $NEWV)"
echo "=================================================="
echo " Panel URL : $SCHEME://$PUB:2080"
echo " Your admin credentials were not changed."
else
echo "  isile $NEWV installed successfully"
echo "=================================================="
echo " Panel URL : $SCHEME://$PUB:2080"
echo " Username  : $ADMIN_USER"
echo " Password  : $ADMIN_PASS"
echo "--------------------------------------------------"
if [ -n "$DOMAIN" ]; then
echo " Open ports 80, 443, 2080 and your SSH port in the cloud firewall."
echo " SSH SSL: direct SSH on 80 (no TLS) and 443 (TLS via stunnel)."
else
echo " No domain: the panel and connections use plain HTTP without TLS."
echo " Open ports 80, 2080 and your SSH port in the cloud firewall."
echo " SSH SSL: direct SSH on 80 (no TLS). TLS needs a domain."
echo " You can add a domain later from the panel Settings."
fi
if systemctl is-active --quiet udp-custom; then
echo " UDP Custom is running: also open its UDP port (default 36712) in the cloud firewall."
echo " It can be removed any time from Settings > Components in the panel."
fi
echo " Type  isile  to open the management menu:"
echo "   1) Edit admin credentials"
echo "   2) Show panel info"
echo "   3) Uninstall panel completely"
echo "   4) Update to the latest version"
fi
echo "=================================================="
