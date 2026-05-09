#!/bin/bash
set +e

echo "[*] stopping services"
sudo systemctl disable --now wg-quick@wg0 2>/dev/null
sudo systemctl disable --now udp2raw-server 2>/dev/null

echo "[*] removing unit files"
sudo rm -f /etc/systemd/system/udp2raw-server.service
sudo systemctl daemon-reload

echo "[*] removing wireguard configs and keys"
sudo rm -rf /etc/wireguard

echo "[*] removing udp2raw binary"
sudo rm -f /usr/local/bin/udp2raw

echo "[*] removing iptables rules we added"
sudo iptables -D INPUT -p udp --dport 51820 -j ACCEPT 2>/dev/null
sudo iptables -D INPUT -p tcp --dport 4096 -j ACCEPT 2>/dev/null
sudo iptables -t raw -D PREROUTING -p tcp --dport 4096 -j NOTRACK 2>/dev/null
sudo iptables -t raw -D OUTPUT -p tcp --sport 4096 -j NOTRACK 2>/dev/null
sudo bash -c 'iptables-save > /etc/sysconfig/iptables' 2>/dev/null

echo "[*] removing firewalld port allowances"
if systemctl is-active --quiet firewalld; then
  sudo firewall-cmd --permanent --remove-port=51820/udp 2>/dev/null
  sudo firewall-cmd --permanent --remove-port=4096/tcp 2>/dev/null
  sudo firewall-cmd --reload 2>/dev/null
fi

echo "[*] removing sysctl override"
sudo rm -f /etc/sysctl.d/99-wireguard.conf

echo
echo "================ SERVER NUKED ================"
echo "  All WireGuard + udp2raw state removed."
echo "  Run scripts/01_server_install.sh to rebuild."
echo "  (OCI ingress rules in the console are NOT touched.)"
echo "==============================================="
