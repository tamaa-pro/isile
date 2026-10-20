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
L(){
echo "+ $*" >>"$LOG"
if ! "$@" >>"$LOG" 2>&1; then FAILED_CMD="$*"; return 1; fi
}
[ "$(id -u)" -eq 0 ] || die "run this script as root"
: > "$LOG"
. /etc/os-release
[ "$ID" = "ubuntu" ] || die "Ubuntu only (found: $ID)"
OLDV="$(cat "$APP/panel/VERSION" 2>/dev/null || echo none)"
if [ "$MODE" = install ]; then
STEP="reading settings"
read -rp "Domain (A record must point to this server): " DOMAIN </dev/tty
DOMAIN="$(echo "$DOMAIN" | tr 'A-Z' 'a-z' | tr -d ' ')"
[[ "$DOMAIN" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || die "invalid domain: $DOMAIN"
read -rp "Email for certificate notices (optional): " EMAIL </dev/tty
read -rp "Admin username: " ADMIN_USER </dev/tty
[[ "$ADMIN_USER" =~ ^[A-Za-z0-9_.-]{3,32}$ ]] || die "username must be 3-32 chars of A-Za-z0-9_.-"
read -rsp "Admin password (min 10 chars): " ADMIN_PASS </dev/tty; echo
read -rsp "Confirm password: " ADMIN_PASS2 </dev/tty; echo
[ "$ADMIN_PASS" = "$ADMIN_PASS2" ] || die "passwords do not match"
[ "${#ADMIN_PASS}" -ge 10 ] || die "password is shorter than 10 characters"
STEP="checking DNS"
SERVER_IP="$(curl -fsS4 --max-time 8 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)"
DOM_IP="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)"
if [ -n "$SERVER_IP" ] && [ "$SERVER_IP" != "$DOM_IP" ]; then
echo "Warning: $DOMAIN resolves to '${DOM_IP:-nothing}' but this server is $SERVER_IP"
read -rp "Continue anyway? [y/N]: " YN </dev/tty
[[ "$YN" =~ ^[Yy]$ ]] || die "domain does not point to this server"
fi
else
STEP="reading current settings"
[ -f "$DATA/panel.db" ] || die "isile is not installed, run the install command instead"
DOMAIN="$(python3 -c 'import sqlite3,sys;r=sqlite3.connect(sys.argv[1]).execute("SELECT v FROM settings WHERE k=?",("domain",)).fetchone();print(r[0] if r else "")' "$DATA/panel.db")"
[ -n "$DOMAIN" ] || die "cannot read the domain from the panel database"
EMAIL=""
fi
STEP="installing packages"
echo "[1/8] Installing packages"
L apt-get update -y
L apt-get install -y nginx certbot python3 python3-venv python3-pip curl unzip nftables ufw openssl ca-certificates
STEP="creating users and directories"
getent group vpnusers >/dev/null || groupadd vpnusers
id xray >/dev/null 2>&1 || useradd -r -M -s /usr/sbin/nologin xray
install -d -m755 "$APP" /usr/local/etc/xray /var/www/certbot
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
echo "[4/8] Installing Xray"
if [ ! -x /usr/local/bin/xray ]; then
case "$(uname -m)" in x86_64) XA=64;; aarch64) XA=arm64-v8a;; *) die "unsupported architecture $(uname -m)";; esac
XU="https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-$XA.zip"
curl -fsSL -o "$TMP/x.zip" "$XU" || die "cannot download Xray"
curl -fsSL -o "$TMP/x.dgst" "$XU.dgst" || die "cannot download Xray checksum"
EXP="$(grep -i 'sha2-256\|sha256' "$TMP/x.dgst" | grep -oE '[0-9a-fA-F]{64}' | head -1 | tr 'A-F' 'a-f' || true)"
ACT="$(sha256sum "$TMP/x.zip" | cut -d' ' -f1)"
[ -n "$EXP" ] && [ "$EXP" = "$ACT" ] || die "Xray checksum mismatch"
L unzip -oq "$TMP/x.zip" -d "$TMP/x"
install -m755 "$TMP/x/xray" /usr/local/bin/xray
install -d /usr/local/share/xray
install -m644 "$TMP/x/geoip.dat" "$TMP/x/geosite.dat" /usr/local/share/xray/
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
echo "[6/8] TLS certificate"
if [ ! -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
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
printf '#!/bin/sh\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
systemctl enable --now certbot.timer >>"$LOG" 2>&1 || true
STEP="creating services"
echo "[7/8] Creating services"
cat > /etc/systemd/system/xray.service <<EOT
[Unit]
Description=Xray
After=network.target
[Service]
User=xray
Group=xray
Environment=XRAY_LOCATION_ASSET=/usr/local/share/xray
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
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
cat > /etc/systemd/system/vpnbridge.service <<EOT
[Unit]
Description=SSH WebSocket bridge
After=network.target
[Service]
User=nobody
Group=nogroup
Environment=SSH_PORT=$SSH_PORT
ExecStart=/usr/bin/python3 $APP/panel/wsbridge.py
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
VPN_ADMIN_USER="$ADMIN_USER" VPN_ADMIN_PASS="$ADMIN_PASS" VPN_DOMAIN="$DOMAIN" "$APP/venv/bin/python" "$APP/panel/app.py" setup >>"$LOG" 2>&1 || die "panel initialization failed"
fi
chmod 600 "$DATA/panel.db"
install -m755 "$APP/panel/isile.sh" /usr/local/bin/isile
WS='proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $remote_addr; proxy_read_timeout 1d; proxy_send_timeout 1d; proxy_buffering off;'
SSL="ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem; ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem; ssl_protocols TLSv1.2 TLSv1.3; ssl_session_cache shared:vpnssl:10m; ssl_session_timeout 1d; ssl_session_tickets off;"
SSHWS='if ($http_upgrade = "") { return 404; } limit_req zone=vpnws burst=40 nodelay; limit_conn vpnconn 100; proxy_pass http://127.0.0.1:10022;'
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/conf.d/vpnpanel.conf <<EOT
limit_req_zone \$binary_remote_addr zone=vpnlogin:10m rate=5r/s;
limit_req_zone \$binary_remote_addr zone=vpnws:10m rate=20r/s;
limit_conn_zone \$binary_remote_addr zone=vpnconn:10m;
server {
listen 80 default_server;
listen [::]:80 default_server;
server_name _;
server_tokens off;
location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
location ^~ /vless { proxy_pass http://127.0.0.1:10011; $WS }
location ^~ /vmess { proxy_pass http://127.0.0.1:10013; $WS }
location ^~ /trojan { proxy_pass http://127.0.0.1:10012; $WS }
location / { $SSHWS $WS }
}
server {
listen 443 ssl default_server;
listen [::]:443 ssl default_server;
server_name _;
server_tokens off;
$SSL
location ^~ /vless { proxy_pass http://127.0.0.1:10001; $WS }
location ^~ /vmess { proxy_pass http://127.0.0.1:10003; $WS }
location ^~ /trojan { proxy_pass http://127.0.0.1:10002; $WS }
location / { $SSHWS $WS }
}
server {
listen 2080 ssl;
listen [::]:2080 ssl;
server_name _;
server_tokens off;
client_max_body_size 64k;
$SSL
add_header Strict-Transport-Security "max-age=31536000" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header Content-Security-Policy "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" always;
location = /login { limit_req zone=vpnlogin burst=10 nodelay; proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-Proto https; }
location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-Proto https; }
}
EOT
L nginx -t || die "nginx configuration test failed"
STEP="starting services and firewall"
echo "[8/8] Starting services"
L ufw allow "$SSH_PORT/tcp"
L ufw allow 80/tcp
L ufw allow 443/tcp
L ufw allow 2080/tcp
L ufw --force enable
L systemctl daemon-reload
L systemctl enable vpnpanel vpnbridge xray
L systemctl restart vpnbridge
L systemctl restart vpnpanel
sleep 3
L systemctl restart xray
L systemctl reload nginx
STEP="verifying services"
for s in vpnpanel vpnbridge xray nginx; do
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
CODE=000
for i in $(seq 1 20); do
CODE="$(curl -ks -o /dev/null -w '%{http_code}' https://127.0.0.1:2080/login || true)"
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
echo " Panel URL : https://$DOMAIN:2080"
echo " Your admin credentials were not changed."
else
echo "  isile $NEWV installed successfully"
echo "=================================================="
echo " Panel URL : https://$DOMAIN:2080"
echo " Username  : $ADMIN_USER"
echo " Password  : $ADMIN_PASS"
echo "--------------------------------------------------"
echo " Open ports 80, 443, 2080 and your SSH port in the cloud firewall."
echo " Type  isile  to open the management menu:"
echo "   1) Edit admin credentials"
echo "   2) Show panel info"
echo "   3) Uninstall panel completely"
echo "   4) Update to the latest version"
fi
echo "=================================================="
