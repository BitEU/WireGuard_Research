#!/bin/bash
set +e

echo "[*] tearing down any active wg interface"
sudo wg-quick down wg-direct 2>/dev/null
sudo wg-quick down wg-obfuscated 2>/dev/null
sudo wg-quick down wg0 2>/dev/null

echo "[*] stopping services"
sudo systemctl disable --now udp2raw-client 2>/dev/null
sudo rm -f /etc/systemd/system/udp2raw-client.service
sudo systemctl daemon-reload

echo "[*] removing wireguard configs"
sudo rm -rf /etc/wireguard

echo "[*] removing udp2raw binary"
sudo rm -f /usr/local/bin/udp2raw

echo "[*] removing iptables NOTRACK rules"
sudo iptables -t raw -D OUTPUT -p tcp --dport 4096 -j NOTRACK 2>/dev/null
sudo iptables -t raw -D PREROUTING -p tcp --sport 4096 -j NOTRACK 2>/dev/null

echo
echo "================ CLIENT NUKED ================"
echo "  All WireGuard + udp2raw state removed."
echo "  Run scripts/03_client_install.sh to rebuild."
echo "==============================================="
