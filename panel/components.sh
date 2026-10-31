#!/usr/bin/env bash
# Usage: components.sh <install|uninstall|refresh> <xray|wsbridge|udpcustom>
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
uninstall_udpcustom(){
echo "Removing UDP Custom"
local P
P="$(udpc_port)"
systemctl disable --now udp-custom >/dev/null 2>&1 || true
rm -f /etc/systemd/system/udp-custom.service "$UDPC_INFO"
nft delete table inet isile_udpc >/dev/null 2>&1 || true
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
dbset comp_udpcustom 1
echo "UDP Custom installed and running on UDP port $(udpc_port)"
}
refresh_udpcustom(){
[ -x "$UDPC_DIR/udp-custom" ] || return 0
id "$UDPC_USER" >/dev/null 2>&1 || die "user $UDPC_USER is missing"
udpc_files
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
*) die "usage: components.sh <install|uninstall> <xray|wsbridge|udpcustom>";;
esac
