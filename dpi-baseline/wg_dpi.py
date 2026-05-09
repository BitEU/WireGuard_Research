import argparse
import os
import sys
from collections import Counter
from datetime import datetime

from wg_classify import classify, WG_TYPES

from scapy.all import IP, IPv6, UDP, Raw, sniff, rdpcap


EVIDENCE_DIR = "/media/sf_Git/evidence"


class Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, s):
        for st in self.streams:
            st.write(s); st.flush()
    def flush(self):
        for st in self.streams:
            st.flush()


def open_evidence(label: str):
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(EVIDENCE_DIR, f"{ts}_{label}.txt")
    return open(path, "w"), path


class Stats:
    def __init__(self):
        self.counts = Counter()
        self.flows = Counter()


def make_handler(stats: Stats, port, verbose, out):
    def handle(pkt):
        if UDP not in pkt or Raw not in pkt:
            return
        udp = pkt[UDP]
        if port and udp.sport != port and udp.dport != port:
            return
        payload = bytes(pkt[Raw].load)
        result = classify(payload)
        if not result:
            return
        label, msg_type, exact = result
        stats.counts[label] += 1
        if IP in pkt:
            src, dst = pkt[IP].src, pkt[IP].dst
        elif IPv6 in pkt:
            src, dst = pkt[IPv6].src, pkt[IPv6].dst
        else:
            src = dst = "?"
        flow = (src, dst, udp.sport, udp.dport)
        stats.flows[flow] += 1
        if verbose or msg_type in (1, 2, 3):
            tag = "MATCH" if exact else "match"
            print(
                f"[{tag}] {src}:{udp.sport} -> {dst}:{udp.dport}  "
                f"len={len(payload):4d}  type={msg_type} ({label})",
                file=out,
            )
    return handle


def report(stats: Stats, out):
    print("\n=== Summary ===", file=out)
    if not stats.counts:
        print("No WireGuard traffic detected.", file=out)
        return
    total = sum(stats.counts.values())
    print(f"Total WireGuard packets detected: {total}", file=out)
    for label, n in stats.counts.most_common():
        print(f"  {label:20s} {n}", file=out)
    print("\nTop flows:", file=out)
    for (src, dst, sp, dp), n in stats.flows.most_common(10):
        print(f"  {src}:{sp} -> {dst}:{dp}   {n}", file=out)


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("-i", "--iface")
    src.add_argument("-r", "--read")
    ap.add_argument("-p", "--port", type=int, default=None)
    ap.add_argument("-c", "--count", type=int, default=0)
    ap.add_argument("-t", "--timeout", type=int, default=None,
                    help="Stop live sniff after N seconds")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--label", default=None,
                    help="Tag for the evidence file (default: 'live' or pcap basename)")
    ap.add_argument("--no-evidence", action="store_true",
                    help="Don't write to /media/sf_Git/evidence")
    args = ap.parse_args()

    if args.label:
        label = args.label
    elif args.read:
        label = os.path.splitext(os.path.basename(args.read))[0]
    else:
        label = f"live-{args.iface}"

    if args.no_evidence:
        out = sys.stdout
        ev_path = None
    else:
        ev_file, ev_path = open_evidence(label)
        out = Tee(sys.stdout, ev_file)

    bpf = "udp" + (f" and port {args.port}" if args.port else "")
    print(f"# wg_dpi.py run at {datetime.now().isoformat(timespec='seconds')}", file=out)
    print(f"# source: {'pcap=' + args.read if args.read else 'iface=' + args.iface}", file=out)
    print(f"# bpf: {bpf}", file=out)
    if ev_path:
        print(f"# evidence: {ev_path}", file=out)

    stats = Stats()
    handler = make_handler(stats, args.port, args.verbose, out)

    try:
        if args.read:
            for pkt in rdpcap(args.read):
                handler(pkt)
        else:
            print(f"[*] Sniffing on {args.iface}  (BPF: {bpf})  Ctrl-C to stop.", file=out)
            sniff(iface=args.iface, filter=bpf, prn=handler,
                  store=False, count=args.count, timeout=args.timeout)
    except PermissionError:
        sys.exit("error: need root/CAP_NET_RAW to sniff (try: sudo)")
    except KeyboardInterrupt:
        pass
    finally:
        report(stats, out)
        if ev_path:
            print(f"\n# saved: {ev_path}", file=out)


if __name__ == "__main__":
    main()
