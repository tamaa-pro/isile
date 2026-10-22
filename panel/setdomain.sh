#!/usr/bin/env bash
set -Eeuo pipefail
APP=/opt/vpnpanel
LOG=/var/log/isile-install.log
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
render(){
local d="${1:-}" tls=0 LST SSL HSTS PROTO WS SSHWS PUB
if [ -n "$d" ] && [ -s "/etc/letsencrypt/live/$d/fullchain.pem" ]; then tls=1; fi
WS='proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $remote_addr; proxy_read_timeout 1d; proxy_send_timeout 1d; proxy_buffering off;'
SSHWS='if ($http_upgrade = "") { rewrite "^/([a-z][a-z0-9_]{2,19})$" /_pub/$1 last; } if ($http_upgrade = "") { return 404; } limit_req zone=vpnws burst=40 nodelay; limit_conn vpnconn 100; proxy_pass http://127.0.0.1:10022;'
PUB='location ^~ /_pub/ { internal; limit_req zone=vpnpub burst=20 nodelay; proxy_pass http://127.0.0.1:8000/p/; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-Proto $scheme; }'
LST='listen 2080; listen [::]:2080;'
SSL=""
HSTS=""
PROTO=http
if [ "$tls" = 1 ]; then
LST='listen 2080 ssl; listen [::]:2080 ssl;'
SSL="ssl_certificate /etc/letsencrypt/live/$d/fullchain.pem; ssl_certificate_key /etc/letsencrypt/live/$d/privkey.pem; ssl_protocols TLSv1.2 TLSv1.3; ssl_session_cache shared:vpnssl:10m; ssl_session_timeout 1d; ssl_session_tickets off;"
HSTS='add_header Strict-Transport-Security "max-age=31536000" always;'
PROTO=https
fi
rm -f /etc/nginx/sites-enabled/default
{
cat <<EOT
limit_req_zone \$binary_remote_addr zone=vpnlogin:10m rate=5r/s;
limit_req_zone \$binary_remote_addr zone=vpnws:10m rate=20r/s;
limit_conn_zone \$binary_remote_addr zone=vpnconn:10m;
limit_req_zone \$binary_remote_addr zone=vpnpub:10m rate=5r/s;
server {
listen 80 default_server;
listen [::]:80 default_server;
server_name _;
server_tokens off;
location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
location = /vless { proxy_pass http://127.0.0.1:10011; $WS }
location ^~ /vless/ { proxy_pass http://127.0.0.1:10011; $WS }
location = /vmess { proxy_pass http://127.0.0.1:10013; $WS }
location ^~ /vmess/ { proxy_pass http://127.0.0.1:10013; $WS }
location = /trojan { proxy_pass http://127.0.0.1:10012; $WS }
location ^~ /trojan/ { proxy_pass http://127.0.0.1:10012; $WS }
location / { $SSHWS $WS }
$PUB
}
EOT
if [ "$tls" = 1 ]; then
cat <<EOT
server {
listen 443 ssl default_server;
listen [::]:443 ssl default_server;
server_name _;
server_tokens off;
$SSL
location = /vless { proxy_pass http://127.0.0.1:10001; $WS }
location ^~ /vless/ { proxy_pass http://127.0.0.1:10001; $WS }
location = /vmess { proxy_pass http://127.0.0.1:10003; $WS }
location ^~ /vmess/ { proxy_pass http://127.0.0.1:10003; $WS }
location = /trojan { proxy_pass http://127.0.0.1:10002; $WS }
location ^~ /trojan/ { proxy_pass http://127.0.0.1:10002; $WS }
location / { $SSHWS $WS }
$PUB
}
EOT
fi
cat <<EOT
server {
$LST
server_name _;
server_tokens off;
client_max_body_size 64k;
$SSL
$HSTS
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header Content-Security-Policy "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" always;
location = /login { limit_req zone=vpnlogin burst=10 nodelay; proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-Proto $PROTO; }
location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-Proto $PROTO; }
}
EOT
} > /etc/nginx/conf.d/vpnpanel.conf
nginx -t
}
apply(){
local d="${1:-}" e="${2:-}"
: > "$LOG"
exec >>"$LOG" 2>&1
[[ "$d" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || { echo "invalid domain: $d"; exit 1; }
install -d /var/www/certbot
if [ ! -s "/etc/letsencrypt/live/$d/fullchain.pem" ]; then
CB=(certonly --webroot -w /var/www/certbot -d "$d" --non-interactive --agree-tos --keep-until-expiring)
if [ -n "$e" ]; then CB+=(-m "$e"); else CB+=(--register-unsafely-without-email); fi
certbot "${CB[@]}" || { echo "certificate issuance failed (check the DNS A record and that port 80 is open in the cloud firewall)"; exit 1; }
[ -s "/etc/letsencrypt/live/$d/fullchain.pem" ] || { echo "certificate file was not created"; exit 1; }
fi
render "$d" || { echo "nginx configuration test failed"; exit 1; }
ufw allow 443/tcp || true
install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
systemctl enable --now certbot.timer || true
VPN_DOMAIN="$d" "$APP/venv/bin/python" "$APP/panel/app.py" setdomain
systemctl reload nginx
echo "domain $d enabled"
systemctl restart vpnpanel
}
case "${1:-}" in
--render) render "${2:-}";;
*) apply "${1:-}" "${2:-}";;
esac
