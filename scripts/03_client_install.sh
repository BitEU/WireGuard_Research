#!/bin/bash
set -euo pipefail

CONFIG_SRC="${CONFIG_SRC:-/media/sf_Git/configs/lab-client.conf}"
SERVER_IP="${SERVER_IP:-158.101.122.42}"
TCP_PORT="${TCP_PORT:-4096}"
LOCAL_LISTEN_PORT="${LOCAL_LISTEN_PORT:-51821}"
PSK="${PSK:-cyb623-wg-obfuscation-2026}"
MTU="${MTU:-1200}"

if [ ! -f "$CONFIG_SRC" ]; then
  echo "error: $CONFIG_SRC not found. Pull lab-client.conf from the server first." >&2
  exit 1
fi

sudo apt update
sudo apt install -y wireguard wireguard-tools resolvconf python3-scapy tshark tcpdump curl

if ! command -v udp2raw >/dev/null 2>&1; then
  TMP="$(mktemp -d)"
  curl -L -o "$TMP/udp2raw.tar.gz" \
    "https://github.com/wangyu-/udp2raw/releases/download/20230206.0/udp2raw_binaries.tar.gz"
  tar -xzf "$TMP/udp2raw.tar.gz" -C "$TMP"
  sudo install -m 755 "$TMP/udp2raw_amd64" /usr/local/bin/udp2raw
  rm -rf "$TMP"
fi

extract() {
  awk -v key="$1" 'BEGIN{IGNORECASE=0} $0 ~ "^"key"[[:space:]]*=" {
    sub("^"key"[[:space:]]*=[[:space:]]*", ""); sub(/[[:space:]]+$/, ""); print; exit }' "$CONFIG_SRC"
}
PEER_PRIV="$(extract PrivateKey)"
PEER_ADDR="$(extract Address)"
PEER_PUB="$(extract PublicKey)"
PEER_PSK="$(extract PresharedKey)"

for v in PEER_PRIV PEER_ADDR PEER_PUB PEER_PSK; do
  if [ -z "${!v}" ]; then
    echo "error: could not parse '$v' from $CONFIG_SRC" >&2
    echo "       check the file has all four lines: PrivateKey, Address, PublicKey, PresharedKey" >&2
    exit 1
  fi
done

sudo install -d -m 700 /etc/wireguard

sudo tee /etc/wireguard/wg-direct.conf >/dev/null <<EOF
[Interface]
PrivateKey = ${PEER_PRIV}
Address = ${PEER_ADDR}
DNS = 1.1.1.1, 9.9.9.9

[Peer]
PublicKey = ${PEER_PUB}
PresharedKey = ${PEER_PSK}
Endpoint = ${SERVER_IP}:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF
sudo chmod 600 /etc/wireguard/wg-direct.conf

sudo tee /etc/wireguard/wg-obfuscated.conf >/dev/null <<EOF
[Interface]
PrivateKey = ${PEER_PRIV}
Address = ${PEER_ADDR}
DNS = 1.1.1.1, 9.9.9.9
MTU = ${MTU}
PostUp = ip route add ${SERVER_IP} via \$(ip route | awk '/default/ {print \$3; exit}')
PostDown = ip route del ${SERVER_IP} 2>/dev/null || true

[Peer]
PublicKey = ${PEER_PUB}
PresharedKey = ${PEER_PSK}
Endpoint = 127.0.0.1:${LOCAL_LISTEN_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF
sudo chmod 600 /etc/wireguard/wg-obfuscated.conf

sudo tee /etc/systemd/system/udp2raw-client.service >/dev/null <<EOF
[Unit]
Description=udp2raw client (wg endpoint -> faketcp ${SERVER_IP}:${TCP_PORT})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/udp2raw -c -l 127.0.0.1:${LOCAL_LISTEN_PORT} -r ${SERVER_IP}:${TCP_PORT} -k "${PSK}" --raw-mode faketcp -a
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo iptables -t raw -C OUTPUT -p tcp --dport ${TCP_PORT} -j NOTRACK 2>/dev/null \
  || sudo iptables -t raw -I OUTPUT -p tcp --dport ${TCP_PORT} -j NOTRACK
sudo iptables -t raw -C PREROUTING -p tcp --sport ${TCP_PORT} -j NOTRACK 2>/dev/null \
  || sudo iptables -t raw -I PREROUTING -p tcp --sport ${TCP_PORT} -j NOTRACK

sudo systemctl daemon-reload
sudo systemctl enable --now udp2raw-client
sudo systemctl restart udp2raw-client

echo
echo "================ CLIENT READY ================"
echo "  Two configs installed; one tunnel up at a time:"
echo
echo "    Direct (DPI-visible):"
echo "      sudo wg-quick up wg-direct"
echo
echo "    Obfuscated (faketcp):"
echo "      sudo wg-quick up wg-obfuscated"
echo
echo "  Tear down with: sudo wg-quick down wg-direct  (or wg-obfuscated)"
echo "==============================================="
