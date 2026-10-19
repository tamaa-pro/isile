#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
REPO="${VPNPANEL_REPO:-tamaa-pro/isile}"
BRANCH="${VPNPANEL_BRANCH:-main}"
APP=/opt/vpnpanel
DATA=/var/lib/vpnpanel
[ "$(id -u)" -eq 0 ] || { echo "Run as root"; exit 1; }
. /etc/os-release
[ "$ID" = "ubuntu" ] || { echo "Ubuntu only"; exit 1; }
read -rp "Domain (A record must point to this server): " DOMAIN </dev/tty
DOMAIN="$(echo "$DOMAIN" | tr 'A-Z' 'a-z' | tr -d ' ')"
[[ "$DOMAIN" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || { echo "Invalid domain"; exit 1; }
read -rp "Email for certificate notices (optional): " EMAIL </dev/tty
read -rp "Admin username: " ADMIN_USER </dev/tty
[[ "$ADMIN_USER" =~ ^[A-Za-z0-9_.-]{3,32}$ ]] || { echo "Username: 3-32 chars of A-Za-z0-9_.-"; exit 1; }
read -rsp "Admin password (min 10 chars): " ADMIN_PASS </dev/tty; echo
read -rsp "Confirm password: " ADMIN_PASS2 </dev/tty; echo
[ "$ADMIN_PASS" = "$ADMIN_PASS2" ] || { echo "Passwords do not match"; exit 1; }
[ "${#ADMIN_PASS}" -ge 10 ] || { echo "Password too short"; exit 1; }
SERVER_IP="$(curl -fsS4 --max-time 8 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)"
DOM_IP="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)"
if [ -n "$SERVER_IP" ] && [ "$SERVER_IP" != "$DOM_IP" ]; then
echo "Warning: $DOMAIN resolves to '${DOM_IP:-nothing}' but this server is $SERVER_IP"
read -rp "Continue anyway? [y/N]: " YN </dev/tty
[[ "$YN" =~ ^[Yy]$ ]] || exit 1
fi
apt-get update -y
apt-get install -y nginx certbot python3 python3-venv python3-pip curl unzip nftables ufw openssl ca-certificates
getent group vpnusers >/dev/null || groupadd vpnusers
id xray >/dev/null 2>&1 || useradd -r -M -s /usr/sbin/nologin xray
install -d -m755 "$APP" /usr/local/etc/xray /var/www/certbot
install -d -m700 "$DATA"
curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" | tar -xz -C "$APP" --strip-components=1
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --no-cache-dir -r "$APP/panel/requirements.txt"
case "$(uname -m)" in x86_64) XA=64;; aarch64) XA=arm64-v8a;; *) echo "Unsupported architecture"; exit 1;; esac
TMP="$(mktemp -d)"
XU="https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-$XA.zip"
curl -fsSL -o "$TMP/x.zip" "$XU"
curl -fsSL -o "$TMP/x.dgst" "$XU.dgst"
EXP="$(grep -i 'sha2-256\|sha256' "$TMP/x.dgst" | grep -oE '[0-9a-fA-F]{64}' | head -1 | tr 'A-F' 'a-f')"
ACT="$(sha256sum "$TMP/x.zip" | cut -d' ' -f1)"
[ -n "$EXP" ] && [ "$EXP" = "$ACT" ] || { echo "Xray checksum mismatch"; exit 1; }
unzip -oq "$TMP/x.zip" -d "$TMP/x"
install -m755 "$TMP/x/xray" /usr/local/bin/xray
install -d /usr/local/share/xray
install -m644 "$TMP/x/geoip.dat" "$TMP/x/geosite.dat" /usr/local/share/xray/
rm -rf "$TMP"
SSH_PORT="$(sshd -T 2>/dev/null | awk '/^port /{print $2; exit}')"
SSH_PORT="${SSH_PORT:-22}"
SSHD_CONF=/etc/ssh/sshd_config.d/99-vpnpanel.conf
cat > "$SSHD_CONF" <<EOF
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
EOF
if ! sshd -t 2>/dev/null; then
sed -i '/PerSourcePenaltyExemptList/d' "$SSHD_CONF"
sshd -t || { rm -f "$SSHD_CONF"; echo "sshd config invalid"; exit 1; }
fi
systemctl reload ssh 2>/dev/null || true
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/conf.d/vpnpanel.conf <<EOF
server {
listen 80 default_server;
listen [::]:80 default_server;
server_name _;
server_tokens off;
location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
location / { return 404; }
}
EOF
nginx -t
systemctl enable nginx
systemctl restart nginx
CB=(certonly --webroot -w /var/www/certbot -d "$DOMAIN" --non-interactive --agree-tos --keep-until-expiring)
if [ -n "$EMAIL" ]; then CB+=(-m "$EMAIL"); else CB+=(--register-unsafely-without-email); fi
certbot "${CB[@]}"
[ -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ] || { echo "Certificate was not issued"; exit 1; }
install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
systemctl enable --now certbot.timer 2>/dev/null || true
cat > /etc/systemd/system/xray.service <<EOF
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
EOF
cat > /etc/systemd/system/vpnbridge.service <<EOF
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
EOF
cat > /etc/systemd/system/vpnpanel.service <<EOF
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
EOF
VPN_ADMIN_USER="$ADMIN_USER" VPN_ADMIN_PASS="$ADMIN_PASS" VPN_DOMAIN="$DOMAIN" "$APP/venv/bin/python" "$APP/panel/app.py" setup
chmod 600 "$DATA/panel.db"
WS='proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_read_timeout 1d; proxy_send_timeout 1d; proxy_buffering off;'
SSL="ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem; ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem; ssl_protocols TLSv1.2 TLSv1.3; ssl_session_cache shared:vpnssl:10m; ssl_session_timeout 1d; ssl_session_tickets off;"
SSHWS='if ($http_upgrade = "") { return 404; } limit_req zone=vpnws burst=40 nodelay; limit_conn vpnconn 100; proxy_pass http://127.0.0.1:10022;'
cat > /etc/nginx/conf.d/vpnpanel.conf <<EOF
limit_req_zone \$binary_remote_addr zone=vpnlogin:10m rate=5r/s;
limit_req_zone \$binary_remote_addr zone=vpnws:10m rate=20r/s;
limit_conn_zone \$binary_remote_addr zone=vpnconn:10m;
server {
listen 80 default_server;
listen [::]:80 default_server;
server_name _;
server_tokens off;
location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
location / { $SSHWS $WS }
}
server {
listen 443 ssl default_server;
listen [::]:443 ssl default_server;
server_name _;
server_tokens off;
$SSL
location ^~ /vless { proxy_pass http://127.0.0.1:10001; $WS }
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
add_header Content-Security-Policy "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" always;
location = /login { limit_req zone=vpnlogin burst=10 nodelay; proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-Proto https; }
location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-Proto https; }
}
EOF
nginx -t
ufw allow "$SSH_PORT/tcp"
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 2080/tcp
ufw --force enable
systemctl daemon-reload
systemctl enable --now vpnpanel vpnbridge
sleep 3
systemctl enable xray
systemctl restart xray
systemctl reload nginx
echo "Panel: https://$DOMAIN:2080"
echo "SSH WS: $DOMAIN:80 and $DOMAIN:443 | VLESS path /vless | Trojan path /trojan"
