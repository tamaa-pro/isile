#!/usr/bin/env bash
set -Eeuo pipefail
APP=/opt/vpnpanel
DATA=/var/lib/vpnpanel
dbget(){ python3 -c 'import sqlite3,sys;r=sqlite3.connect(sys.argv[1],timeout=10).execute("SELECT v FROM settings WHERE k=?",(sys.argv[2],)).fetchone();print(r[0] if r else "")' "$DATA/panel.db" "$1" 2>/dev/null || true; }
LOG=/var/log/isile-install.log
DOMAIN_RE='^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$'
[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
# Cloudflare edge ranges: the real visitor address is trusted from CF-Connecting-IP only when the TCP peer is one of them.
cf_geo(){
local n
echo 'geo $isile_cfpeer {'
echo 'default 0;'
for n in 173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22 2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 2405:8100::/32 2a06:98c0::/29 2c0f:f248::/32; do echo "$n 1;"; done
echo '}'
echo 'map "$isile_cfpeer:$http_cf_connecting_ip" $isile_ip {'
echo 'default $remote_addr;'
echo '"~^1:(?<cfip>[0-9A-Fa-f.:]+)$" $cfip;'
echo '}'
}
# The panel itself (security headers and proxy locations), shared by the port listener and the subdomain server.
panel_inner(){
cat <<EOT
client_max_body_size 64k;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header Content-Security-Policy "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" always;
location = /login { limit_req zone=vpnlogin burst=10 nodelay; proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$isile_ip; proxy_set_header X-Forwarded-Proto $PROTO; }
location ^~ /api/public/ { limit_req zone=vpnlogin burst=30 nodelay; proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$isile_ip; proxy_set_header X-Forwarded-Proto $PROTO; }
location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$isile_ip; proxy_set_header X-Forwarded-Proto $PROTO; }
EOT
}
# Prints the HTTP status of the panel login page through the path that is really in use (subdomain on 443, or the panel port).
panel_probe(){
local md pd pp
md="$(dbget domain)"; pd="$(dbget panel_domain)"; pp="$(dbget port_panel)"
[[ "$pp" =~ ^[0-9]{4,5}$ ]] || pp=2080
if [ -n "$md" ] && [ -n "$pd" ] && [ -s "/etc/letsencrypt/live/$md/fullchain.pem" ] && [ -s "/etc/letsencrypt/live/$pd/fullchain.pem" ]; then
curl -ks -o /dev/null -w '%{http_code}' --max-time 4 --resolve "$pd:443:127.0.0.1" "https://$pd/login" || true
elif [ -n "$md" ]; then
curl -ks -o /dev/null -w '%{http_code}' --max-time 4 "https://127.0.0.1:$pp/login" || true
else
curl -ks -o /dev/null -w '%{http_code}' --max-time 4 "http://127.0.0.1:$pp/login" || true
fi
}
render(){
local d="${1:-}" tls=0 pdok=0 PD PP LST SSL HSTS PROTO WS SSHWS RIP GRPC_COMMON XH DON DURL DECOY DRE STUN
if [ -n "$d" ] && [ -s "/etc/letsencrypt/live/$d/fullchain.pem" ]; then tls=1; fi
# Panel subdomain: served on 443 (stunnel picks its certificate by SNI, nginx routes it by Host). Used only while its certificate exists.
PD="$(dbget panel_domain)"
if [ "$tls" = 1 ] && [ -n "$PD" ] && [[ "$PD" =~ $DOMAIN_RE ]] && [ "$PD" != "$d" ] && [ -s "/etc/letsencrypt/live/$PD/fullchain.pem" ] && [ -s "/etc/letsencrypt/live/$PD/privkey.pem" ]; then pdok=1; fi
WS='proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $remote_addr; proxy_read_timeout 1d; proxy_send_timeout 1d; proxy_buffering off;'
# What a plain visitor (browser, curl) gets from the domain: nothing by default (connection closed, 444).
# Optional: classic 404 page, or a redirect to a decoy site. Chosen in the panel (decoy_on / decoy_url).
DON="$(dbget decoy_on)"
DURL="$(dbget decoy_url)"
DRE='^https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~%/?=&:@+-]*)?$'
DECOY='return 444;'
if [ "$DON" = 1 ]; then
DECOY='return 404;'
if [ -n "$DURL" ] && [ "${#DURL}" -le 300 ] && [[ "$DURL" =~ $DRE ]]; then DECOY="return 302 $DURL;"; fi
fi
SSHWS='if ($http_upgrade = "") { '"$DECOY"' } limit_req zone=vpnws burst=40 nodelay; limit_conn vpnconn 100; proxy_pass http://127.0.0.1:10022;'
RIP='set_real_ip_from 127.0.0.1; real_ip_header proxy_protocol;'
GRPC_COMMON='client_max_body_size 0; client_body_timeout 1d; grpc_read_timeout 1d; grpc_send_timeout 1d; grpc_socket_keepalive on; grpc_set_header X-Real-IP $remote_addr;'
# XHTTP: HTTP/1.1 clients go through proxy_pass without buffering, HTTP/2 clients through grpc_pass (same as gRPC, recommended by Xray)
XH='proxy_http_version 1.1; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $remote_addr; proxy_buffering off; proxy_request_buffering off; client_max_body_size 0; client_body_timeout 1d; proxy_read_timeout 1d; proxy_send_timeout 1d;'
PP="$(dbget port_panel)"
[[ "$PP" =~ ^[0-9]{4,5}$ ]] && [ "$PP" -ge 1024 ] && [ "$PP" -le 65535 ] || PP=2080
LST="listen $PP; listen [::]:$PP;"
SSL=""
HSTS=""
PROTO=http
if [ "$tls" = 1 ]; then
LST="listen $PP ssl; listen [::]:$PP ssl;"
SSL="ssl_certificate /etc/letsencrypt/live/$d/fullchain.pem; ssl_certificate_key /etc/letsencrypt/live/$d/privkey.pem; ssl_protocols TLSv1.2 TLSv1.3; ssl_session_cache shared:vpnssl:10m; ssl_session_timeout 1d; ssl_session_tickets off;"
HSTS='add_header Strict-Transport-Security "max-age=31536000" always;'
PROTO=https
elif [ -z "$d" ] && [ "$(dbget selfsigned)" = 1 ] && [ -s /etc/vpnpanel/selfsigned/cert.pem ] && [ -s /etc/vpnpanel/selfsigned/key.pem ]; then
LST="listen $PP ssl; listen [::]:$PP ssl;"
SSL="ssl_certificate /etc/vpnpanel/selfsigned/cert.pem; ssl_certificate_key /etc/vpnpanel/selfsigned/key.pem; ssl_protocols TLSv1.2 TLSv1.3; ssl_session_cache shared:vpnssl:10m; ssl_session_timeout 1d; ssl_session_tickets off;"
PROTO=https
fi
rm -f /etc/nginx/sites-enabled/default
if [ -f /etc/nginx/conf.d/vpnpanel.conf ]; then cp -f /etc/nginx/conf.d/vpnpanel.conf /etc/nginx/conf.d/vpnpanel.conf.bak; fi
{
cat <<EOT
limit_req_zone \$binary_remote_addr zone=vpnlogin:10m rate=5r/s;
limit_req_zone \$binary_remote_addr zone=vpnws:10m rate=20r/s;
limit_conn_zone \$binary_remote_addr zone=vpnconn:10m;
EOT
cf_geo
cat <<EOT
server {
listen 127.0.0.1:10080 proxy_protocol;
$RIP
server_name _;
server_tokens off;
location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
location ^~ /vless-xhttp { proxy_pass http://127.0.0.1:10211; $XH }
location ^~ /vmess-xhttp { proxy_pass http://127.0.0.1:10213; $XH }
location ^~ /trojan-xhttp { proxy_pass http://127.0.0.1:10212; $XH }
location ^~ /vless { proxy_pass http://127.0.0.1:10011; $WS }
location ^~ /vmess { proxy_pass http://127.0.0.1:10013; $WS }
location ^~ /trojan { proxy_pass http://127.0.0.1:10012; $WS }
location / { $SSHWS $WS }
}
EOT
if [ "$pdok" = 1 ]; then
cat <<EOT
server {
listen 127.0.0.1:10080 proxy_protocol;
$RIP
server_name $PD;
server_tokens off;
location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
location / { return 301 https://\$host\$request_uri; }
}
EOT
fi
cat <<EOT
server {
listen 127.0.0.1:10081 http2 proxy_protocol;
$RIP
server_name _;
server_tokens off;
$GRPC_COMMON
location ^~ /vless-grpc { grpc_pass grpc://127.0.0.1:10111; }
location ^~ /vmess-grpc { grpc_pass grpc://127.0.0.1:10113; }
location ^~ /trojan-grpc { grpc_pass grpc://127.0.0.1:10112; }
location ^~ /vless-xhttp { grpc_pass grpc://127.0.0.1:10211; }
location ^~ /vmess-xhttp { grpc_pass grpc://127.0.0.1:10213; }
location ^~ /trojan-xhttp { grpc_pass grpc://127.0.0.1:10212; }
location / { $DECOY }
}
EOT
if [ "$tls" = 1 ]; then
cat <<EOT
server {
listen 127.0.0.1:10443 proxy_protocol;
$RIP
server_name _;
server_tokens off;
location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }
location ^~ /vless-xhttp { proxy_pass http://127.0.0.1:10201; $XH }
location ^~ /vmess-xhttp { proxy_pass http://127.0.0.1:10203; $XH }
location ^~ /trojan-xhttp { proxy_pass http://127.0.0.1:10202; $XH }
location ^~ /vless { proxy_pass http://127.0.0.1:10001; $WS }
location ^~ /vmess { proxy_pass http://127.0.0.1:10003; $WS }
location ^~ /trojan { proxy_pass http://127.0.0.1:10002; $WS }
location / { $SSHWS $WS }
}
server {
listen 127.0.0.1:10442 http2 proxy_protocol;
$RIP
server_name _;
server_tokens off;
$GRPC_COMMON
location ^~ /vless-grpc { grpc_pass grpc://127.0.0.1:10101; }
location ^~ /vmess-grpc { grpc_pass grpc://127.0.0.1:10103; }
location ^~ /trojan-grpc { grpc_pass grpc://127.0.0.1:10102; }
location ^~ /vless-xhttp { grpc_pass grpc://127.0.0.1:10201; }
location ^~ /vmess-xhttp { grpc_pass grpc://127.0.0.1:10203; }
location ^~ /trojan-xhttp { grpc_pass grpc://127.0.0.1:10202; }
location / { $DECOY }
}
EOT
if [ "$pdok" = 1 ]; then
cat <<EOT
server {
listen 127.0.0.1:10443 proxy_protocol;
$RIP
server_name $PD;
server_tokens off;
add_header Strict-Transport-Security "max-age=31536000" always;
$(panel_inner)
}
EOT
fi
fi
if [ "$pdok" != 1 ]; then
cat <<EOT
server {
$LST
server_name _;
server_tokens off;
$SSL
$HSTS
$(panel_inner)
}
EOT
fi
} > /etc/nginx/conf.d/vpnpanel.conf
if [ "$tls" = 1 ]; then
STUN="foreground = yes
pid =
debug = 4
sslVersionMin = TLSv1.2
TIMEOUTidle = 86400
socket = l:TCP_NODELAY=1
socket = r:TCP_NODELAY=1
socket = l:SO_KEEPALIVE=1
[isile-tls]
accept = 0.0.0.0:443
connect = 127.0.0.1:10444
cert = /etc/letsencrypt/live/$d/fullchain.pem
key = /etc/letsencrypt/live/$d/privkey.pem
protocol = proxy"
if [ "$pdok" = 1 ]; then
# Name-based virtual services (SNI): the panel subdomain gets its own certificate, the main domain keeps its own.
# Any other name (or none) falls back to the first service above.
STUN="$STUN

[isile-main]
sni = isile-tls:$d
connect = 127.0.0.1:10444
cert = /etc/letsencrypt/live/$d/fullchain.pem
key = /etc/letsencrypt/live/$d/privkey.pem
protocol = proxy

[isile-panel]
sni = isile-tls:$PD
connect = 127.0.0.1:10444
cert = /etc/letsencrypt/live/$PD/fullchain.pem
key = /etc/letsencrypt/live/$PD/privkey.pem
protocol = proxy"
fi
fi
if ! nginx -t; then
if [ -f /etc/nginx/conf.d/vpnpanel.conf.bak ]; then mv -f /etc/nginx/conf.d/vpnpanel.conf.bak /etc/nginx/conf.d/vpnpanel.conf; fi
return 1
fi
rm -f /etc/nginx/conf.d/vpnpanel.conf.bak
if [ "$tls" = 1 ]; then
install -d -m755 /etc/vpnpanel
printf '%s\n' "$STUN" > /etc/vpnpanel/stunnel.conf.new
chmod 600 /etc/vpnpanel/stunnel.conf.new
mv -f /etc/vpnpanel/stunnel.conf.new /etc/vpnpanel/stunnel.conf
else
rm -f /etc/vpnpanel/stunnel.conf
fi
}
apply(){
local d="${1:-}" e="${2:-}"
: > "$LOG"
exec >>"$LOG" 2>&1
[[ "$d" =~ $DOMAIN_RE ]] || { echo "invalid domain: $d"; exit 1; }
[ "$d" != "$(dbget panel_domain)" ] || { echo "$d is the panel subdomain, choose a different main domain"; exit 1; }
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
printf '#!/bin/sh\nsystemctl reload nginx\nsystemctl try-restart vpnstunnel\n' > /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/vpnpanel-nginx.sh
systemctl enable --now certbot.timer || true
systemctl daemon-reload
systemctl enable vpnstunnel
systemctl restart vpnstunnel || true
sleep 1
systemctl is-active --quiet vpnstunnel || { echo "stunnel (vpnstunnel) failed to start on port 443"; journalctl -u vpnstunnel -n 10 --no-pager; exit 1; }
VPN_DOMAIN="$d" "$APP/venv/bin/python" "$APP/panel/app.py" setdomain
systemctl reload nginx || true
echo "domain $d enabled"
systemctl restart vpnpanel
PP="$(dbget port_panel)"
[[ "$PP" =~ ^[0-9]{4,5}$ ]] || PP=2080
CODE=000
for i in $(seq 1 20); do
CODE="$(panel_probe)"
[ "$CODE" = 200 ] && break
sleep 1
done
if [ "$CODE" != 200 ]; then
echo "the panel does not answer (HTTP $CODE), panel port $PP"
nginx -t 2>&1 || true
ss -ltnp 2>&1 | grep -E ":($PP|443|80) " || true
journalctl -u nginx -n 8 --no-pager 2>&1 || true
journalctl -u vpnpanel -n 8 --no-pager 2>&1 || true
exit 1
fi
}
pd_set(){ VPN_PANEL_DOMAIN="$1" "$APP/venv/bin/python" "$APP/panel/app.py" setpaneldomain; }
# Restores the previous panel subdomain setting and the matching nginx and stunnel configuration.
pd_rollback(){
local old="$1" md="$2" PP
pd_set "$old" || true
render "$md" || true
systemctl restart vpnstunnel || true
systemctl reload nginx || true
PP="$(dbget port_panel)"
[[ "$PP" =~ ^[0-9]{4,5}$ ]] || PP=2080
if [ -z "$old" ]; then ufw allow "$PP/tcp" || true; fi
}
apply_panel(){
local d="${1:-}" e="${2:-}" md old t PP CODE i
: > "$LOG"
exec >>"$LOG" 2>&1
md="$(dbget domain)"
[ -n "$md" ] && [ -s "/etc/letsencrypt/live/$md/fullchain.pem" ] || { echo "set the main domain first: the panel subdomain is served over HTTPS on port 443"; exit 1; }
[[ "$d" =~ $DOMAIN_RE ]] || { echo "invalid domain: $d"; exit 1; }
[ "$d" != "$md" ] || { echo "the panel subdomain must be different from the main domain"; exit 1; }
for t in "$(dbget vaydns_domain)" "$(dbget slowdns_domain)"; do
if [ -n "$t" ] && { [ "$d" = "$t" ] || [[ "$d" == *".$t" ]]; }; then echo "$d belongs to a DNS tunnel domain ($t), choose another name"; exit 1; fi
done
old="$(dbget panel_domain)"
install -d /var/www/certbot
if [ ! -s "/etc/letsencrypt/live/$d/fullchain.pem" ]; then
CB=(certonly --webroot -w /var/www/certbot -d "$d" --non-interactive --agree-tos --keep-until-expiring)
if [ -n "$e" ]; then CB+=(-m "$e"); else CB+=(--register-unsafely-without-email); fi
certbot "${CB[@]}" || { echo "certificate issuance failed for $d (check its DNS record, that port 80 is open and that Cloudflare Always Use HTTPS is off)"; exit 1; }
[ -s "/etc/letsencrypt/live/$d/fullchain.pem" ] || { echo "certificate file was not created"; exit 1; }
fi
pd_set "$d" || { echo "could not save the panel subdomain"; exit 1; }
if ! render "$md"; then
pd_rollback "$old" "$md"
echo "nginx configuration test failed, nothing was changed"
exit 1
fi
ufw allow 443/tcp || true
systemctl enable vpnstunnel || true
systemctl restart vpnstunnel || true
systemctl reload nginx || true
sleep 1
if ! systemctl is-active --quiet vpnstunnel; then
journalctl -u vpnstunnel -n 10 --no-pager || true
pd_rollback "$old" "$md"
echo "stunnel (vpnstunnel) failed to start with the panel subdomain, the previous setup was restored"
exit 1
fi
CODE=000
for i in $(seq 1 20); do
CODE="$(panel_probe)"
[ "$CODE" = 200 ] && break
sleep 1
done
if [ "$CODE" != 200 ]; then
echo "the panel does not answer on https://$d/login (HTTP $CODE), the previous setup was restored"
nginx -t 2>&1 || true
journalctl -u vpnstunnel -n 8 --no-pager 2>&1 || true
journalctl -u vpnpanel -n 8 --no-pager 2>&1 || true
pd_rollback "$old" "$md"
exit 1
fi
PP="$(dbget port_panel)"
[[ "$PP" =~ ^[0-9]{4,5}$ ]] || PP=2080
ufw delete allow "$PP/tcp" || true
if [ -n "$old" ] && [ "$old" != "$d" ]; then certbot delete --cert-name "$old" --non-interactive || true; fi
echo "panel subdomain $d enabled, the panel port $PP is closed"
}
apply_panel_off(){
local md old PP CODE i
: > "$LOG"
exec >>"$LOG" 2>&1
md="$(dbget domain)"
old="$(dbget panel_domain)"
[ -n "$old" ] || { echo "no panel subdomain is set"; exit 0; }
pd_set "" || { echo "could not clear the panel subdomain"; exit 1; }
if ! render "$md"; then
pd_set "$old" || true
render "$md" || true
echo "nginx configuration test failed, nothing was changed"
exit 1
fi
PP="$(dbget port_panel)"
[[ "$PP" =~ ^[0-9]{4,5}$ ]] || PP=2080
ufw allow "$PP/tcp" || true
systemctl restart vpnstunnel || true
systemctl reload nginx || true
CODE=000
for i in $(seq 1 20); do
CODE="$(panel_probe)"
[ "$CODE" = 200 ] && break
sleep 1
done
if [ "$CODE" != 200 ]; then
echo "the panel does not answer on port $PP (HTTP $CODE)"
nginx -t 2>&1 || true
journalctl -u nginx -n 8 --no-pager 2>&1 || true
exit 1
fi
certbot delete --cert-name "$old" --non-interactive || true
echo "panel subdomain removed, the panel is back on port $PP"
}
case "${1:-}" in
--render) render "${2:-}";;
--panel) apply_panel "${2:-}" "${3:-}";;
--panel-off) apply_panel_off;;
*) apply "${1:-}" "${2:-}";;
esac
