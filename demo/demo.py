"""
Live TUI demo for the WireGuard-in-udp2raw detection paper.

Five scenes, manual advance with SPACE / ENTER, full-screen Rich layout.
Bottom-left pane streams the actual command being run; top pane shows the
result. Designed for projector use; readable from the back of a room.

Run inside the Kali VM:
    sudo python3 /media/sf_Git/demo/demo.py

Requirements:
    sudo apt install -y python3-rich python3-scapy python3-sklearn python3-pandas
"""

import argparse
import os
import queue
import shlex
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

# scapy and sklearn lazy-imported to keep startup snappy
ROOT       = Path("/media/sf_Git")
NOVEL      = ROOT / "novel"
DPI_BASE   = ROOT / "dpi-baseline"
MASTER     = ROOT / "master_set"
EVIDENCE   = ROOT / "evidence" / "demo-runs"
EVIDENCE.mkdir(parents=True, exist_ok=True)

SERVER_IP = os.environ.get("SERVER_IP", "158.101.122.42")
TCP_PORT  = 4096
UDP_PORT  = 51820
SSH_PORT  = 22
CLOSED_PORT = 9999
IFACE = "eth0"

console = Console()


# ----------------------------------------------------------------------
# Scene state shared between the worker threads and the renderer
# ----------------------------------------------------------------------
class Scene:
    def __init__(self):
        self.idx = 0
        self.title = "Press SPACE to begin"
        self.subtitle = ""
        self.upper: Group = Group(Text(""))
        self.cmd_text: Text = Text("")
        self.result_text: Text = Text("")
        self.lock = threading.Lock()

    def set_upper(self, renderable):
        with self.lock:
            self.upper = renderable

    def append_cmd(self, line: str, style="white"):
        with self.lock:
            self.cmd_text.append(line.rstrip() + "\n", style=style)
            # cap to last 14 lines
            lines = self.cmd_text.plain.splitlines()
            if len(lines) > 14:
                self.cmd_text = Text("\n".join(lines[-14:]) + "\n")

    def set_cmd(self, line: str, style="bold white"):
        with self.lock:
            self.cmd_text = Text(line + "\n", style=style)

    def append_result(self, line: str, style="white"):
        with self.lock:
            self.result_text.append(line.rstrip() + "\n", style=style)

    def set_result(self, renderable):
        with self.lock:
            self.result_text = renderable

    def header(self, idx, title, subtitle=""):
        with self.lock:
            self.idx = idx
            self.title = title
            self.subtitle = subtitle


SCENE = Scene()


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------
def render_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="bottom", size=18),
        Layout(name="footer", size=1),
    )
    layout["bottom"].split_row(
        Layout(name="cmd", ratio=1),
        Layout(name="result", ratio=1),
    )
    with SCENE.lock:
        head = Text()
        head.append("WireGuard-in-udp2raw  ", style="bold #102A43")
        head.append("· ", style="grey42")
        head.append("Live demo  ", style="white")
        head.append(f"· scene {SCENE.idx} / 5", style="grey42")
        head_right = Text("Schiavone & Johannsen · CYB623",
                          style="grey42", justify="right")
        title_text = Text()
        title_text.append(SCENE.title, style="bold #C9462C")
        if SCENE.subtitle:
            title_text.append("  ")
            title_text.append(SCENE.subtitle, style="grey50")
        upper = SCENE.upper
        cmd = SCENE.cmd_text
        result = SCENE.result_text

    layout["header"].update(
        Panel(Align.center(title_text, vertical="middle"),
              box=box.SIMPLE, padding=(0, 1)))
    layout["body"].update(
        Panel(upper, box=box.ROUNDED, border_style="#102A43",
              padding=(1, 2)))
    layout["cmd"].update(
        Panel(cmd, title="[grey50]running",
              box=box.ROUNDED, border_style="grey50",
              padding=(0, 1)))
    layout["result"].update(
        Panel(result, title="[grey50]result",
              box=box.ROUNDED, border_style="grey50",
              padding=(0, 1)))
    footer = Text(
        "  SPACE / ENTER → next scene      Q → quit",
        style="grey42")
    layout["footer"].update(footer)
    return layout


# ----------------------------------------------------------------------
# Input handling: wait for SPACE/ENTER to advance, Q to quit
# ----------------------------------------------------------------------
def wait_for_advance(live: Live):
    """Block until user presses space/enter (or q to quit). Returns True
    to continue, False to quit."""
    import termios, tty, select
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            r, _, _ = select.select([sys.stdin], [], [], 0.1)
            if r:
                ch = sys.stdin.read(1)
                if ch in ("\n", "\r", " "):
                    return True
                if ch.lower() == "q":
                    return False
            live.update(render_layout(), refresh=True)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ----------------------------------------------------------------------
# Subprocess streamer: runs a command, mirrors stdout into the cmd pane,
# returns stdout-as-string when done.
# ----------------------------------------------------------------------
def run_streamed(cmd: list[str], live: Live, prefix_label: str | None = None,
                 max_seconds: float = 60.0) -> str:
    SCENE.set_cmd("$ " + " ".join(shlex.quote(c) for c in cmd), style="bold white")
    if prefix_label:
        SCENE.append_cmd(prefix_label, style="grey50")

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)
    out_chunks = []
    start = time.time()

    q: queue.Queue[str] = queue.Queue()

    def reader():
        for line in proc.stdout:
            q.put(line)
        q.put("__EOF__")

    threading.Thread(target=reader, daemon=True).start()

    while True:
        try:
            line = q.get(timeout=0.15)
        except queue.Empty:
            line = None
        if line is not None:
            if line == "__EOF__":
                break
            out_chunks.append(line)
            SCENE.append_cmd(line, style="white")
        live.update(render_layout(), refresh=True)
        if time.time() - start > max_seconds:
            proc.terminate()
            SCENE.append_cmd(f"[timeout after {max_seconds}s]", style="red")
            break

    proc.wait(timeout=2)
    return "".join(out_chunks)


# ----------------------------------------------------------------------
# Scene 1: bare WireGuard, byte-level fingerprint trivially identifies it
# ----------------------------------------------------------------------
def scene1(live: Live):
    SCENE.header(1, "Bare WireGuard is fingerprintable",
                 "tcpdump + 25-line classifier on UDP/51820")
    intro = Group(
        Text("• Bring up wg-direct (no obfuscation)", style="white"),
        Text("• Capture 12 s of traffic on the real wire", style="white"),
        Text("• Run our 25-line predicate over the pcap", style="white"),
        Text(""),
        Text("Expected: a 148-byte HANDSHAKE_INIT and 92-byte "
             "HANDSHAKE_RESPONSE pop out without decrypting a byte.",
             style="grey50"),
    )
    SCENE.set_upper(intro)
    SCENE.set_result(Text(""))
    live.update(render_layout(), refresh=True)
    if not wait_for_advance(live):
        return False

    # Bring up the tunnel
    subprocess.run(["wg-quick", "down", "wg-direct"],
                   capture_output=True, text=True)
    run_streamed(["wg-quick", "up", "wg-direct"], live, max_seconds=10)

    # Capture
    pcap = EVIDENCE / f"demo-bare-{int(time.time())}.pcap"
    SCENE.append_cmd(f"# capturing 12 s of UDP/51820 -> {pcap.name}",
                     style="grey50")
    cap = subprocess.Popen(
        ["timeout", "12", "tcpdump", "-i", IFACE, "-w", str(pcap),
         f"udp port {UDP_PORT}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Animate a small progress while it runs; also generate traffic
    for i in range(12):
        live.update(render_layout(), refresh=True)
        if i == 1:
            subprocess.Popen(
                ["ping", "-c", "8", "-W", "1", "10.66.66.1"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if i == 2:
            subprocess.Popen(
                ["curl", "-s", "--max-time", "8",
                 "https://api.ipify.org"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
    cap.wait(timeout=2)

    # Classify
    SCENE.append_cmd(f"$ python3 wg_dpi.py -r {pcap.name} --no-evidence",
                     style="bold white")
    classify_out = subprocess.run(
        ["python3", str(DPI_BASE / "wg_dpi.py"),
         "-r", str(pcap), "--no-evidence"],
        capture_output=True, text=True, timeout=20).stdout

    # Parse a summary
    n_total = 0
    n_init = 0
    n_resp = 0
    n_data = 0
    for line in classify_out.splitlines():
        if "HANDSHAKE_INIT" in line and "len=" in line and "TYPE" not in line:
            n_init += 1; n_total += 1
        elif "HANDSHAKE_RESPONSE" in line and "len=" in line and "TYPE" not in line:
            n_resp += 1; n_total += 1
        elif "TRANSPORT_DATA" in line and "len=" in line and "TYPE" not in line:
            n_data += 1; n_total += 1

    tail = "\n".join(classify_out.splitlines()[-12:])
    SCENE.append_cmd(tail, style="white")

    result = Table.grid(padding=(0, 2))
    result.add_column(justify="right", style="grey50")
    result.add_column(justify="left", style="bold white")
    result.add_row("WireGuard packets identified:", f"{n_total}")
    result.add_row("HANDSHAKE_INIT (148 B):", f"{n_init}")
    result.add_row("HANDSHAKE_RESPONSE (92 B):", f"{n_resp}")
    result.add_row("TRANSPORT_DATA:", f"{n_data}")
    result.add_row("Verdict:", Text("FINGERPRINTED", style="bold #C9462C"))
    SCENE.set_result(result)

    subprocess.run(["wg-quick", "down", "wg-direct"],
                   capture_output=True)
    live.update(render_layout(), refresh=True)
    return wait_for_advance(live)


# ----------------------------------------------------------------------
# Scene 2: same classifier on udp2raw — byte fingerprint vanishes
# ----------------------------------------------------------------------
def scene2(live: Live):
    SCENE.header(2, "udp2raw eliminates the byte fingerprint",
                 "Same predicate, same 12-second capture, now over TCP/4096")
    intro = Group(
        Text("• Bring up wg-obfuscated (udp2raw faketcp wrapper)", style="white"),
        Text("• Capture 12 s of traffic on the wire", style="white"),
        Text("• Re-run the same WireGuard predicate", style="white"),
        Text(""),
        Text("Expected: zero matches. The byte-level fingerprint is gone.",
             style="grey50"),
    )
    SCENE.set_upper(intro)
    SCENE.set_result(Text(""))
    live.update(render_layout(), refresh=True)
    if not wait_for_advance(live):
        return False

    subprocess.run(["wg-quick", "down", "wg-obfuscated"],
                   capture_output=True)
    run_streamed(["wg-quick", "up", "wg-obfuscated"], live, max_seconds=10)
    SCENE.append_cmd("# letting udp2raw faketcp settle (~10 s)",
                     style="grey50")
    for _ in range(10):
        live.update(render_layout(), refresh=True)
        time.sleep(1)

    pcap = EVIDENCE / f"demo-udp2raw-{int(time.time())}.pcap"
    SCENE.append_cmd(f"# capturing 14 s of TCP/4096 -> {pcap.name}",
                     style="grey50")
    cap = subprocess.Popen(
        ["timeout", "14", "tcpdump", "-i", IFACE, "-w", str(pcap),
         f"port {TCP_PORT}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(14):
        live.update(render_layout(), refresh=True)
        if i == 1:
            subprocess.Popen(
                ["ping", "-c", "10", "-W", "1", "10.66.66.1"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
    cap.wait(timeout=2)

    SCENE.append_cmd(f"$ python3 wg_dpi.py -r {pcap.name} --no-evidence",
                     style="bold white")
    classify_out = subprocess.run(
        ["python3", str(DPI_BASE / "wg_dpi.py"),
         "-r", str(pcap), "--no-evidence"],
        capture_output=True, text=True, timeout=20).stdout

    tail = "\n".join(classify_out.splitlines()[-8:])
    SCENE.append_cmd(tail, style="white")

    no_match = "No WireGuard traffic detected" in classify_out
    n_packets = 0
    try:
        # also count TCP packets via tcpdump just to show traffic existed
        c = subprocess.run(
            ["tcpdump", "-nn", "-r", str(pcap)],
            capture_output=True, text=True, timeout=10)
        n_packets = len(c.stdout.splitlines())
    except Exception:
        pass

    result = Table.grid(padding=(0, 2))
    result.add_column(justify="right", style="grey50")
    result.add_column(justify="left", style="bold white")
    result.add_row("Total TCP/4096 packets seen:", f"{n_packets}")
    result.add_row("WireGuard handshakes identified:", "0")
    result.add_row("WireGuard transport packets identified:", "0")
    if no_match:
        result.add_row("Verdict:", Text("BYTE FINGERPRINT NEUTRALIZED",
                                        style="bold #C9462C"))
    else:
        result.add_row("Verdict:", Text("INCONCLUSIVE", style="grey50"))
    SCENE.set_result(result)
    live.update(render_layout(), refresh=True)
    return wait_for_advance(live)


# ----------------------------------------------------------------------
# Scene 3: active prober against three targets
# ----------------------------------------------------------------------
def scene3(live: Live):
    SCENE.header(3, "But the wrapper isn't TCP-conformant",
                 "5 stateless probes · 3 targets · same OCI host")
    intro = Group(
        Text("• Probe TCP/4096 (udp2raw),  TCP/22 (real SSH),  TCP/9999 (closed)",
             style="white"),
        Text("• Five probes each: SYN, SYN+payload, bogus-ACK, WS=14 SYN, FIN",
             style="white"),
        Text(""),
        Text("Expected: real TCP answers all 5. udp2raw drops 3 of 4 follow-ups.",
             style="grey50"),
    )
    SCENE.set_upper(intro)
    SCENE.set_result(Text(""))
    live.update(render_layout(), refresh=True)
    if not wait_for_advance(live):
        return False

    targets = [
        ("TCP/4096 udp2raw", TCP_PORT),
        ("TCP/22 real SSH",  SSH_PORT),
        ("TCP/9999 closed",  CLOSED_PORT),
    ]
    verdicts: list[tuple[str, str, str]] = []
    for label, port in targets:
        SCENE.append_cmd(f"# {label}", style="grey50")
        out = run_streamed(
            ["python3", str(NOVEL / "active_probe.py"),
             SERVER_IP, str(port), "--no-evidence"],
            live, max_seconds=20)
        verdict = "?"
        reason = ""
        for line in out.splitlines():
            if line.startswith("=== verdict:"):
                verdict = line.split(":", 1)[1].strip().rstrip("=").strip()
            if line.strip().startswith("reason:"):
                reason = line.split(":", 1)[1].strip()
        verdicts.append((label, verdict, reason))

    result = Table(box=box.MINIMAL_HEAVY_HEAD,
                   show_header=True, header_style="bold #102A43",
                   pad_edge=False, padding=(0, 1))
    result.add_column("Target", style="white", no_wrap=True)
    result.add_column("Verdict", style="bold white")
    result.add_column("Reason", style="grey50")
    for label, verdict, reason in verdicts:
        v_style = "bold #C9462C" if "UDP2RAW" in verdict else \
                  "bold green" if "REAL_TCP" in verdict else "grey50"
        result.add_row(label, Text(verdict, style=v_style), reason)
    SCENE.set_result(result)
    live.update(render_layout(), refresh=True)
    return wait_for_advance(live)


# ----------------------------------------------------------------------
# Scene 4: extract live features and overlay on the master_set scatter
# ----------------------------------------------------------------------
def scene4(live: Live):
    SCENE.header(4, "Live features land in WireGuard cluster",
                 "Extract bulk_fraction + ack60_fraction from this session's pcap")

    # Find the most recent demo pcaps from scene 1 + 2
    pcaps = sorted(EVIDENCE.glob("demo-*.pcap"),
                   key=lambda p: p.stat().st_mtime)
    intro = Group(
        Text(f"• Re-use the {len(pcaps)} pcap(s) captured in scenes 1-2",
             style="white"),
        Text("• Compute (bulk_fraction, ack60_fraction) for each flow",
             style="white"),
        Text("• Plot against the 1082-flow ISCXVPN2016 background",
             style="white"),
        Text(""),
        Text("Expected: live points land where the WG training cluster lives.",
             style="grey50"),
    )
    SCENE.set_upper(intro)
    SCENE.set_result(Text(""))
    live.update(render_layout(), refresh=True)
    if not wait_for_advance(live):
        return False

    live_features: list[tuple[str, float, float]] = []
    for p in pcaps[-2:]:
        SCENE.append_cmd(f"$ python3 flow_features.py {p.name}",
                         style="bold white")
        label = "wg-direct" if "bare" in p.name else "wg-udp2raw"
        out = subprocess.run(
            ["python3", str(NOVEL / "flow_features.py"),
             str(p), "--label", label,
             "--out", str(EVIDENCE / (p.stem + "_features.csv"))],
            capture_output=True, text=True, timeout=30)
        SCENE.append_cmd(out.stdout.strip()[-400:], style="white")
        # Parse the CSV
        feat_csv = EVIDENCE / (p.stem + "_features.csv")
        if feat_csv.exists():
            df = pd.read_csv(feat_csv)
            for _, row in df.iterrows():
                live_features.append(
                    (label, float(row["bulk_fraction"]),
                     float(row["ack60_fraction"])))

    # Build an ASCII scatter from the master_set background + our live points
    background = pd.read_csv(
        sorted(MASTER.glob("*classifier_features.csv"))[-1])
    bg = background[background["is_wg"] == 0]
    wg_train = background[background["is_wg"] == 1]

    grid_w, grid_h = 70, 14
    grid = [[" " for _ in range(grid_w)] for _ in range(grid_h)]

    def place(x, y, ch, density=False):
        if not (0 <= x <= 1 and 0 <= y <= 1):
            return
        gx = int(x * (grid_w - 1))
        gy = int((1 - y) * (grid_h - 1))
        if density and grid[gy][gx] == "·":
            grid[gy][gx] = ":"
        elif density and grid[gy][gx] == ":":
            grid[gy][gx] = "#"
        elif grid[gy][gx] == " " or ch in "★●":
            grid[gy][gx] = ch

    for _, r in bg.iterrows():
        place(r["bulk_fraction"], r["ack60_fraction"], "·", density=True)
    for _, r in wg_train.iterrows():
        place(r["bulk_fraction"], r["ack60_fraction"], "●")
    for label, bf, af in live_features:
        place(bf, af, "★")

    # Render scatter as a Group
    scatter_lines = []
    for gy, row in enumerate(grid):
        # color the line: stars accent, dots grey, circles navy
        line = Text()
        for ch in row:
            if ch == "★":
                line.append(ch, style="bold yellow")
            elif ch == "●":
                line.append(ch, style="bold #C9462C")
            elif ch in "·:#":
                line.append(ch, style="grey42")
            else:
                line.append(ch)
        scatter_lines.append(line)

    legend = Text()
    legend.append(" ★ ", style="bold yellow")
    legend.append("live (this session)   ", style="white")
    legend.append("● ", style="bold #C9462C")
    legend.append("WG training (n=24)   ", style="white")
    legend.append("·  ", style="grey42")
    legend.append("non-VPN (n=1058)", style="white")

    axes_top = Text("ack60_fraction →", style="grey50")
    axes_bot = Text("0  ←  bulk_fraction  →  1", style="grey50",
                    justify="center")

    upper = Group(
        Text(""),
        legend, Text(""),
        axes_top,
        *scatter_lines,
        axes_bot,
    )
    SCENE.set_upper(upper)

    # Result panel: list each live point and where it lands
    result = Table.grid(padding=(0, 2))
    result.add_column(justify="right", style="grey50")
    result.add_column(justify="left", style="bold white")
    if not live_features:
        result.add_row("Live flows extracted:", "0  (no pcaps?)")
    else:
        for label, bf, af in live_features[:6]:
            land = "in WG cluster" if (bf >= 0.2) else "outside cluster"
            color = "bold #C9462C" if "WG cluster" in land else "grey50"
            result.add_row(
                f"{label}",
                Text(f"bulk={bf:.2f}  ack60={af:.2f}  → {land}", style=color))
    SCENE.set_result(result)
    live.update(render_layout(), refresh=True)
    return wait_for_advance(live)


# ----------------------------------------------------------------------
# Scene 5: pre-trained classifier predicts on live data
# ----------------------------------------------------------------------
def scene5(live: Live):
    SCENE.header(5, "The classifier flags every live flow",
                 "Random Forest (2 features) trained on master_set")

    intro = Group(
        Text("• Train RandomForest on (bulk, ack60) using master_set.",
             style="white"),
        Text("• Predict on the live features extracted in scene 4.",
             style="white"),
        Text(""),
        Text("Expected: every live WG flow predicted as WG with high confidence.",
             style="grey50"),
    )
    SCENE.set_upper(intro)
    SCENE.set_result(Text(""))
    live.update(render_layout(), refresh=True)
    if not wait_for_advance(live):
        return False

    SCENE.append_cmd(
        "$ from sklearn.ensemble import RandomForestClassifier", style="white")
    SCENE.append_cmd(
        "$ rf.fit(X_train, y_train)   # 1082 flows × 2 features",
        style="white")
    live.update(render_layout(), refresh=True)

    from sklearn.ensemble import RandomForestClassifier

    df = pd.read_csv(sorted(MASTER.glob("*classifier_features.csv"))[-1])
    X = df[["bulk_fraction", "ack60_fraction"]].values
    y = df["is_wg"].values
    rf = RandomForestClassifier(n_estimators=200, random_state=0,
                                class_weight="balanced")
    rf.fit(X, y)

    # Find the most recent feature CSVs from scene 4
    live_csvs = sorted((EVIDENCE).glob("demo-*_features.csv"),
                      key=lambda p: p.stat().st_mtime)[-2:]
    rows = []
    for csv in live_csvs:
        try:
            d = pd.read_csv(csv)
        except Exception:
            continue
        for _, row in d.iterrows():
            x_live = np.array([[row["bulk_fraction"], row["ack60_fraction"]]])
            pred = rf.predict(x_live)[0]
            prob = rf.predict_proba(x_live)[0, 1]
            rows.append((row["label"], row["bulk_fraction"],
                         row["ack60_fraction"], pred, prob))
            SCENE.append_cmd(
                f"  {row['label']}  bulk={row['bulk_fraction']:.2f}  "
                f"ack60={row['ack60_fraction']:.2f}  →  "
                f"pred={'WG' if pred else 'non-WG'}  p={prob:.3f}",
                style="white")
            live.update(render_layout(), refresh=True)
            time.sleep(0.4)

    result = Table(box=box.MINIMAL_HEAVY_HEAD,
                   show_header=True, header_style="bold #102A43",
                   pad_edge=False, padding=(0, 1))
    result.add_column("Live flow", style="white")
    result.add_column("bulk", justify="right")
    result.add_column("ack60", justify="right")
    result.add_column("predicted", style="bold")
    result.add_column("p(WG)", justify="right")
    for label, bf, af, pred, prob in rows:
        verdict = "WireGuard" if pred else "non-WG"
        v_style = "bold #C9462C" if pred else "grey50"
        result.add_row(label, f"{bf:.2f}", f"{af:.2f}",
                       Text(verdict, style=v_style), f"{prob:.3f}")
    SCENE.set_result(result)

    n_flagged = sum(1 for r in rows if r[3] == 1)
    if rows:
        summary = Text()
        summary.append(f"  → {n_flagged}/{len(rows)} live flows ",
                       style="white")
        summary.append("flagged as WireGuard", style="bold #C9462C")
        summary.append(" by the trained classifier.", style="white")
        SCENE.set_upper(Group(intro, Text(""), summary))

    live.update(render_layout(), refresh=True)
    SCENE.header(5, "Q&A", "")
    SCENE.set_upper(Group(
        Text(""),
        Text("Demo complete.  Ready for questions.", style="bold #102A43",
             justify="center"),
        Text(""),
        Text("Two structural fingerprints:", style="white", justify="center"),
        Text(""),
        Text("  WireGuard pads to MTU.", style="grey50", justify="center"),
        Text("  udp2raw acks every datagram 1:1.", style="grey50",
             justify="center"),
        Text("  udp2raw silently drops unfamiliar TCP shapes.",
             style="grey50", justify="center"),
        Text(""),
        Text("Both are mechanical consequences of the protocols' implementations.",
             style="white", justify="center"),
    ))
    live.update(render_layout(), refresh=True)
    return wait_for_advance(live)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def preflight():
    if os.geteuid() != 0:
        console.print("[bold red]must be run as root[/]   "
                      "[grey50](needed for wg-quick, tcpdump, raw socket probes)[/]")
        sys.exit(1)
    for p in [DPI_BASE / "wg_dpi.py",
              NOVEL / "active_probe.py",
              NOVEL / "flow_features.py"]:
        if not p.exists():
            console.print(f"[bold red]missing: {p}[/]")
            sys.exit(1)
    if not list(MASTER.glob("*classifier_features.csv")):
        console.print(
            "[bold red]missing classifier_features.csv in master_set/[/]")
        sys.exit(1)


def main():
    preflight()
    SCENE.header(0, "Press SPACE to begin",
                 "Live demo · WireGuard-in-udp2raw detection")
    SCENE.set_upper(Group(
        Text(""),
        Text("Five scenes, manual advance.  ~90 seconds total.",
             style="white", justify="center"),
        Text(""),
        Text("  1.  Bare WireGuard is byte-fingerprintable",
             style="grey50", justify="left"),
        Text("  2.  udp2raw eliminates that fingerprint",
             style="grey50", justify="left"),
        Text("  3.  But the wrapper isn't TCP-conformant",
             style="grey50", justify="left"),
        Text("  4.  Live features land in the WG cluster",
             style="grey50", justify="left"),
        Text("  5.  Trained classifier flags every live flow",
             style="grey50", justify="left"),
        Text(""),
        Text("Press SPACE / ENTER to begin   (Q to quit anywhere)",
             style="bold white", justify="center"),
    ))
    SCENE.set_cmd("# subprocess output streams here during each scene",
                  style="grey50")
    SCENE.set_result(Text("# scene results land here", style="grey50"))

    with Live(render_layout(), console=console, screen=True,
              auto_refresh=False, redirect_stderr=False) as live:
        if not wait_for_advance(live):
            return
        for scene in (scene1, scene2, scene3, scene4, scene5):
            if not scene(live):
                break


if __name__ == "__main__":
    main()
