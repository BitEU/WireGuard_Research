#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVIDENCE="/media/sf_Git/evidence"
TS="$(date +%Y%m%d-%H%M%S)"
LABEL="${1:-baseline}"
IFACE="${IFACE:-eth0}"
PORT="${PORT:-51820}"
PROTO="${PROTO:-udp}"
DURATION="${DURATION:-25}"

mkdir -p "$EVIDENCE"

if [ "$EUID" -ne 0 ]; then
  echo "[!] needs root (wg-quick, tcpdump, sniff). re-running with sudo."
  exec sudo -E env LABEL="$LABEL" IFACE="$IFACE" PORT="$PORT" PROTO="$PROTO" DURATION="$DURATION" "$0" "$@"
fi

echo "================================================================"
echo " DPI demo: ${LABEL}    iface=${IFACE} ${PROTO}/${PORT}    ${TS}"
echo " capture window: ${DURATION}s"
echo "================================================================"

PCAP="${EVIDENCE}/${TS}_${LABEL}.pcap"

echo "[1/4] classifier self-test"
python3 "${HERE}/test_synthetic.py"
echo

echo "[2/4] starting tcpdump (${DURATION}s)  -> ${PCAP}"
if [ "${PROTO}" = "any" ]; then
  BPF="port ${PORT}"
else
  BPF="${PROTO} port ${PORT}"
fi
timeout "${DURATION}" tcpdump -i "${IFACE}" -w "${PCAP}" ${BPF} >/dev/null 2>&1 &
TCPDUMP_PID=$!
sleep 1

WG_IF="$(ip -o link show type wireguard 2>/dev/null | awk -F': ' '{print $2}' | head -n1)"
if [ -z "${WG_IF}" ]; then
  echo "[!] no WireGuard interface up. bring one up first (wg-quick up wg-direct or wg-obfuscated)" >&2
  kill "${TCPDUMP_PID}" 2>/dev/null || true
  exit 1
fi
echo "[3/4] traffic gen: bouncing ${WG_IF}, waiting for handshake, then ping + curl"
wg-quick down "${WG_IF}" 2>/dev/null || true
wg-quick up "${WG_IF}"

for i in $(seq 1 30); do
  hs=$(wg show "${WG_IF}" latest-handshakes 2>/dev/null | awk '{print $2}')
  if [ -n "${hs}" ] && [ "${hs}" != "0" ]; then
    echo "    handshake established after ${i}s"
    break
  fi
  sleep 1
done

ping -c 5 -W 2 10.66.66.1 || true
curl -s --max-time 8 https://api.ipify.org && echo || echo "(curl failed)"

wait "${TCPDUMP_PID}" 2>/dev/null || true

echo
echo "[4/4] post-processing pcap  -> evidence/${TS}_${LABEL}-pcap.txt"
python3 "${HERE}/wg_dpi.py" -r "${PCAP}" --verbose --label "${LABEL}-pcap"

echo
echo "================================================================"
echo " done. recent artifacts in ${EVIDENCE}:"
ls -1t "${EVIDENCE}" | head -10 | sed 's/^/   /'
echo "================================================================"
