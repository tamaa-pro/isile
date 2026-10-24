#!/usr/bin/env bash
APP=/opt/vpnpanel
DATA=/var/lib/vpnpanel
PY="$APP/venv/bin/python"
[ "$(id -u)" -eq 0 ] || { echo "Run as root: sudo isile"; exit 1; }
[ -f "$DATA/panel.db" ] || { echo "isile is not installed"; exit 1; }
dbget(){ python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);r=c.execute("SELECT v FROM settings WHERE k=?",(sys.argv[2],)).fetchone();print(r[0] if r else "")' "$DATA/panel.db" "$1"; }
dbq(){ python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);[print(*r) for r in c.execute(sys.argv[2])]' "$DATA/panel.db" "$1"; }
show_info(){
local d u ip sc h
d="$(dbget domain)"
ip="$(dbget server_ip)"
u="$(dbget admin_user)"
if [ -n "$d" ]; then sc=https; h="$d"; else sc=http; h="${ip:-server-address}"; fi
echo "=================================================="
echo "  isile panel info"
echo "=================================================="
echo " Version   : $(cat "$APP/panel/VERSION" 2>/dev/null)"
echo " Panel URL : $sc://$h:2080"
echo " Username  : $u"
echo " Password  : (stored hashed, use option 1 to set a new one)"
echo " Domain    : ${d:-not set (server address, no TLS)}"
echo " Server IP : ${ip:-unknown}"
if [ -n "$d" ]; then echo " Ports     : 80 (no TLS) | 443 (TLS) | 2080 (panel, HTTPS)"; else echo " Ports     : 80 (no TLS) | 2080 (panel, HTTP)"; fi
if [ -n "$d" ]; then echo " SSH SSL   : direct SSH on 80 (no TLS) and 443 (TLS via stunnel)"; else echo " SSH SSL   : direct SSH on 80 (no TLS)"; fi
echo " Paths     : /vless /vmess /trojan (any other path = SSH WebSocket)"
echo " Services  :"
local svcs="vpnpanel vpnbridge vpnmux xray nginx"
[ -z "$d" ] || svcs="$svcs vpnstunnel"
for s in $svcs; do
printf '   %-10s %s\n' "$s" "$(systemctl is-active "$s" 2>/dev/null)"
done
echo " Accounts  :"
dbq "SELECT CASE WHEN proto='ssh' THEN 'ssh-'||transport ELSE proto END AS k,COUNT(*) FROM accounts GROUP BY k" | sed 's/^/   /'
echo "=================================================="
}
edit_admin(){
local nu np np2
read -rp "New username (Enter to keep): " nu
[ -z "$nu" ] || [[ "$nu" =~ ^[A-Za-z0-9_.-]{3,32}$ ]] || { echo "Username: 3-32 chars of A-Za-z0-9_.-"; return; }
read -rsp "New password (Enter to keep, min 10 chars): " np; echo
if [ -n "$np" ]; then
[ "${#np}" -ge 10 ] || { echo "Password too short"; return; }
read -rsp "Confirm password: " np2; echo
[ "$np" = "$np2" ] || { echo "Passwords do not match"; return; }
fi
[ -n "$nu$np" ] || { echo "Nothing changed"; return; }
VPN_ADMIN_USER="$nu" VPN_ADMIN_PASS="$np" "$PY" "$APP/panel/app.py" setadmin || { echo "Update failed"; return; }
echo "Admin credentials updated."
echo " Username : $(dbget admin_user)"
[ -z "$np" ] || echo " Password : $np"
}
update(){
local r b
r="tamaa-pro/isile"
b="main"
[ -f "$APP/.repo" ] && read -r r b <"$APP/.repo"
echo "Updating from github.com/$r ($b) ..."
bash <(curl -fsSL "https://raw.githubusercontent.com/$r/$b/install.sh") --update
}
uninstall(){
local ans d n
if [ "${1:-}" = "--yes" ]; then ans=YES; else
echo "This removes the panel, Xray, the SSH bridge and SSL multiplexer, stunnel, all VPN accounts and the TLS certificate."
read -rp "Type YES to continue: " ans
fi
[ "$ans" = "YES" ] || { echo "Cancelled"; return 1; }
d="$(dbget domain)"
local names
names="$(dbq "SELECT name FROM accounts WHERE proto='ssh'")"
systemctl disable --now vpnpanel vpnbridge vpnmux vpnstunnel xray >/dev/null 2>&1
rm -f /etc/systemd/system/vpnpanel.service /etc/systemd/system/vpnbridge.service /etc/systemd/system/vpnmux.service /etc/systemd/system/vpnstunnel.service /etc/systemd/system/xray.service
systemctl daemon-reload
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
for p in 2080 80 443; do ufw delete allow "$p/tcp" >/dev/null 2>&1; done
rm -rf "$APP" "$DATA" /etc/vpnpanel /usr/local/etc/xray /usr/local/share/xray /usr/local/bin/xray /var/log/xray /etc/logrotate.d/vpnpanel-xray /var/log/isile-install.log
echo "=================================================="
echo "  isile was uninstalled completely"
echo "=================================================="
echo " Installed packages (nginx, certbot, stunnel4, ufw, python3) were left in place."
rm -f /usr/local/bin/isile
return 0
}
menu(){
while true; do
echo "=================================================="
echo "  isile menu"
echo "=================================================="
echo "  1) Edit admin credentials"
echo "  2) Show panel info"
echo "  3) Uninstall panel completely"
echo "  4) Update to the latest version"
echo "  0) Exit"
read -rp "> " c
case "$c" in
1) edit_admin;;
2) show_info;;
3) uninstall && exit 0;;
4) update; exit 0;;
0) exit 0;;
*) echo "Invalid choice";;
esac
done
}
case "${1:-}" in
1) edit_admin;;
2) show_info;;
3) uninstall "${2:-}";;
4) update;;
*) menu;;
esac
exit 0
