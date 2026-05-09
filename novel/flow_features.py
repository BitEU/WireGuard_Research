"""Flow-feature extractor for WireGuard-vs-everything-else classification.

Reads a pcap, groups packets into bidirectional flows by 5-tuple, emits one
feature row per flow. Empirical features chosen after observing the actual
length distributions of bare-WG and WG-in-udp2raw captures:

  * Bare WireGuard: ~81% of packets are one specific size (~1386 B).
  * WG-in-udp2raw:  ~37% at the top mode, ~87% in the top three modes,
                    plus a large 60-B ACK population from faketcp.
  * Background HTTPS expected to be smoother (no extreme mode concentration).

Output is CSV. Run:
    python3 flow_features.py <pcap> --label <class>
"""
import argparse
import csv
import math
import os
import statistics
import sys
from collections import defaultdict, Counter

from scapy.all import IP, IPv6, TCP, UDP, rdpcap


def flow_key(pkt):
    if IP in pkt:
        ip = pkt[IP]
        src, dst = ip.src, ip.dst
    elif IPv6 in pkt:
        ip = pkt[IPv6]
        src, dst = ip.src, ip.dst
    else:
        return None
    if TCP in pkt:
        return ("tcp", tuple(sorted([(src, pkt[TCP].sport), (dst, pkt[TCP].dport)])))
    if UDP in pkt:
        return ("udp", tuple(sorted([(src, pkt[UDP].sport), (dst, pkt[UDP].dport)])))
    return None


def shannon_entropy(values):
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def features_for_flow(packets, label, proto):
    if len(packets) < 10:
        return None
    times = [p[0] for p in packets]
    lengths = [p[1] for p in packets]
    iats = [times[i+1] - times[i] for i in range(len(times) - 1)]

    duration = times[-1] - times[0]
    if duration < 5.0:
        return None

    size_counts = Counter(lengths)
    sorted_sizes = size_counts.most_common()
    dominant_size = sorted_sizes[0][0]
    dominant_size_count = sorted_sizes[0][1]
    top3_count = sum(c for _, c in sorted_sizes[:3])

    # TCP-only feature: 60-byte ACK ratio (no-payload segments).
    n_60byte = size_counts.get(60, 0)
    ack_to_data_ratio = n_60byte / max(1, len(lengths) - n_60byte) if proto == "tcp" else 0.0

    # WG bulk packets (full-MTU transport) on direct path are 1386 B.
    # On udp2raw they fragment to 1302/1314 B. Bulk = >= 1200 B.
    bulk_count = sum(1 for l in lengths if l >= 1200)

    return {
        "label": label,
        "proto": proto,
        "n_packets": len(packets),
        "duration_s": round(duration, 2),
        "len_mean": round(statistics.mean(lengths), 1),
        "len_stdev": round(statistics.stdev(lengths) if len(lengths) > 1 else 0, 1),
        "len_entropy": round(shannon_entropy(lengths), 3),
        "n_unique_sizes": len(size_counts),
        "dominant_size": dominant_size,
        "dominant_size_fraction": round(dominant_size_count / len(lengths), 3),
        "top3_size_fraction": round(top3_count / len(lengths), 3),
        "bulk_fraction": round(bulk_count / len(lengths), 3),
        "ack60_fraction": round(n_60byte / len(lengths), 3),
        "ack_to_data_ratio": round(ack_to_data_ratio, 3),
        "iat_mean": round(statistics.mean(iats), 4),
        "iat_stdev": round(statistics.stdev(iats) if len(iats) > 1 else 0, 4),
        "rate_pps": round(len(packets) / duration, 2),
    }


def extract_pcap(pcap_path, label, min_duration=5.0):
    pkts = rdpcap(pcap_path)
    flows = defaultdict(list)
    canonical = {}

    for pkt in pkts:
        key = flow_key(pkt)
        if key is None:
            continue
        if key not in canonical:
            if IP in pkt:
                canonical[key] = pkt[IP].src
            elif IPv6 in pkt:
                canonical[key] = pkt[IPv6].src
        flows[key].append((float(pkt.time), len(pkt)))

    rows = []
    for key, packets in flows.items():
        packets.sort(key=lambda x: x[0])
        if packets[-1][0] - packets[0][0] < min_duration:
            continue
        feat = features_for_flow(packets, label, key[0])
        if feat:
            feat["flow_key"] = f"{key[0]}:{key[1][0][0]}:{key[1][0][1]}<->{key[1][1][0]}:{key[1][1][1]}"
            rows.append(feat)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--min-duration", type=float, default=5.0)
    args = ap.parse_args()

    rows = extract_pcap(args.pcap, args.label, args.min_duration)
    if not rows:
        print(f"warning: no flows >= {args.min_duration}s in {args.pcap}", file=sys.stderr)
        return

    out = args.out or os.path.splitext(args.pcap)[0] + "_features.csv"
    fieldnames = list(rows[0].keys())
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} flows -> {out}")
    for r in rows:
        print(f"  {r['flow_key']:60s} dur={r['duration_s']:5.0f}s  "
              f"dom={r['dominant_size_fraction']:.2f}  top3={r['top3_size_fraction']:.2f}  "
              f"ack60={r['ack60_fraction']:.2f}  ent={r['len_entropy']:.2f}")


if __name__ == "__main__":
    main()
