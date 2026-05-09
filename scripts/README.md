# Setup from zero

Five scripts. Run them in order. Each is idempotent — safe to re-run.

## On the OCI server (run from your Windows host)

```powershell
$key = "..\creds\ssh-key-2026-05-08.key"
scp -i $key .\01_server_install.sh .\02_add_peer.sh opc@158.101.122.42:/home/opc/
ssh -i $key opc@158.101.122.42 "bash ~/01_server_install.sh"
ssh -i $key opc@158.101.122.42 "sudo bash ~/02_add_peer.sh lab-client"
```

The second `ssh` prints the client config. Save it to `configs/lab-client.conf`:

```powershell
ssh -i $key opc@158.101.122.42 "sudo cat /etc/wireguard/clients/lab-client.conf" |
  Out-File -Encoding ascii ..\configs\lab-client.conf
```

## In the OCI web console

Open **two** ingress rules on the VCN's default security list (Source `0.0.0.0/0`):
- UDP port `51820` — the unobfuscated WireGuard path
- TCP port `4096`  — the obfuscated faketcp path

## In the Kali VM (with the project folder shared at `/media/sf_Git`)

```bash
sudo bash /media/sf_Git/scripts/03_client_install.sh
```

This installs WireGuard + udp2raw + Scapy/tshark, drops in **two** WireGuard configs, and starts the udp2raw client as a systemd service.

## Run the demo

```bash
# Direct WireGuard — DPI sees the handshake
sudo wg-quick up wg-direct
PROTO=udp PORT=51820 /media/sf_Git/dpi/run_demo.sh baseline
sudo wg-quick down wg-direct

# Obfuscated WireGuard — DPI sees nothing
sudo wg-quick up wg-obfuscated
PROTO=any PORT=4096 /media/sf_Git/dpi/run_demo.sh udp2raw
sudo wg-quick down wg-obfuscated
```

Evidence text + pcap files land in `/media/sf_Git/evidence/`.

## Nuke and start over

```bash
# Server
ssh -i $key opc@158.101.122.42 "bash ~/99_server_teardown.sh"

# Client
sudo bash /media/sf_Git/scripts/99_client_teardown.sh
```
