"""Active probe for udp2raw faketcp.

Hypothesis: udp2raw's --raw-mode faketcp emulates TCP at the packet level but
does not maintain a real kernel TCP socket. It listens for SYN packets via
AF_PACKET, hands them to its own state machine, and silently drops or
non-conformantly responds to anything that doesn't fit its expected handshake
pattern. We exploit this with five lightweight probes.

The probes are designed to be cheap (one or two packets each), deterministic,
and harmless to a real TCP server (a real server will return RST or ignore).

Run:
    sudo python3 active_probe.py 158.101.122.42 4096
    sudo python3 active_probe.py 158.101.122.42 22       # control: real TCP
    sudo python3 active_probe.py 158.101.122.42 9999     # control: closed

Output is a verdict line and per-probe results, also written to
/media/sf_Git/evidence/<ts>_active-probe_<host>_<port>.txt
"""
import argparse
import os
import random
import socket
import sys
import time
from datetime import datetime

from scapy.all import IP, TCP, sr1, send, conf

conf.verb = 0
EVIDENCE_DIR = "/media/sf_Git/evidence"


class Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, s):
        for st in self.streams: st.write(s); st.flush()
    def flush(self):
        for st in self.streams: st.flush()


def open_evidence(host, port):
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(EVIDENCE_DIR, f"{ts}_active-probe_{host}_{port}.txt")
    return open(path, "w"), path


def probe_1_baseline_syn(host, port, sport):
    """Baseline: send a normal SYN, expect SYN-ACK from real TCP. udp2raw
    accepts SYNs as part of its faketcp handshake but only responds with its
    own crafted SYN-ACK (which a real kernel sees, then a kernel RST follows
    because the kernel never actually opened a socket)."""
    t0 = time.time()
    pkt = IP(dst=host)/TCP(sport=sport, dport=port, flags="S", seq=random.randint(0, 2**32 - 1))
    resp = sr1(pkt, timeout=3)
    rtt_ms = int((time.time() - t0) * 1000)
    if resp is None:
        return {"probe": "syn", "outcome": "no_response", "rtt_ms": rtt_ms}
    if not resp.haslayer(TCP):
        return {"probe": "syn", "outcome": "non_tcp_response", "rtt_ms": rtt_ms}
    flags = resp[TCP].flags
    return {
        "probe": "syn",
        "outcome": "syn_ack" if flags & 0x12 == 0x12 else "rst" if flags & 0x04 else f"flags={int(flags)}",
        "rtt_ms": rtt_ms,
        "ttl": resp[IP].ttl,
        "win": resp[TCP].window,
        "options": [(o[0], o[1]) for o in resp[TCP].options] if resp[TCP].options else [],
    }


def probe_2_syn_with_payload(host, port, sport):
    """RFC 9293 says SYN segments MUST NOT contain data unless TCP Fast Open
    is in use. A real Linux kernel ignores the payload. udp2raw's faketcp
    parser may consume it, leading to its handshake1/handshake2 state
    advancing on a single packet. We look for an unusual response."""
    payload = b"\x00" * 32
    pkt = IP(dst=host)/TCP(sport=sport, dport=port, flags="S", seq=random.randint(0, 2**32 - 1))/payload
    resp = sr1(pkt, timeout=3)
    if resp is None:
        return {"probe": "syn_with_payload", "outcome": "no_response"}
    return {
        "probe": "syn_with_payload",
        "outcome": "response",
        "resp_flags": int(resp[TCP].flags) if resp.haslayer(TCP) else None,
        "resp_payload_len": len(bytes(resp[TCP].payload)) if resp.haslayer(TCP) else 0,
    }


def probe_3_bogus_seq_ack(host, port, sport):
    """Send an ACK with a wildly wrong sequence number to a port that has no
    open connection. RFC 9293 says: real TCP responds with RST. udp2raw's
    faketcp doesn't claim the packet, so the host kernel eventually emits a
    RST instead --- but that RST takes ~3s vs. ~100ms for a real listener,
    because udp2raw's AF_PACKET hook delays kernel delivery."""
    t0 = time.time()
    pkt = IP(dst=host)/TCP(sport=sport, dport=port, flags="A", seq=0xDEADBEEF, ack=0xCAFEBABE)
    resp = sr1(pkt, timeout=4)
    rtt_ms = int((time.time() - t0) * 1000)
    if resp is None:
        return {"probe": "bogus_ack", "outcome": "no_rst", "rtt_ms": rtt_ms}
    if resp.haslayer(TCP) and resp[TCP].flags & 0x04:
        return {"probe": "bogus_ack", "outcome": "rst", "rtt_ms": rtt_ms}
    return {"probe": "bogus_ack", "outcome": "other", "rtt_ms": rtt_ms,
            "flags": int(resp[TCP].flags) if resp.haslayer(TCP) else None}


def probe_4_window_scale(host, port, sport):
    """Real TCP servers echo or omit window-scale based on whether the SYN
    advertised it. udp2raw's faketcp has a fixed set of TCP options it emits
    regardless of what the client sent. Send a SYN with an extreme WS=14 and
    see if the response acknowledges or ignores it."""
    pkt = IP(dst=host)/TCP(sport=sport, dport=port, flags="S",
                           seq=random.randint(0, 2**32 - 1),
                           options=[("WScale", 14), ("MSS", 1460)])
    resp = sr1(pkt, timeout=3)
    if resp is None or not resp.haslayer(TCP):
        return {"probe": "wscale", "outcome": "no_response"}
    options = [(o[0], o[1]) for o in resp[TCP].options]
    ws_seen = next((v for k, v in options if k == "WScale"), None)
    return {
        "probe": "wscale",
        "outcome": "response",
        "options": options,
        "wscale_returned": ws_seen,
    }


def probe_5_fin_to_unopened(host, port, sport):
    """Send a FIN to a port with no established connection. Real TCP: RST or
    silent drop. udp2raw faketcp: typically ignored entirely (no state)."""
    pkt = IP(dst=host)/TCP(sport=sport, dport=port, flags="F", seq=random.randint(0, 2**32 - 1))
    resp = sr1(pkt, timeout=2)
    if resp is None:
        return {"probe": "fin_to_unopened", "outcome": "no_response"}
    if resp.haslayer(TCP) and resp[TCP].flags & 0x04:
        return {"probe": "fin_to_unopened", "outcome": "rst"}
    return {"probe": "fin_to_unopened", "outcome": "other"}


SLOW_RST_THRESHOLD_MS = 1000


def classify(results):
    """Decide REAL_TCP vs UDP2RAW_FAKETCP vs PORT_CLOSED.

    The discriminator is the *combination* of:
      * syn:        both real TCP and udp2raw answer SYN-ACK
      * syn_payload: real TCP answers SYN-ACK; udp2raw drops the packet
      * bogus_ack:  real TCP answers RST in <100ms; udp2raw answers RST in
                    ~3s (kernel timeout, because udp2raw consumed the packet
                    via AF_PACKET) or no answer
      * wscale:     real TCP answers SYN-ACK; udp2raw drops it (custom
                    parser rejects unexpected option layout)
      * fin:        real TCP answers RST; udp2raw silent

    The latency on probe 3 (bogus_ack) is the cleanest single signal."""
    p = {r["probe"]: r for r in results}
    syn = p["syn"]["outcome"]
    syn_payload = p["syn_with_payload"]["outcome"]
    bogus = p["bogus_ack"]["outcome"]
    bogus_rtt = p["bogus_ack"].get("rtt_ms", 0)
    wscale = p["wscale"]["outcome"]
    fin = p["fin_to_unopened"]["outcome"]

    if syn == "no_response":
        return "UNREACHABLE_OR_FILTERED", \
               "no SYN-ACK and no RST on initial probe"

    if syn == "rst":
        return "PORT_CLOSED", "kernel RST on SYN: no listener"

    silent_count = sum(1 for x in (syn_payload, wscale, fin) if x == "no_response")
    slow_rst = (bogus == "rst" and bogus_rtt >= SLOW_RST_THRESHOLD_MS)

    if syn == "syn_ack" and (silent_count >= 2 or slow_rst):
        reasons = []
        if silent_count >= 2:
            reasons.append(f"{silent_count}/3 follow-up probes silent")
        if slow_rst:
            reasons.append(f"bogus-ACK RST took {bogus_rtt}ms (real TCP <100ms)")
        return "UDP2RAW_FAKETCP_SUSPECTED", "; ".join(reasons)

    if syn == "syn_ack" and bogus == "rst" and bogus_rtt < SLOW_RST_THRESHOLD_MS \
       and silent_count == 0:
        return "REAL_TCP", \
               f"prompt SYN-ACK, prompt kernel RST ({bogus_rtt}ms), all probes answered"

    return "INCONCLUSIVE", \
           f"syn={syn}, syn_payload={syn_payload}, bogus_ack={bogus}@{bogus_rtt}ms, " \
           f"wscale={wscale}, fin={fin}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("port", type=int)
    ap.add_argument("--no-evidence", action="store_true")
    args = ap.parse_args()

    if os.geteuid() != 0:
        sys.exit("error: needs root for raw socket sends (try: sudo)")

    if args.no_evidence:
        out = sys.stdout
        path = None
    else:
        f, path = open_evidence(args.host, args.port)
        out = Tee(sys.stdout, f)

    sport = random.randint(40000, 65000)
    print(f"# active_probe.py at {datetime.now().isoformat(timespec='seconds')}", file=out)
    print(f"# target: {args.host}:{args.port}", file=out)
    print(f"# source port: {sport}", file=out)
    if path:
        print(f"# evidence: {path}", file=out)

    probes = [
        probe_1_baseline_syn,
        probe_2_syn_with_payload,
        probe_3_bogus_seq_ack,
        probe_4_window_scale,
        probe_5_fin_to_unopened,
    ]
    results = []
    t0 = time.time()
    for fn in probes:
        r = fn(args.host, args.port, sport)
        elapsed_ms = int((time.time() - t0) * 1000)
        print(f"  [{elapsed_ms:5d}ms] {r}", file=out)
        results.append(r)

    verdict, reason = classify(results)
    total_ms = int((time.time() - t0) * 1000)
    print(file=out)
    print(f"=== verdict: {verdict} ===", file=out)
    print(f"  reason: {reason}", file=out)
    print(f"  total time: {total_ms} ms", file=out)
    if path:
        print(f"\n# saved: {path}", file=out)


if __name__ == "__main__":
    main()
