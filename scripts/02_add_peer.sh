#!/bin/bash
# Provision a WireGuard peer on the server.
# Usage: sudo ./02_add_peer.sh <peer_name>
# Output: /etc/wireguard/clients/<peer_name>.conf  (copy this to the client)
set -euo pipefail

PEER="${1:-}"
if [ -z "$PEER" ]; then echo "usage: $0 <peer_name>"; exit 1; fi

WG_PORT="${WG_PORT:-51820}"
WG_NET_PREFIX="${WG_NET_PREFIX:-10.66.66}"
SERVER_PUB="$(cat /etc/wireguard/server_public.key)"
SERVER_ENDPOINT="${SERVER_ENDPOINT:-$(curl -s4 ifconfig.me):${WG_PORT}}"

mkdir -p /etc/wireguard/clients
cd /etc/wireguard/clients

# Pick the next free .2-.254 address.
USED=$(awk '/AllowedIPs/ {print $3}' /etc/wireguard/wg0.conf | awk -F'[./]' '{print $4}' | sort -n)
NEXT=2
for n in $USED; do [ "$n" = "$NEXT" ] && NEXT=$((NEXT+1)); done
PEER_IP="${WG_NET_PREFIX}.${NEXT}"

umask 077
wg genkey | tee "${PEER}_priv.key" | wg pubkey > "${PEER}_pub.key"
PEER_PRIV=$(cat "${PEER}_priv.key")
PEER_PUB=$(cat "${PEER}_pub.key")
PSK=$(wg genpsk); echo "$PSK" > "${PEER}_psk.key"

# Append peer to server config and apply live.
cat >> /etc/wireguard/wg0.conf <<EOF

# peer: ${PEER}
[Peer]
PublicKey = ${PEER_PUB}
PresharedKey = ${PSK}
AllowedIPs = ${PEER_IP}/32
EOF
wg syncconf wg0 <(wg-quick strip wg0)

# Client-side config.
cat > "${PEER}.conf" <<EOF
[Interface]
PrivateKey = ${PEER_PRIV}
Address = ${PEER_IP}/24
DNS = 1.1.1.1, 9.9.9.9

[Peer]
PublicKey = ${SERVER_PUB}
PresharedKey = ${PSK}
Endpoint = ${SERVER_ENDPOINT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

echo "Peer ${PEER} added at ${PEER_IP}."
echo "Client config: /etc/wireguard/clients/${PEER}.conf"
echo "----- BEGIN ${PEER}.conf -----"
cat "${PEER}.conf"
echo "----- END ${PEER}.conf -----"
