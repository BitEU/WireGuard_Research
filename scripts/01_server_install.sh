#!/bin/bash
set -euo pipefail

WG_PORT="${WG_PORT:-51820}"
WG_SERVER_IP="${WG_SERVER_IP:-10.66.66.1/24}"
TCP_PORT="${TCP_PORT:-4096}"
PSK="${PSK:-cyb623-wg-obfuscation-2026}"
WAN_IF="$(ip -o -4 route show to default | awk '{print $5}' | head -n1)"
ARCH="$(uname -m)"
case "$ARCH" in
  aarch64|arm64) UDP2RAW_BIN="udp2raw_arm" ;;
  x86_64)        UDP2RAW_BIN="udp2raw_amd64" ;;
  *) echo "unsupported arch: $ARCH"; exit 1 ;;
esac

echo "[*] WAN: $WAN_IF   WG: $WG_PORT   udp2raw: TCP/$TCP_PORT"

sudo dnf install -y oracle-epel-release-el9
sudo dnf install -y wireguard-tools iptables-services curl tar

echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-wireguard.conf >/dev/null
sudo sysctl --system >/dev/null

sudo install -d -m 700 /etc/wireguard
if [ ! -f /etc/wireguard/server_private.key ]; then
  umask 077
  wg genkey | sudo tee /etc/wireguard/server_private.key >/dev/null
  sudo chmod 600 /etc/wireguard/server_private.key
  sudo cat /etc/wireguard/server_private.key | wg pubkey | sudo tee /etc/wireguard/server_public.key >/dev/null
fi
SERVER_PRIV=$(sudo cat /etc/wireguard/server_private.key)
SERVER_PUB=$(sudo cat /etc/wireguard/server_public.key)

sudo tee /etc/wireguard/wg0.conf >/dev/null <<EOF
[Interface]
Address = ${WG_SERVER_IP}
ListenPort = ${WG_PORT}
PrivateKey = ${SERVER_PRIV}
SaveConfig = false
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o ${WAN_IF} -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o ${WAN_IF} -j MASQUERADE
EOF
sudo chmod 600 /etc/wireguard/wg0.conf

if systemctl is-active --quiet firewalld; then
  sudo firewall-cmd --permanent --add-port=${WG_PORT}/udp --add-port=${TCP_PORT}/tcp
  sudo firewall-cmd --permanent --add-masquerade
  sudo firewall-cmd --reload
fi
sudo iptables -C INPUT -p udp --dport ${WG_PORT} -j ACCEPT 2>/dev/null \
  || sudo iptables -I INPUT 1 -p udp --dport ${WG_PORT} -j ACCEPT
sudo iptables -C INPUT -p tcp --dport ${TCP_PORT} -j ACCEPT 2>/dev/null \
  || sudo iptables -I INPUT 1 -p tcp --dport ${TCP_PORT} -j ACCEPT
sudo iptables -t raw -C PREROUTING -p tcp --dport ${TCP_PORT} -j NOTRACK 2>/dev/null \
  || sudo iptables -t raw -I PREROUTING -p tcp --dport ${TCP_PORT} -j NOTRACK
sudo iptables -t raw -C OUTPUT -p tcp --sport ${TCP_PORT} -j NOTRACK 2>/dev/null \
  || sudo iptables -t raw -I OUTPUT -p tcp --sport ${TCP_PORT} -j NOTRACK
sudo bash -c 'iptables-save > /etc/sysconfig/iptables' || true

if ! command -v udp2raw >/dev/null 2>&1; then
  TMP="$(mktemp -d)"
  curl -L -o "$TMP/udp2raw.tar.gz" \
    "https://github.com/wangyu-/udp2raw/releases/download/20230206.0/udp2raw_binaries.tar.gz"
  tar -xzf "$TMP/udp2raw.tar.gz" -C "$TMP"
  sudo install -m 755 "$TMP/${UDP2RAW_BIN}" /usr/local/bin/udp2raw
  rm -rf "$TMP"
fi

sudo tee /etc/systemd/system/udp2raw-server.service >/dev/null <<EOF
[Unit]
Description=udp2raw server (faketcp -> wg/${WG_PORT})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/udp2raw -s -l 0.0.0.0:${TCP_PORT} -r 127.0.0.1:${WG_PORT} -k "${PSK}" --raw-mode faketcp -a
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now wg-quick@wg0
sudo systemctl restart wg-quick@wg0
sudo systemctl enable --now udp2raw-server
sudo systemctl restart udp2raw-server

echo
echo "================ SERVER READY ================"
echo "  Server public key: $SERVER_PUB"
echo "  WireGuard:  UDP/${WG_PORT}     (the unobfuscated path)"
echo "  udp2raw:    TCP/${TCP_PORT}    (the obfuscated path)"
echo "  Tunnel:     ${WG_SERVER_IP}"
echo
echo "  Next on this server: bash 02_add_peer.sh <peer_name>"
echo "  In OCI console: open ingress rules for UDP/${WG_PORT} and TCP/${TCP_PORT}"
echo "==============================================="
