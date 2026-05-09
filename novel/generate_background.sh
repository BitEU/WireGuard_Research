#!/bin/bash
set -euo pipefail

EVIDENCE="/media/sf_Git/evidence"
TS="$(date +%Y%m%d-%H%M%S)"
LABEL="${1:-background-https}"
DURATION="${DURATION:-90}"
IFACE="${IFACE:-eth0}"

mkdir -p "$EVIDENCE"

if [ "$EUID" -ne 0 ]; then
  echo "[!] needs root for tcpdump; re-running with sudo."
  exec sudo -E env LABEL="$LABEL" DURATION="$DURATION" IFACE="$IFACE" "$0" "$@"
fi

PCAP="${EVIDENCE}/${TS}_${LABEL}.pcap"

echo "[*] capturing ${DURATION}s of sustained HTTPS traffic on ${IFACE} -> ${PCAP}"

timeout "${DURATION}" tcpdump -i "${IFACE}" -w "${PCAP}" "tcp port 443" >/dev/null 2>&1 &
TCPDUMP_PID=$!
sleep 1

# Sustained downloads from a few large-asset sites — keeps each flow alive
# >>5s so the feature extractor accepts them. Background loop runs in
# parallel against multiple sites.
URLS=(
  "https://speed.cloudflare.com/__down?bytes=10000000"
  "https://github.com/torvalds/linux/archive/refs/heads/master.zip"
  "https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tar.xz"
  "https://cachefly.cachefly.net/100mb.test"
)

for url in "${URLS[@]}"; do
  curl -sL --max-time "${DURATION}" -o /dev/null "$url" &
done

wait "${TCPDUMP_PID}" 2>/dev/null || true
# kill any still-running curls
pkill -f "^curl -sL --max-time" 2>/dev/null || true

echo "[*] saved: ${PCAP}"
echo "[*] $(tcpdump -nn -r "${PCAP}" 2>/dev/null | wc -l) packets captured"
