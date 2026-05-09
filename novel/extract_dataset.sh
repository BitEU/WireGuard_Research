#!/bin/bash
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: $0 <pcap_dir> <label> [output_csv] [max_files]"
  echo "  recursively finds .pcap/.pcapng under <pcap_dir>, samples up to"
  echo "  max_files (default 30, sorted by size ascending — small first)"
  echo "  and extracts features tagging each flow with <label>."
  exit 1
fi

DIR="$1"
LABEL="$2"
OUT="${3:-/media/sf_Git/evidence/$(date +%Y%m%d-%H%M%S)_${LABEL}_combined.csv}"
MAX_FILES="${4:-30}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$DIR" ]; then
  echo "error: $DIR is not a directory"; exit 1
fi

TMP="$(mktemp -d)"
trap "rm -rf $TMP" EXIT

mapfile -t PCAPS < <(find "$DIR" -type f \( -name '*.pcap' -o -name '*.pcapng' \) -printf '%s %p\n' | sort -n | head -n "$MAX_FILES" | cut -d' ' -f2-)
echo "[*] sampling ${#PCAPS[@]} pcap(s) from $DIR (smallest first, max=$MAX_FILES)"

count=0
for p in "${PCAPS[@]}"; do
  count=$((count+1))
  size=$(du -h "$p" | cut -f1)
  printf "[%2d/%d] %-8s %s\n" "$count" "${#PCAPS[@]}" "$size" "$(basename "$p")"
  python3 "$HERE/flow_features.py" "$p" --label "$LABEL" \
    --out "$TMP/$count.csv" 2>/dev/null || continue
done

# concat, header from first non-empty file only
HEAD_DONE=0
> "$OUT"
for f in "$TMP"/*.csv; do
  [ -s "$f" ] || continue
  if [ "$HEAD_DONE" -eq 0 ]; then
    cat "$f" >> "$OUT"
    HEAD_DONE=1
  else
    tail -n +2 "$f" >> "$OUT"
  fi
done

ROWS=$(($(wc -l < "$OUT") - 1))
echo "[*] wrote $ROWS flows -> $OUT"
