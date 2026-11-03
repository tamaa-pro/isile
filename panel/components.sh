#!/usr/bin/env bash
# Usage: components.sh <install|uninstall|refresh> <xray|wsbridge|udpcustom|vaydns|slowdns>
# Output goes to stdout/stderr: the caller (install.sh or the panel job) redirects it to the log.
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
APP=/opt/vpnpanel
DATA=/var/lib/vpnpanel
UDPC_DIR=/usr/local/lib/isile/udp-custom
UDPC_USER=udpc
UDPC_INFO=/etc/vpnpanel/udp-custom.info
UDPC_PORT=36712
UDPC_URL_AMD64="https://github.com/http-custom/udp-custom/raw/main/bin/udp-custom-linux-amd64"
VAYDNS_DIR=/usr/local/lib/isile/vaydns
VAYDNS_USER=vaydns
VAYDNS_ENV=/etc/vpnpanel/vaydns.env
VAYDNS_INFO=/etc/vpnpanel/vaydns.info
VAYDNS_BASE="https://github.com/net2share/vaydns/releases/latest/download"
VAYDNS_URL="${VAYDNS_URL:-}"
VAYDNS_SHA256="$(echo "${VAYDNS_SHA256:-}" | tr 'A-F' 'a-f' | tr -d ' ')"
VAYDNS_UDP=5300
VAYDNS_UPSTREAM=10053
SLOWDNS_DIR=/usr/local/lib/isile/slowdns
SLOWDNS_USER=slowdns
SLOWDNS_ENV=/etc/vpnpanel/slowdns.env
SLOWDNS_INFO=/etc/vpnpanel/slowdns.info
SLOWDNS_UDP=5301
DNSFRONT_UDP=5302
DNSFRONT_NFT=/usr/local/lib/isile/dnsfront.nft
UDPC_URL="${UDPC_URL:-}"
UDPC_SHA256="$(echo "${UDPC_SHA256:-}" | tr 'A-F' 'a-f' | tr -d ' ')"
ACTION="${1:-}"
COMP="${2:-}"
die(){ echo "ERROR: $1" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "run as root"
dbset(){
[ -f "$DATA/panel.db" ] || return 0
python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1],timeout=30);c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(sys.argv[2],sys.argv[3]));c.commit()' "$DATA/panel.db" "$1" "$2" || true
}
ssh_port(){
local p
p="$(sshd -T 2>/dev/null | awk '/^port /{print $2; exit}' || true)"
echo "${SSH_PORT:-${p:-22}}"
}

# ---------- Xray ----------
unit_xray(){
cat > /etc/systemd/system/xray.service <<EOT
[Unit]
Description=Xray
After=network.target
[Service]
User=xray
Group=xray
LogsDirectory=xray
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
}
install_xray(){
echo "Installing Xray"
id xray >/dev/null 2>&1 || useradd -r -M -s /usr/sbin/nologin xray
install -d -m755 /usr/local/etc/xray
install -d -o xray -g xray -m755 /var/log/xray
if [ ! -x /usr/local/bin/xray ]; then
local XA XU TMP EXP ACT
case "$(uname -m)" in x86_64) XA=64;; aarch64) XA=arm64-v8a;; *) die "unsupported architecture $(uname -m)";; esac
command -v unzip >/dev/null 2>&1 || apt-get install -y unzip
XU="https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-$XA.zip"
TMP="$(mktemp -d)"
curl -fsSL -o "$TMP/x.zip" "$XU" || { rm -rf "$TMP"; die "cannot download Xray"; }
curl -fsSL -o "$TMP/x.dgst" "$XU.dgst" || { rm -rf "$TMP"; die "cannot download Xray checksum"; }
EXP="$(grep -i 'sha2-256\|sha256' "$TMP/x.dgst" | grep -oE '[0-9a-fA-F]{64}' | head -1 | tr 'A-F' 'a-f' || true)"
ACT="$(sha256sum "$TMP/x.zip" | cut -d' ' -f1)"
[ -n "$EXP" ] && [ "$EXP" = "$ACT" ] || { rm -rf "$TMP"; die "Xray checksum mismatch"; }
unzip -oq "$TMP/x.zip" -d "$TMP/x" || { rm -rf "$TMP"; die "Xray archive is invalid"; }
install -m755 "$TMP/x/xray" /usr/local/bin/xray
install -d /usr/local/share/xray
install -m644 "$TMP/x/geoip.dat" "$TMP/x/geosite.dat" /usr/local/share/xray/
rm -rf "$TMP"
fi
unit_xray
systemctl daemon-reload
systemctl enable xray >/dev/null 2>&1 || true
dbset comp_xray 1
echo "Xray installed"
}
uninstall_xray(){
echo "Removing Xray"
systemctl disable --now xray >/dev/null 2>&1 || true
rm -f /etc/systemd/system/xray.service /usr/local/bin/xray /usr/local/etc/xray/config.json
rm -rf /usr/local/share/xray
systemctl daemon-reload
dbset comp_xray 0
echo "Xray removed"
}

# ---------- SSH WebSocket bridge ----------
unit_wsbridge(){
cat > /etc/systemd/system/vpnbridge.service <<EOT
[Unit]
Description=SSH WebSocket bridge
After=network.target
[Service]
User=nobody
Group=nogroup
Environment=SSH_PORT=$(ssh_port)
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
}
install_wsbridge(){
echo "Installing the SSH WebSocket bridge"
[ -f "$APP/panel/wsbridge.py" ] || die "panel/wsbridge.py is missing"
unit_wsbridge
systemctl daemon-reload
systemctl enable --now vpnbridge >/dev/null 2>&1 || true
dbset comp_wsbridge 1
echo "SSH WebSocket bridge installed"
}
uninstall_wsbridge(){
echo "Removing the SSH WebSocket bridge"
systemctl disable --now vpnbridge >/dev/null 2>&1 || true
rm -f /etc/systemd/system/vpnbridge.service
systemctl daemon-reload
dbset comp_wsbridge 0
echo "SSH WebSocket bridge removed"
}

# ---------- UDP Custom (third-party, closed source) ----------
udpc_files(){
# Everything except the binary itself: config (kept if present), egress firewall and unit.
local UID_N
UID_N="$(id -u "$UDPC_USER")"
install -d -m755 /usr/local/lib/isile "$UDPC_DIR" /etc/vpnpanel
if [ ! -s "$UDPC_DIR/config.json" ]; then
cat > "$UDPC_DIR/config.json" <<EOT
{
  "listen": ":$UDPC_PORT",
  "stream_buffer": 33554432,
  "receive_buffer": 83886080,
  "auth": {
    "mode": "passwords"
  }
}
EOT
fi
chmod 644 "$UDPC_DIR/config.json"
# The binary dials the destinations of the tunnelled traffic itself, so it must be allowed to make
# outbound connections (blocking them gave a tunnel that connects but carries no traffic).
# egress.nft now only clears the old drop table and, if sshd is not on port 22, redirects the
# binary's loopback connections to 22 to the real sshd port.
local SP
SP="$(ssh_port)"
cat > "$UDPC_DIR/egress.nft" <<EOT
table inet isile_udpc
delete table inet isile_udpc
table ip isile_udpc_nat
delete table ip isile_udpc_nat
EOT
if [ "$SP" != "22" ]; then
cat >> "$UDPC_DIR/egress.nft" <<EOT
table ip isile_udpc_nat {
 chain out {
  type nat hook output priority -100; policy accept;
  socket cgroupv2 level 2 "system.slice/udp-custom.service" ip daddr 127.0.0.1 tcp dport 22 dnat to 127.0.0.1:$SP
 }
}
EOT
fi
chmod 644 "$UDPC_DIR/egress.nft"
cat > /etc/systemd/system/udp-custom.service <<EOT
[Unit]
Description=UDP Custom (third-party closed-source binary)
After=network.target ssh.service sshd.service
[Service]
User=root
WorkingDirectory=$UDPC_DIR
ExecStartPre=-+/usr/sbin/nft -f $UDPC_DIR/egress.nft
ExecStart=$UDPC_DIR/udp-custom server
ExecStopPost=-+/usr/sbin/nft delete table inet isile_udpc
ExecStopPost=-+/usr/sbin/nft delete table ip isile_udpc_nat
Restart=always
RestartSec=3
LimitNOFILE=65535
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
RestrictNamespaces=true
RestrictSUIDSGID=true
LockPersonality=true
SystemCallArchitectures=native
CapabilityBoundingSet=CAP_DAC_READ_SEARCH CAP_SETUID CAP_SETGID CAP_NET_BIND_SERVICE CAP_AUDIT_WRITE
[Install]
WantedBy=multi-user.target
EOT
}
udpc_port(){
local p
p="$(grep -oE '"listen"[^,]*' "$UDPC_DIR/config.json" 2>/dev/null | grep -oE '[0-9]{1,5}' | tail -1 || true)"
echo "${p:-$UDPC_PORT}"
}
# ---------- udpgw (BadVPN, open source, from the distribution): UDP-over-TCP for clients ----------
# Listens on 127.0.0.1:7300 TCP only; clients reach it through their SSH tunnel, so no firewall port is needed.
UDPGW_USER=udpgw
UDPGW_PORT=7300
UDPGW_NFT=/etc/vpnpanel/udpgw.nft
udpgw_setup(){
local BIN UID_N
if ! command -v badvpn-udpgw >/dev/null 2>&1; then
apt-get install -y badvpn >/dev/null 2>&1 || { apt-get update -qq >/dev/null 2>&1; apt-get install -y badvpn >/dev/null 2>&1; } || true
fi
BIN="$(command -v badvpn-udpgw || true)"
if [ -z "$BIN" ]; then echo "Warning: badvpn-udpgw is not available from the package sources, UDP over the tunnel stays off"; return 0; fi
getent group "$UDPGW_USER" >/dev/null || groupadd -r "$UDPGW_USER"
id "$UDPGW_USER" >/dev/null 2>&1 || useradd -r -M -s /usr/sbin/nologin -g "$UDPGW_USER" "$UDPGW_USER"
UID_N="$(id -u "$UDPGW_USER")"
install -d -m755 /etc/vpnpanel
# udpgw relays clients' UDP to any address, so keep it away from private/internal networks (DNS excepted).
cat > "$UDPGW_NFT" <<EOT
table inet isile_udpgw
delete table inet isile_udpgw
table inet isile_udpgw {
 chain out {
  type filter hook output priority 0; policy accept;
  meta skuid $UID_N meta l4proto udp th dport 53 accept
  meta skuid $UID_N ip daddr { 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.168.0.0/16 } counter drop
  meta skuid $UID_N ip6 daddr { ::1, fc00::/7, fe80::/10 } counter drop
 }
}
EOT
chmod 644 "$UDPGW_NFT"
cat > /etc/systemd/system/vpn-udpgw.service <<EOT
[Unit]
Description=BadVPN udpgw (UDP over the SSH tunnel, loopback only)
After=network.target
[Service]
User=$UDPGW_USER
Group=$UDPGW_USER
ExecStartPre=-+/usr/sbin/nft -f $UDPGW_NFT
ExecStart=$BIN --listen-addr 127.0.0.1:$UDPGW_PORT --max-clients 1000 --max-connections-for-client 20
ExecStopPost=-+/usr/sbin/nft delete table inet isile_udpgw
Restart=always
RestartSec=3
LimitNOFILE=65535
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6
RestrictNamespaces=true
LockPersonality=true
CapabilityBoundingSet=
[Install]
WantedBy=multi-user.target
EOT
systemctl daemon-reload
systemctl enable vpn-udpgw >/dev/null 2>&1 || true
systemctl restart vpn-udpgw >/dev/null 2>&1 || true
sleep 1
systemctl is-active --quiet vpn-udpgw && echo "udpgw running on 127.0.0.1:$UDPGW_PORT" || echo "Warning: udpgw did not start (journalctl -u vpn-udpgw)"
}
udpgw_remove(){
systemctl disable --now vpn-udpgw >/dev/null 2>&1 || true
rm -f /etc/systemd/system/vpn-udpgw.service "$UDPGW_NFT"
nft delete table inet isile_udpgw >/dev/null 2>&1 || true
id "$UDPGW_USER" >/dev/null 2>&1 && userdel "$UDPGW_USER" >/dev/null 2>&1 || true
getent group "$UDPGW_USER" >/dev/null 2>&1 && groupdel "$UDPGW_USER" >/dev/null 2>&1 || true
}

uninstall_udpcustom(){
echo "Removing UDP Custom"
local P
P="$(udpc_port)"
systemctl disable --now udp-custom >/dev/null 2>&1 || true
rm -f /etc/systemd/system/udp-custom.service "$UDPC_INFO"
nft delete table inet isile_udpc >/dev/null 2>&1 || true
udpgw_remove
rm -rf "$UDPC_DIR"
rmdir /usr/local/lib/isile >/dev/null 2>&1 || true
if command -v ufw >/dev/null 2>&1; then ufw delete allow "$P/udp" >/dev/null 2>&1 || true; fi
id "$UDPC_USER" >/dev/null 2>&1 && userdel "$UDPC_USER" >/dev/null 2>&1 || true
getent group "$UDPC_USER" >/dev/null 2>&1 && groupdel "$UDPC_USER" >/dev/null 2>&1 || true
systemctl daemon-reload
dbset comp_udpcustom 0
echo "UDP Custom removed"
}
install_udpcustom(){
echo "Installing UDP Custom (third-party closed-source binary)"
local URL TMP SHA
URL="$UDPC_URL"
if [ -z "$URL" ]; then
case "$(uname -m)" in
x86_64) URL="$UDPC_URL_AMD64";;
*) die "no default UDP Custom binary for $(uname -m); set UDPC_URL (and UDPC_SHA256) to a binary you trust";;
esac
fi
[[ "$URL" =~ ^https:// ]] || die "UDPC_URL must be an https:// address"
TMP="$(mktemp -d)"
echo "Source: $URL"
curl -fsSL --max-time 180 -o "$TMP/udpc" "$URL" || { rm -rf "$TMP"; die "cannot download the UDP Custom binary from $URL"; }
[ "$(head -c4 "$TMP/udpc" | od -An -tx1 | tr -d ' \n')" = "7f454c46" ] || { rm -rf "$TMP"; die "the downloaded file is not a Linux executable"; }
SHA="$(sha256sum "$TMP/udpc" | cut -d' ' -f1)"
echo "SHA-256: $SHA"
if [ -n "$UDPC_SHA256" ] && [ "$UDPC_SHA256" != "$SHA" ]; then rm -rf "$TMP"; die "SHA-256 mismatch (expected $UDPC_SHA256)"; fi
if [ -z "$UDPC_SHA256" ]; then echo "Note: no UDPC_SHA256 was supplied, so the binary could not be verified against a known hash"; fi
getent group "$UDPC_USER" >/dev/null || groupadd -r "$UDPC_USER"
id "$UDPC_USER" >/dev/null 2>&1 || useradd -r -M -s /usr/sbin/nologin -g "$UDPC_USER" "$UDPC_USER"
udpc_files
install -m755 "$TMP/udpc" "$UDPC_DIR/udp-custom"
rm -rf "$TMP"
printf 'url=%s\nsha256=%s\n' "$URL" "$SHA" > "$UDPC_INFO"
chmod 644 "$UDPC_INFO"
if command -v ufw >/dev/null 2>&1; then ufw allow "$(udpc_port)/udp" || true; fi
systemctl daemon-reload
systemctl enable --now udp-custom >/dev/null 2>&1 || true
local i ok=0
for i in 1 2 3 4 5 6; do
sleep 1
if systemctl is-active --quiet udp-custom; then ok=1; fi
done
if [ "$ok" != 1 ] || ! systemctl is-active --quiet udp-custom; then
journalctl -u udp-custom -n 12 --no-pager 2>&1 || true
uninstall_udpcustom
die "UDP Custom did not stay running, so it was removed again (see the log lines above)"
fi
udpgw_setup || true
dbset comp_udpcustom 1
echo "UDP Custom installed and running on UDP port $(udpc_port)"
}
refresh_udpcustom(){
[ -x "$UDPC_DIR/udp-custom" ] || return 0
id "$UDPC_USER" >/dev/null 2>&1 || die "user $UDPC_USER is missing"
udpc_files
systemctl daemon-reload
udpgw_setup || true
}

# ---------- VayDNS (open source DNS tunnel, net2share/vaydns) ----------
# The server listens on UDP 5300 as an unprivileged user; an nftables rule redirects incoming UDP 53 to it
# (so systemd-resolved can keep its own loopback listener). Everything the tunnel carries is forwarded to the
# local multiplexer (127.0.0.1:10053), which sends SSH to sshd, TLS to stunnel and HTTP to nginx.
# UDP 53 is shared by VayDNS and SlowDNS: nftables redirects it to the DNS front inside vpnmux (UDP $DNSFRONT_UDP),
# which hands every query to the tunnel server that owns the query's domain (zones written by the panel to /etc/vpnpanel/dnszones).
dnsfront_files(){
install -d -m755 /usr/local/lib/isile
cat > "$DNSFRONT_NFT" <<EOT
table inet isile_dns
delete table inet isile_dns
table inet isile_dns {
 chain pre {
  type nat hook prerouting priority dstnat; policy accept;
  iifname != "lo" udp dport 53 redirect to :$DNSFRONT_UDP
 }
}
EOT
chmod 644 "$DNSFRONT_NFT"
# the redirect rewrites the destination port before the firewall sees it, so the front port must be open
if command -v ufw >/dev/null 2>&1; then ufw allow "$DNSFRONT_UDP/udp" >/dev/null 2>&1 || true; fi
}
vaydns_files(){
install -d -m755 /usr/local/lib/isile "$VAYDNS_DIR" /etc/vpnpanel
rm -f "$VAYDNS_DIR/redirect.nft"
dnsfront_files
cat > /etc/systemd/system/vaydns.service <<EOT
[Unit]
Description=VayDNS server (DNS tunnel)
After=network.target vpnmux.service
ConditionPathExists=$VAYDNS_ENV
[Service]
User=$VAYDNS_USER
Group=$VAYDNS_USER
EnvironmentFile=$VAYDNS_ENV
ExecStartPre=-+/usr/sbin/nft delete table inet isile_vaydns
ExecStartPre=-+/usr/sbin/nft -f $DNSFRONT_NFT
ExecStart=$VAYDNS_DIR/vaydns-server -udp :$VAYDNS_UDP -privkey-file $VAYDNS_DIR/server.key -domain \${VAYDNS_DOMAIN} -upstream 127.0.0.1:$VAYDNS_UPSTREAM
ExecStopPost=-+/bin/sh -c "systemctl is-active --quiet slowdns || /usr/sbin/nft delete table inet isile_dns"
Restart=always
RestartSec=3
LimitNOFILE=65535
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6
RestrictNamespaces=true
LockPersonality=true
SystemCallArchitectures=native
CapabilityBoundingSet=
[Install]
WantedBy=multi-user.target
EOT
}
vaydns_fetch(){
local ARCH URL SHA EXP TMP="$1"
case "$(uname -m)" in x86_64) ARCH=amd64;; aarch64) ARCH=arm64;; *) die "unsupported architecture $(uname -m)";; esac
URL="$VAYDNS_URL"
[ -n "$URL" ] || URL="$VAYDNS_BASE/vaydns-server-linux-$ARCH"
[[ "$URL" =~ ^https:// ]] || die "VAYDNS_URL must be an https:// address"
echo "Source: $URL"
curl -fsSL --max-time 180 -o "$TMP/vaydns" "$URL" || { rm -rf "$TMP"; die "cannot download VayDNS from $URL"; }
[ "$(head -c4 "$TMP/vaydns" | od -An -tx1 | tr -d ' \n')" = "7f454c46" ] || { rm -rf "$TMP"; die "the downloaded file is not a Linux executable"; }
SHA="$(sha256sum "$TMP/vaydns" | cut -d' ' -f1)"
echo "SHA-256: $SHA"
EXP="$VAYDNS_SHA256"
if [ -z "$EXP" ] && [ -z "$VAYDNS_URL" ]; then
curl -fsSL --max-time 30 -o "$TMP/vaydns.sha256" "$URL.sha256" || { rm -rf "$TMP"; die "cannot download the VayDNS checksum"; }
EXP="$(grep -oE '[0-9a-fA-F]{64}' "$TMP/vaydns.sha256" | head -1 | tr 'A-F' 'a-f' || true)"
[ -n "$EXP" ] || { rm -rf "$TMP"; die "the VayDNS checksum file is invalid"; }
fi
if [ -n "$EXP" ] && [ "$EXP" != "$SHA" ]; then rm -rf "$TMP"; die "VayDNS SHA-256 mismatch (expected $EXP)"; fi
if [ -z "$EXP" ]; then echo "Note: no VAYDNS_SHA256 was supplied, so the binary could not be verified against a known hash"; fi
VURL="$URL"
VSHA="$SHA"
}
install_vaydns(){
echo "Installing VayDNS (DNS tunnel)"
local URL TMP SHA
TMP="$(mktemp -d)"
vaydns_fetch "$TMP"
URL="$VURL"
SHA="$VSHA"
getent group "$VAYDNS_USER" >/dev/null || groupadd -r "$VAYDNS_USER"
id "$VAYDNS_USER" >/dev/null 2>&1 || useradd -r -M -s /usr/sbin/nologin -g "$VAYDNS_USER" "$VAYDNS_USER"
install -d -m755 /usr/local/lib/isile "$VAYDNS_DIR" /etc/vpnpanel
install -m755 "$TMP/vaydns" "$VAYDNS_DIR/vaydns-server"
rm -rf "$TMP"
if [ ! -s "$VAYDNS_DIR/server.key" ] || [ ! -s "$VAYDNS_DIR/server.pub" ]; then
rm -f "$VAYDNS_DIR/server.key" "$VAYDNS_DIR/server.pub"
"$VAYDNS_DIR/vaydns-server" -gen-key -privkey-file "$VAYDNS_DIR/server.key" -pubkey-file "$VAYDNS_DIR/server.pub" >/dev/null || die "VayDNS key generation failed"
[ -s "$VAYDNS_DIR/server.key" ] && [ -s "$VAYDNS_DIR/server.pub" ] || die "VayDNS did not write its key files"
fi
chown "$VAYDNS_USER:$VAYDNS_USER" "$VAYDNS_DIR/server.key"
chmod 600 "$VAYDNS_DIR/server.key"
chmod 644 "$VAYDNS_DIR/server.pub"
printf 'url=%s\nsha256=%s\n' "$URL" "$SHA" > "$VAYDNS_INFO"
chmod 644 "$VAYDNS_INFO"
vaydns_files
if command -v ufw >/dev/null 2>&1; then ufw allow 53/udp || true; ufw allow "$VAYDNS_UDP/udp" || true; fi
systemctl daemon-reload
systemctl enable vaydns >/dev/null 2>&1 || true
dbset comp_vaydns 1
if [ -n "${VAYDNS_DOMAIN:-}" ]; then
[[ "$VAYDNS_DOMAIN" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || die "invalid VayDNS tunnel domain: $VAYDNS_DOMAIN"
dbset vaydns_domain "$VAYDNS_DOMAIN"
fi
echo "VayDNS installed. Set the tunnel domain in Settings > Components, then add its NS record; UDP 53 must be open."
}
uninstall_vaydns(){
echo "Removing VayDNS"
systemctl disable --now vaydns >/dev/null 2>&1 || true
rm -f /etc/systemd/system/vaydns.service "$VAYDNS_ENV" "$VAYDNS_INFO"
nft delete table inet isile_vaydns >/dev/null 2>&1 || true
if [ ! -d "$SLOWDNS_DIR" ]; then
nft delete table inet isile_dns >/dev/null 2>&1 || true
rm -f "$DNSFRONT_NFT"
if command -v ufw >/dev/null 2>&1; then ufw delete allow 53/udp >/dev/null 2>&1 || true; ufw delete allow "$DNSFRONT_UDP/udp" >/dev/null 2>&1 || true; fi
fi
if command -v ufw >/dev/null 2>&1; then ufw delete allow "$VAYDNS_UDP/udp" >/dev/null 2>&1 || true; fi
rm -rf "$VAYDNS_DIR"
rmdir /usr/local/lib/isile >/dev/null 2>&1 || true
id "$VAYDNS_USER" >/dev/null 2>&1 && userdel "$VAYDNS_USER" >/dev/null 2>&1 || true
getent group "$VAYDNS_USER" >/dev/null 2>&1 && groupdel "$VAYDNS_USER" >/dev/null 2>&1 || true
systemctl daemon-reload
dbset comp_vaydns 0
echo "VayDNS removed"
}
refresh_vaydns(){
[ -x "$VAYDNS_DIR/vaydns-server" ] || return 0
id "$VAYDNS_USER" >/dev/null 2>&1 || die "user $VAYDNS_USER is missing"
vaydns_files
systemctl daemon-reload
}

# ---------- SlowDNS (SSH over a DNS tunnel for SlowDNS / dnstt clients) ----------
# Same open source server binary as VayDNS (net2share/vaydns) started with -dnstt-compat, which speaks the original
# dnstt wire protocol that SlowDNS apps use. It has its own domain, key pair and UDP port; UDP 53 is shared through the DNS front.
slowdns_files(){
install -d -m755 /usr/local/lib/isile "$SLOWDNS_DIR" /etc/vpnpanel
dnsfront_files
cat > /etc/systemd/system/slowdns.service <<EOT
[Unit]
Description=SlowDNS server (dnstt compatible DNS tunnel)
After=network.target vpnmux.service
ConditionPathExists=$SLOWDNS_ENV
[Service]
User=$SLOWDNS_USER
Group=$SLOWDNS_USER
EnvironmentFile=$SLOWDNS_ENV
ExecStartPre=-+/usr/sbin/nft delete table inet isile_vaydns
ExecStartPre=-+/usr/sbin/nft -f $DNSFRONT_NFT
ExecStart=$SLOWDNS_DIR/vaydns-server -udp :$SLOWDNS_UDP -privkey-file $SLOWDNS_DIR/server.key -dnstt-compat -domain \${SLOWDNS_DOMAIN} -upstream 127.0.0.1:$VAYDNS_UPSTREAM
ExecStopPost=-+/bin/sh -c "systemctl is-active --quiet vaydns || /usr/sbin/nft delete table inet isile_dns"
Restart=always
RestartSec=3
LimitNOFILE=65535
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6
RestrictNamespaces=true
LockPersonality=true
SystemCallArchitectures=native
CapabilityBoundingSet=
[Install]
WantedBy=multi-user.target
EOT
}
install_slowdns(){
echo "Installing SlowDNS (DNS tunnel)"
local TMP SRC SHA
TMP="$(mktemp -d)"
if [ -x "$VAYDNS_DIR/vaydns-server" ]; then
echo "Using the VayDNS server binary that is already installed"
cp "$VAYDNS_DIR/vaydns-server" "$TMP/vaydns"
SRC="$(grep '^url=' "$VAYDNS_INFO" 2>/dev/null | cut -d= -f2- || true)"
else
vaydns_fetch "$TMP"
SRC="$VURL"
fi
SHA="$(sha256sum "$TMP/vaydns" | cut -d' ' -f1)"
getent group "$SLOWDNS_USER" >/dev/null || groupadd -r "$SLOWDNS_USER"
id "$SLOWDNS_USER" >/dev/null 2>&1 || useradd -r -M -s /usr/sbin/nologin -g "$SLOWDNS_USER" "$SLOWDNS_USER"
install -d -m755 /usr/local/lib/isile "$SLOWDNS_DIR" /etc/vpnpanel
install -m755 "$TMP/vaydns" "$SLOWDNS_DIR/vaydns-server"
rm -rf "$TMP"
if [ ! -s "$SLOWDNS_DIR/server.key" ] || [ ! -s "$SLOWDNS_DIR/server.pub" ]; then
rm -f "$SLOWDNS_DIR/server.key" "$SLOWDNS_DIR/server.pub"
"$SLOWDNS_DIR/vaydns-server" -gen-key -privkey-file "$SLOWDNS_DIR/server.key" -pubkey-file "$SLOWDNS_DIR/server.pub" >/dev/null || die "SlowDNS key generation failed"
[ -s "$SLOWDNS_DIR/server.key" ] && [ -s "$SLOWDNS_DIR/server.pub" ] || die "SlowDNS did not write its key files"
fi
chown "$SLOWDNS_USER:$SLOWDNS_USER" "$SLOWDNS_DIR/server.key"
chmod 600 "$SLOWDNS_DIR/server.key"
chmod 644 "$SLOWDNS_DIR/server.pub"
printf 'url=%s\nsha256=%s\n' "$SRC" "$SHA" > "$SLOWDNS_INFO"
chmod 644 "$SLOWDNS_INFO"
slowdns_files
if command -v ufw >/dev/null 2>&1; then ufw allow 53/udp || true; ufw allow "$SLOWDNS_UDP/udp" || true; fi
systemctl daemon-reload
systemctl enable slowdns >/dev/null 2>&1 || true
dbset comp_slowdns 1
if [ -n "${SLOWDNS_DOMAIN:-}" ]; then
[[ "$SLOWDNS_DOMAIN" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || die "invalid SlowDNS tunnel domain: $SLOWDNS_DOMAIN"
dbset slowdns_domain "$SLOWDNS_DOMAIN"
fi
echo "SlowDNS installed. Set the tunnel domain in Settings > Components, then add its NS record; UDP 53 must be open."
}
uninstall_slowdns(){
echo "Removing SlowDNS"
systemctl disable --now slowdns >/dev/null 2>&1 || true
rm -f /etc/systemd/system/slowdns.service "$SLOWDNS_ENV" "$SLOWDNS_INFO"
if [ ! -d "$VAYDNS_DIR" ]; then
nft delete table inet isile_dns >/dev/null 2>&1 || true
rm -f "$DNSFRONT_NFT"
if command -v ufw >/dev/null 2>&1; then ufw delete allow 53/udp >/dev/null 2>&1 || true; ufw delete allow "$DNSFRONT_UDP/udp" >/dev/null 2>&1 || true; fi
fi
if command -v ufw >/dev/null 2>&1; then ufw delete allow "$SLOWDNS_UDP/udp" >/dev/null 2>&1 || true; fi
rm -rf "$SLOWDNS_DIR"
rmdir /usr/local/lib/isile >/dev/null 2>&1 || true
id "$SLOWDNS_USER" >/dev/null 2>&1 && userdel "$SLOWDNS_USER" >/dev/null 2>&1 || true
getent group "$SLOWDNS_USER" >/dev/null 2>&1 && groupdel "$SLOWDNS_USER" >/dev/null 2>&1 || true
systemctl daemon-reload
dbset comp_slowdns 0
echo "SlowDNS removed"
}
refresh_slowdns(){
[ -x "$SLOWDNS_DIR/vaydns-server" ] || return 0
id "$SLOWDNS_USER" >/dev/null 2>&1 || die "user $SLOWDNS_USER is missing"
slowdns_files
systemctl daemon-reload
}

case "$ACTION:$COMP" in
install:xray) install_xray;;
uninstall:xray) uninstall_xray;;
install:wsbridge) install_wsbridge;;
uninstall:wsbridge) uninstall_wsbridge;;
install:udpcustom) install_udpcustom;;
uninstall:udpcustom) uninstall_udpcustom;;
refresh:udpcustom) refresh_udpcustom;;
install:vaydns) install_vaydns;;
uninstall:vaydns) uninstall_vaydns;;
refresh:vaydns) refresh_vaydns;;
install:slowdns) install_slowdns;;
uninstall:slowdns) uninstall_slowdns;;
refresh:slowdns) refresh_slowdns;;
*) die "usage: components.sh <install|uninstall|refresh> <xray|wsbridge|udpcustom|vaydns|slowdns>";;
esac
