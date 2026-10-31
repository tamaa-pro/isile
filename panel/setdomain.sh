#!/usr/bin/env bash
set -Eeuo pipefail
APP=/opt/vpnpanel
LOG=/var/log/isile-install.log
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
DATA=/var/lib/vpnpanel
UDPC=/usr/local/lib/isile/udp-custom
dbget(){
[ -f "$DATA/panel.db" ] || return 0
python3 -c 'import sqlite3,sys;r=sqlite3.connect(sys.argv[1]).execute("SELECT v FROM settings WHERE k=?",(sys.argv[2],)).fetchone();print(r[0] if r else "")' "$DATA/panel.db" "$1" 2>/dev/null || true
}
dbset(){
[ -f "$DATA/panel.db" ] || return 0
python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1],timeout=30);c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(sys.argv[2],sys.argv[3]));c.commit()' "$DATA/panel.db" "$1" "$2"
}
pget(){
local v
v="$(dbget "port_$1")"
if [[ "$v" =~ ^[0-9]{1,5}$ ]] && [ "$v" -ge 1 ] && [ "$v" -le 65535 ]; then echo "$v"; else echo "$2"; fi
}
render(){
local d="${1:-}" tls=0 LST SSL HSTS PROTO WS SSHWS RIP PH PS PP
PH="$(pget http 80)"; PS="$(pget https 443)"; PP="$(pget panel 2080)"
if [ -n "$d" ] && [ -s "/etc/letsencrypt/live/$d/fullchain.pem" ]; then tls=1; fi
WS='proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $remote_addr; proxy_read_timeout 1d; proxy_send_timeout 1d; proxy_buffering off;'
SSHWS='if ($http_upgrade = "") { return 404; } limit_req zone=vpnws burst=40 nodelay; limit_conn vpnconn 100; proxy_pass http://127.0.0.1:10022;'
RIP='set_real_ip_from 127.0.0.1; real_ip_header proxy_protocol;'
LST="listen $PP; listen [::]:$PP;"
SSL=""
HSTS=""
PROTO=http
if [ "$tls" = 1 ]; then
LST="listen $PP ssl; listen [::]:$PP ssl;"
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
server {
listen 127.0.0.1:10080 proxy_protocol;
$RIP
server_name _;
server_tokens off;
location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
location ^~ /vless { proxy_pass http://127.0.0.1:10011; $WS }
location ^~ /vmess { proxy_pass http://127.0.0.1:10013; $WS }
location ^~ /trojan { proxy_pass http://127.0.0.1:10012; $WS }
location / { $SSHWS $WS }
}
EOT
if [ "$tls" = 1 ]; then
cat <<EOT
server {
listen 127.0.0.1:10443 proxy_protocol;
$RIP
server_name _;
server_tokens off;
location ^~ /vless { proxy_pass http://127.0.0.1:10001; $WS }
location ^~ /vmess { proxy_pass http://127.0.0.1:10003; $WS }
location ^~ /trojan { proxy_pass http://127.0.0.1:10002; $WS }
location / { $SSHWS $WS }
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
location ^~ /api/public/ { limit_req zone=vpnlogin burst=30 nodelay; proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-Proto $PROTO; }
location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-Proto $PROTO; }
}
EOT
} > /etc/nginx/conf.d/vpnpanel.conf
if [ "$tls" = 1 ]; then
install -d -m755 /etc/vpnpanel
cat > /etc/vpnpanel/stunnel.conf <<EOT
foreground = yes
pid =
debug = 4
sslVersionMin = TLSv1.2
TIMEOUTidle = 86400
socket = l:TCP_NODELAY=1
socket = r:TCP_NODELAY=1
socket = l:SO_KEEPALIVE=1
[isile-tls]
accept = 0.0.0.0:$PS
connect = 127.0.0.1:10444
cert = /etc/letsencrypt/live/$d/fullchain.pem
key = /etc/letsencrypt/live/$d/privkey.pem
protocol = proxy
EOT
chmod 600 /etc/vpnpanel/stunnel.conf
else
rm -f /etc/vpnpanel/stunnel.conf
fi
install -d -m755 /etc/vpnpanel
printf 'MUX_PUBLIC_PORT=%s\nMUX_HTTPS_PORT=%s\n' "$PH" "$PS" > /etc/vpnpanel/ports.env
chmod 644 /etc/vpnpanel/ports.env
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
ufw allow "$(pget https 443)/tcp" || true
install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\nsystemctl try-restart vpnstunnel\n' > /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
systemctl enable --now certbot.timer || true
systemctl daemon-reload
systemctl enable vpnstunnel
systemctl restart vpnstunnel
sleep 1
systemctl is-active --quiet vpnstunnel || { echo "stunnel (vpnstunnel) failed to start on port 443"; journalctl -u vpnstunnel -n 10 --no-pager; exit 1; }
VPN_DOMAIN="$d" "$APP/venv/bin/python" "$APP/panel/app.py" setdomain
systemctl reload nginx
echo "domain $d enabled"
systemctl restart vpnpanel
}
ports_apply(){
local nh="$1" ns="$2" np="$3" nu="$4" d oh os op ou v
for v in "$nh" "$ns" "$np" "$nu"; do [[ "$v" =~ ^[0-9]{1,5}$ ]] || { echo "invalid port: $v"; exit 1; }; done
d="$(dbget domain)"
oh="$(pget http 80)"; os="$(pget https 443)"; op="$(pget panel 2080)"
ou=0
if [ -s "$UDPC/config.json" ]; then ou="$(grep -oE '"listen"[^,]*' "$UDPC/config.json" | grep -oE '[0-9]{1,5}' | tail -1 || true)"; ou="${ou:-0}"; fi
setudp(){
if [ "$1" -gt 0 ] && [ -s "$UDPC/config.json" ]; then
sed -i -E 's/("listen"[[:space:]]*:[[:space:]]*"[^"]*:)[0-9]+(")/\1'"$1"'\2/' "$UDPC/config.json"
systemctl try-restart udp-custom || true
fi
}
reload_all(){
render "$d" || return 1
systemctl daemon-reload
systemctl reload nginx || systemctl restart nginx || return 1
systemctl restart vpnmux || return 1
if [ -s /etc/vpnpanel/stunnel.conf ]; then systemctl restart vpnstunnel || return 1; fi
sleep 1
systemctl is-active --quiet vpnmux || return 1
if [ -s /etc/vpnpanel/stunnel.conf ]; then systemctl is-active --quiet vpnstunnel || return 1; fi
return 0
}
ufw allow "$nh/tcp" || true
if [ -n "$d" ]; then ufw allow "$ns/tcp" || true; fi
ufw allow "$np/tcp" || true
if [ "$nu" -gt 0 ]; then ufw allow "$nu/udp" || true; fi
dbset port_http "$nh"; dbset port_https "$ns"; dbset port_panel "$np"
setudp "$nu"
if ! reload_all; then
echo "applying the new ports failed, restoring the previous ones"
journalctl -u vpnmux -n 10 --no-pager || true
dbset port_http "$oh"; dbset port_https "$os"; dbset port_panel "$op"
setudp "$ou"
reload_all || true
exit 1
fi
for v in "$oh" "$os" "$op"; do
case " $nh $ns $np " in *" $v "*) ;; *) ufw delete allow "$v/tcp" || true;; esac
done
if [ "$ou" -gt 0 ] && [ "$ou" != "$nu" ]; then ufw delete allow "$ou/udp" || true; fi
echo "ports updated: http=$nh https=$ns panel=$np udp=$nu"
}
case "${1:-}" in
--render) render "${2:-}";;
--ports) ports_apply "${2:-}" "${3:-}" "${4:-}" "${5:-0}";;
*) apply "${1:-}" "${2:-}";;
esac
