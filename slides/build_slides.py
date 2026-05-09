"""Build the CYB623 presentation deck from the master_set artifacts.

Plain academic style. Title page, problem framing, two-stage methodology,
two contributions with their headline numbers, related work, conclusion.
Speaker notes on every slide.

Run:
    pip install python-pptx --break-system-packages
    python3 build_slides.py
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MASTER = os.path.join(ROOT, "master_set")
OUT = os.path.join(HERE, "WireGuard-udp2raw-detection.pptx")


# Plot files  pulled from the canonical run
CONFUSION_2F = os.path.join(MASTER, "20260509-132138_classifier_confusion.png")
ROC_2F       = os.path.join(MASTER, "20260509-132138_classifier_roc.png")
IMPORT_8F    = os.path.join(MASTER, "20260509-132129_classifier_feature_importance.png")


# Style ---------------------------------------------------------------
NAVY    = RGBColor(0x10, 0x2A, 0x43)
ACCENT  = RGBColor(0xC9, 0x46, 0x2C)
GREY    = RGBColor(0x55, 0x55, 0x55)
LIGHT   = RGBColor(0xF2, 0xF2, 0xF2)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
BLACK   = RGBColor(0x10, 0x10, 0x10)


def _para(p, text, *, size=18, bold=False, color=BLACK, align=None,
          space_after=4, font="Calibri"):
    p.text = ""
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    if align is not None:
        p.alignment = align
    p.space_after = Pt(space_after)
    return run


def _add_text(slide, left, top, width, height, text, *, size=18, bold=False,
              color=BLACK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font="Calibri"):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Pt(0); tf.margin_right = Pt(0)
    tf.margin_top  = Pt(0); tf.margin_bottom = Pt(0)
    if isinstance(text, str):
        _para(tf.paragraphs[0], text, size=size, bold=bold, color=color, align=align, font=font)
    else:
        # list of (text, kwargs) tuples
        first = True
        for entry in text:
            if isinstance(entry, str):
                t, kw = entry, {}
            else:
                t, kw = entry
            kw = {"size": size, "bold": bold, "color": color, "align": align, "font": font, **kw}
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            _para(p, t, **kw)
            first = False
    return box


def _bullet_list(slide, left, top, width, height, items, *, size=18,
                 color=BLACK, line_spacing=1.15, font="Calibri"):
    """items: list of strings or (level, string) tuples."""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(0); tf.margin_right = Pt(0)
    tf.margin_top  = Pt(0); tf.margin_bottom = Pt(0)
    first = True
    for it in items:
        if isinstance(it, tuple):
            level, txt = it
        else:
            level, txt = 0, it
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        bullet = "• " if level == 0 else "    – "
        _para(p, bullet + txt, size=size, color=color, font=font,
              align=PP_ALIGN.LEFT, space_after=4)
        p.line_spacing = line_spacing
    return box


def _accent_bar(slide, left, top, width, color=ACCENT):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, Pt(2.5))
    bar.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    return bar


def _title_block(slide, title, subtitle=None):
    _add_text(slide, Inches(0.6), Inches(0.35), Inches(11.5), Inches(0.7),
              title, size=32, bold=True, color=NAVY)
    _accent_bar(slide, Inches(0.6), Inches(1.05), Inches(1.0))
    if subtitle:
        _add_text(slide, Inches(0.6), Inches(1.15), Inches(11.5), Inches(0.5),
                  subtitle, size=16, color=GREY)


def _footer(slide, page_no, total):
    _add_text(slide, Inches(0.6), Inches(7.05), Inches(8), Inches(0.3),
              "Schiavone & Johannsen, CYB623, Pace University",
              size=10, color=GREY, align=PP_ALIGN.LEFT)
    _add_text(slide, Inches(11.5), Inches(7.05), Inches(1.3), Inches(0.3),
              f"{page_no} / {total}", size=10, color=GREY, align=PP_ALIGN.RIGHT)


def _notes(slide, text):
    notes = slide.notes_slide.notes_text_frame
    notes.text = text


# ---------------------------------------------------------------------
def build():
    prs = Presentation()
    prs.slide_width = Inches(13.333)   # widescreen 16:9
    prs.slide_height = Inches(7.5)

    blank = prs.slide_layouts[6]

    # We'll fill total page count after building
    slides = []

    # ============= 1. TITLE =============
    s = prs.slides.add_slide(blank)
    slides.append(s)

    _add_text(s, Inches(0.6), Inches(2.2), Inches(12.1), Inches(1.0),
              "Two-Feature Detection of",
              size=44, bold=True, color=NAVY)
    _add_text(s, Inches(0.6), Inches(2.95), Inches(12.1), Inches(1.0),
              "WireGuard-in-udp2raw",
              size=44, bold=True, color=NAVY)
    _accent_bar(s, Inches(0.6), Inches(3.85), Inches(2.5))
    _add_text(s, Inches(0.6), Inches(4.05), Inches(12.1), Inches(0.5),
              "A Probe-and-Classify Methodology",
              size=22, color=GREY)
    _add_text(s, Inches(0.6), Inches(5.6), Inches(12.1), Inches(0.4),
              "Steven Schiavone   ·   Nicholas Johannsen",
              size=18, color=BLACK)
    _add_text(s, Inches(0.6), Inches(6.0), Inches(12.1), Inches(0.4),
              "Seidenberg School of CSIS · Pace University · CYB623, May 2026",
              size=14, color=GREY)
    _notes(s, """Hi, I'm Steven, and with me is Nicholas. We spent the semester building
and breaking a small WireGuard deployment.

The headline: WireGuard's wire format is so regular that a 25-line script
detects it. The community fix is an obfuscation tool called udp2raw, which
has roughly 8500 GitHub stars and is documented to be actively blocked by
the Great Firewall and Iran's DPI. Despite that, no peer-reviewed paper
has ever analyzed it.

We did, and the result is in two parts: an active prober that finds udp2raw
in 8 seconds, and a passive two-feature classifier that hits 99.9 percent
accuracy on real-world background traffic.""")

    # ============= 2. PROBLEM =============
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s, "WireGuard is encrypted, but not unobservable",
                 "Strong cryptography ≠ traffic that hides itself")

    _add_text(s, Inches(0.6), Inches(1.7), Inches(12.1), Inches(0.4),
              "Every WireGuard message starts with this 4-byte header:",
              size=18, color=BLACK)

    code = ("+---------+-------------------+\n"
            "| type(1) | reserved zero (3) | … rest of message\n"
            "+---------+-------------------+")
    _add_text(s, Inches(0.6), Inches(2.2), Inches(8.5), Inches(1.4),
              code, size=18, font="Consolas", color=NAVY)

    _bullet_list(s, Inches(0.6), Inches(3.7), Inches(12.1), Inches(2.5), [
        "type byte ∈ {0x01, 0x02, 0x03, 0x04}; next three bytes are zero.",
        "Handshake messages are exactly 148 / 92 / 64 bytes.",
        "Three concatenated checks identify a WireGuard handshake with negligible false-positive risk.",
        "A 25-line Python predicate gives you the full detector. We re-derived it as our baseline.",
        "Used in production by the Great Firewall (Wu et al., USENIX Security '23).",
    ], size=20)

    _add_text(s, Inches(0.6), Inches(6.55), Inches(12.1), Inches(0.5),
              "Donenfeld's whitepaper says obfuscation is out of scope. The community wraps WireGuard in udp2raw.",
              size=16, color=ACCENT, bold=True)

    _footer(s, 2, 0)
    _notes(s, """Two important things on this slide.

First, the wire format is *trivial*. One type byte, three zero bytes,
fixed lengths for the handshake. Anyone watching UDP can fingerprint it
without decrypting anything.

Second - and this is not a vulnerability - Donenfeld's whitepaper
explicitly says obfuscation is out of scope for WireGuard. The community
response has been to wrap WireGuard in something else, most prominently
the tool called udp2raw.

So the question of this paper isn't 'can you detect WireGuard?' That's
been done. It's 'can you detect WireGuard once it's hidden inside udp2raw?'""")

    # ============= 3. udp2raw + GAP =============
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s, "udp2raw is the most-deployed shim - and academically unstudied",
                 "Wraps WireGuard's UDP datagrams as TCP-shaped packets in userspace")

    _add_text(s, Inches(0.6), Inches(1.7), Inches(12.1), Inches(0.4),
              "End-to-end paths under test (same WG keys, same inner IPs, only transport differs):",
              size=16, color=GREY)

    # Two boxes side by side
    # Direct path
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(0.6), Inches(2.2), Inches(5.9), Inches(1.4))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = NAVY
    box.text_frame.margin_left = Pt(8); box.text_frame.margin_top = Pt(6)
    p = box.text_frame.paragraphs[0]
    _para(p, "Direct (passive-detectable)", size=15, bold=True, color=NAVY, space_after=2)
    p = box.text_frame.add_paragraph()
    _para(p, "Kali wg client  ──UDP/51820──▶  OCI wg server",
          size=14, color=BLACK, font="Consolas", space_after=2)

    # Obfuscated path
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(6.85), Inches(2.2), Inches(6.0), Inches(1.4))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = ACCENT
    box.text_frame.margin_left = Pt(8); box.text_frame.margin_top = Pt(6)
    p = box.text_frame.paragraphs[0]
    _para(p, "Obfuscated (this paper's target)", size=15, bold=True, color=ACCENT, space_after=2)
    p = box.text_frame.add_paragraph()
    _para(p, "wg ─lo─▶ udp2raw ─TCP/4096 (faketcp)─▶ udp2raw ─lo─▶ wg",
          size=12, color=BLACK, font="Consolas", space_after=2)

    _add_text(s, Inches(0.6), Inches(3.95), Inches(12.1), Inches(0.4),
              "Why udp2raw, specifically:",
              size=18, bold=True, color=NAVY)

    _bullet_list(s, Inches(0.6), Inches(4.4), Inches(12.1), Inches(2.5), [
        "≈8.5k GitHub stars; standard recommendation alongside WireGuard in censored regions.",
        "Documented to be actively blocked by the Great Firewall and Iran's DPI (gray-literature reports).",
        "Cited once by the WireGuard project's own “Known Limitations” page.",
        "But: zero peer-reviewed analysis. We searched USENIX, NDSS, IMC, FOCI, PETS, CCS - nothing.",
    ], size=18)

    _footer(s, 3, 0)
    _notes(s, """Quick orientation. Top of the slide: two paths through our lab. Same
WireGuard keys both ways - only the transport changes. The direct path
is what censors block. The obfuscated path wraps each WireGuard packet
inside what looks like a long-running TCP connection on port 4096.

The bullets at the bottom are the gap we identified. udp2raw is a tool
that protects roughly eight and a half thousand stars worth of users.
It's documented to be blocked. And it's never been formally analyzed.

Other obfuscators - AmneziaWG, swgp-go, wstunnel - exist, but udp2raw is
the dominant one and the one nobody has studied. So we focused there.""")

    # ============= 4. METHODOLOGY =============
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s, "Two attacks, one lab",
                 "Following Xue et al.'s active-probe-and-passive-classify pattern from USENIX Security '22")

    # Two columns
    # C1
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(0.6), Inches(1.65), Inches(6.05), Inches(5.0))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = NAVY
    tf = box.text_frame
    tf.margin_left = Pt(14); tf.margin_top = Pt(12); tf.margin_right = Pt(14)
    _para(tf.paragraphs[0], "C1 - Active prober", size=22, bold=True, color=NAVY, space_after=8)
    for line in [
        "Send 5 stateless TCP probes to (IP, port).",
        "Real Linux TCP answers all 5.",
        "udp2raw answers SYN, drops 3 of 4 follow-ups.",
        "Verdict in ≤ 9 seconds, deterministic on 5/5 trials.",
    ]:
        p = tf.add_paragraph()
        _para(p, "•  " + line, size=16, color=BLACK, space_after=4)
    p = tf.add_paragraph()
    p.space_before = Pt(10)
    _para(p, "Cost to adversary: ~1.7 KB and 9 seconds per host.",
          size=14, color=GREY, space_after=2)

    # C2
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(6.85), Inches(1.65), Inches(6.0), Inches(5.0))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = ACCENT
    tf = box.text_frame
    tf.margin_left = Pt(14); tf.margin_top = Pt(12); tf.margin_right = Pt(14)
    _para(tf.paragraphs[0], "C2 - Two-feature passive classifier", size=22, bold=True, color=ACCENT, space_after=8)
    for line in [
        "bulk_fraction:   fraction of MTU-class packets.",
        "ack60_fraction:  fraction of 60-byte TCP ACKs.",
        "Both are mechanical consequences of how the protocols are written, not statistical regularities.",
        "Random Forest: 99.9 % accuracy, AUC = 1.000.",
    ]:
        p = tf.add_paragraph()
        _para(p, "•  " + line, size=16, color=BLACK, space_after=4)
    p = tf.add_paragraph()
    p.space_before = Pt(10)
    _para(p, "Trained on 24 WG flows + 1058 ISCXVPN2016 non-VPN flows.",
          size=14, color=GREY, space_after=2)

    _footer(s, 4, 0)
    _notes(s, """The methodology is borrowed shamelessly from Xue et al.'s 2022 paper that
won Distinguished Paper at USENIX. They built passive-then-active detectors
for OpenVPN. We do the same pattern, but for WireGuard-in-udp2raw, which
they didn't cover.

Left side: contribution one is an active prober. Five stateless TCP packets,
nine seconds, deterministic. I'll show the actual probe outputs in two
slides.

Right side: contribution two is a passive classifier with two features.
Both features fall out of how the protocols work - WireGuard pads to MTU,
udp2raw acks every datagram one-to-one - so they're not statistical luck,
they're structural.

Trained on 24 WireGuard flows we captured ourselves, against 1058 non-VPN
flows from ISCXVPN2016, the canonical dataset for this task.""")

    # ============= 5. C1 RESULTS =============
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s, "C1 - One probe distinguishes udp2raw from real TCP",
                 "Three targets on the same OCI host; deterministic verdict in 5/5 repeated trials")

    # Build a table-like layout manually (cleaner than pptx default tables)
    headers = ["Probe", "TCP/22 (real SSH)", "TCP/4096 (udp2raw)", "TCP/9999 (closed)"]
    rows = [
        ["P1  SYN",                "SYN-ACK 181 ms",    "SYN-ACK 163 ms",    "no response"],
        ["P2  SYN + payload",      "SYN-ACK + 2 B",     "silent",            "no response"],
        ["P3  bogus ACK",          "RST 81 ms",         "RST 91 ms",         "no RST"],
        ["P4  WS=14 SYN",          "SYN-ACK",           "silent",            "no response"],
        ["P5  FIN to unopened",    "RST",               "silent",            "no response"],
    ]

    top = Inches(1.6)
    col_lefts = [Inches(0.6), Inches(3.5), Inches(6.7), Inches(10.0)]
    col_widths = [Inches(2.85), Inches(3.15), Inches(3.25), Inches(2.85)]
    row_h = Inches(0.45)

    # header
    for i, h in enumerate(headers):
        _add_text(s, col_lefts[i], top, col_widths[i], row_h,
                  h, size=14, bold=True, color=NAVY)
    _accent_bar(s, Inches(0.6), top + Inches(0.45), Inches(12.1), color=NAVY)

    # rows
    for r, row in enumerate(rows):
        y = top + Inches(0.55) + r * Inches(0.42)
        for i, val in enumerate(row):
            color = BLACK
            if "silent" in val:
                color = ACCENT
            _add_text(s, col_lefts[i], y, col_widths[i], row_h,
                      val, size=14, color=color,
                      font="Consolas" if i > 0 else "Calibri")

    # Summary band
    y = top + Inches(0.55) + len(rows) * Inches(0.42) + Inches(0.15)
    _accent_bar(s, Inches(0.6), y, Inches(12.1), color=NAVY)
    summary_y = y + Inches(0.15)
    _add_text(s, col_lefts[0], summary_y, col_widths[0], Inches(0.4),
              "Total time", size=14, bold=True, color=NAVY)
    for i, val in enumerate(["0.5 s", "8.5 s", "15.5 s"]):
        _add_text(s, col_lefts[i+1], summary_y, col_widths[i+1], Inches(0.4),
                  val, size=14, bold=True, color=BLACK, font="Consolas")
    summary_y2 = summary_y + Inches(0.42)
    _add_text(s, col_lefts[0], summary_y2, col_widths[0], Inches(0.4),
              "Verdict", size=14, bold=True, color=NAVY)
    for i, val in enumerate(["REAL_TCP", "UDP2RAW_FAKETCP", "UNREACHABLE"]):
        c = ACCENT if "UDP2RAW" in val else BLACK
        _add_text(s, col_lefts[i+1], summary_y2, col_widths[i+1], Inches(0.4),
                  val, size=14, bold=True, color=c, font="Consolas")

    _add_text(s, Inches(0.6), Inches(6.55), Inches(12.1), Inches(0.5),
              "Discriminator: count silent responses among {P2, P4, P5}.  Real TCP answers all three.  udp2raw answers none.",
              size=16, color=GREY)

    _footer(s, 5, 0)
    _notes(s, """Read the table. Three columns, one for each thing we probed: real SSH,
udp2raw, and a closed port.

Look at the orange entries. udp2raw answers the SYN, because it has to -
that's its disguise. It also answers the bogus ACK because the kernel
underneath emits a RST when udp2raw doesn't claim the packet. So those
two probes don't discriminate.

The other three - SYN with payload, an unusual window-scale option, FIN
to a port with no connection - udp2raw drops every one. A real Linux
kernel always answers them. That's the signal.

Total time: real TCP is half a second. udp2raw is eight and a half
seconds. The closed port times out at fifteen.

We ran this five times against udp2raw and got the same verdict five
times. It's not statistical, it's structural - udp2raw's userspace state
machine simply doesn't recognize these packet shapes.""")

    # ============= 6. C2 - class means =============
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s, "C2 - Two features carry the entire signal",
                 "Class means across 24 WG flows and 1058 ISCXVPN2016 non-VPN flows")

    # Numeric comparison panel on the left
    headers = ["Feature", "WireGuard", "Non-VPN", "Ratio"]
    rows_top = [
        ["bulk_fraction",   "0.553 ± 0.186", "0.019 ± 0.066", "29×"],
        ["ack60_fraction",  "0.295 ± 0.187", "0.069 ± 0.169", "4.3×"],
    ]
    rows_other = [
        ["len_entropy",          "1.94 ± 0.82",   "1.23 ± 1.42",   "-"],
        ["dominant_size_frac.",  "0.50 ± 0.19",   "0.71 ± 0.30",   "(inv.)"],
        ["top3_size_fraction",   "0.88 ± 0.15",   "0.87 ± 0.19",   "-"],
        ["rate_pps",             "3.23 ± 0.90",   "3.37 ± 30.27",  "-"],
    ]

    top = Inches(1.6)
    col_lefts = [Inches(0.6), Inches(3.0), Inches(5.4), Inches(7.3)]
    col_widths = [Inches(2.4), Inches(2.4), Inches(2.0), Inches(0.8)]

    for i, h in enumerate(headers):
        _add_text(s, col_lefts[i], top, col_widths[i], Inches(0.4),
                  h, size=14, bold=True, color=NAVY)
    _accent_bar(s, Inches(0.6), top + Inches(0.4), Inches(7.5), color=NAVY)

    y = top + Inches(0.5)
    for row in rows_top:
        for i, val in enumerate(row):
            c = ACCENT if i == 3 else BLACK
            b = (i == 3)
            font = "Consolas" if i > 0 else "Calibri"
            _add_text(s, col_lefts[i], y, col_widths[i], Inches(0.38),
                      val, size=14, bold=b, color=c, font=font)
        y += Inches(0.42)

    # divider
    _accent_bar(s, Inches(0.6), y + Inches(0.05), Inches(7.5), color=GREY)
    y += Inches(0.18)

    for row in rows_other:
        for i, val in enumerate(row):
            c = GREY
            font = "Consolas" if i > 0 else "Calibri"
            _add_text(s, col_lefts[i], y, col_widths[i], Inches(0.38),
                      val, size=13, color=c, font=font)
        y += Inches(0.36)

    # Right side: importance plot
    if os.path.exists(IMPORT_8F):
        s.shapes.add_picture(IMPORT_8F, Inches(8.4), Inches(1.6),
                              height=Inches(4.1))
    _add_text(s, Inches(8.4), Inches(5.85), Inches(4.4), Inches(0.5),
              "Permutation importance (RF, 8-feature variant) confirms bulk_fraction is the dominant signal.",
              size=11, color=GREY, align=PP_ALIGN.LEFT)

    _add_text(s, Inches(0.6), Inches(6.5), Inches(7.7), Inches(0.7),
              ("Naive intuition would have picked dominant_size_fraction. "
               "Real-world background INVERTS that signal, because non-VPN traffic "
               "contains many degenerate idle flows."),
              size=13, color=ACCENT, align=PP_ALIGN.LEFT)

    _footer(s, 6, 0)
    _notes(s, """Two features do the work.

Bulk fraction - that's the share of packets in a flow that are MTU-sized.
For WireGuard it's 55 percent. For non-VPN background it's two percent.
That's a 29-fold separation. Why? Because WireGuard pads every packet to
the configured MTU. A web browser doesn't.

ACK60 fraction - that's the share of 60-byte TCP ACK packets. For
WireGuard-in-udp2raw it's 30 percent. Why? udp2raw frames every WireGuard
datagram as one TCP segment, and the receiver's kernel emits a 60-byte
ACK for each one. So the ACK ratio is essentially 1 to 1, where real TCP
uses delayed ACK and gets to about 1 to 2.

The greyed-out rows below are the features that DIDN'T separate. The
honest finding is that dominant_size_fraction - which I expected to be
the killer feature - is actually inverted. ISCXVPN2016 contains a lot of
idle TCP keepalives that have ALL packets at one size, more concentrated
than WireGuard. Real data inverted my intuition. We left those features
out of the headline classifier.

The plot on the right is the permutation importance from the 8-feature
Random Forest. bulk_fraction sits at the top by a wide margin.""")

    # ============= 7. C2 - classifier results =============
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s, "C2 - Random Forest hits 99.9 % with two features",
                 "5-fold stratified cross-validation; class-balanced.")

    # Big numbers on the left
    big_y = Inches(1.7)
    _add_text(s, Inches(0.6), big_y, Inches(5.5), Inches(0.4),
              "Two-feature Random Forest", size=18, bold=True, color=NAVY)

    metrics = [
        ("99.91 %",  "Accuracy"),
        ("1.000",    "Precision  (zero false positives in 1058)"),
        ("0.958",    "Recall  (23 of 24 WG flows caught)"),
        ("1.000",    "ROC AUC"),
    ]
    y = big_y + Inches(0.55)
    for big, label in metrics:
        _add_text(s, Inches(0.6), y, Inches(2.4), Inches(0.6),
                  big, size=30, bold=True, color=ACCENT, font="Consolas")
        _add_text(s, Inches(3.0), y + Inches(0.15), Inches(3.2), Inches(0.45),
                  label, size=14, color=BLACK)
        y += Inches(0.7)

    # Comparison table at bottom-left
    _accent_bar(s, Inches(0.6), Inches(5.5), Inches(6.0), color=NAVY)
    _add_text(s, Inches(0.6), Inches(5.6), Inches(6.0), Inches(0.4),
              "Adding more features hurts.", size=14, bold=True, color=NAVY)
    rows = [
        ["RF, 2 features", "0.999",  "1.000", "0.958"],
        ["RF, 8 features", "0.998",  "1.000", "0.917"],
        ["LR, 2 features", "0.969",  "0.414", "1.000"],
    ]
    headers = ["model", "acc", "prec", "rec"]
    col_lefts = [Inches(0.6), Inches(3.2), Inches(4.2), Inches(5.2)]
    col_widths = [Inches(2.6), Inches(1.0), Inches(1.0), Inches(1.0)]
    yy = Inches(6.05)
    for i, h in enumerate(headers):
        _add_text(s, col_lefts[i], yy, col_widths[i], Inches(0.3),
                  h, size=11, bold=True, color=GREY)
    yy += Inches(0.3)
    for r in rows:
        for i, v in enumerate(r):
            font = "Consolas" if i > 0 else "Calibri"
            _add_text(s, col_lefts[i], yy, col_widths[i], Inches(0.3),
                      v, size=12, color=BLACK, font=font)
        yy += Inches(0.32)

    # Confusion + ROC on right
    if os.path.exists(CONFUSION_2F):
        s.shapes.add_picture(CONFUSION_2F, Inches(7.6), Inches(1.55),
                              height=Inches(2.6))
    if os.path.exists(ROC_2F):
        s.shapes.add_picture(ROC_2F, Inches(7.6), Inches(4.3),
                              height=Inches(2.6))

    _footer(s, 7, 0)
    _notes(s, """The big numbers on the left are the headline. 99.91 percent accuracy.
Precision of 1.0 - zero false positives across 1058 background flows.
Recall of 0.958 - we caught 23 of 24 WireGuard flows. AUC is 1.0.

Below that is a small comparison. The 2-feature RF is the headline. The
8-feature RF - adding entropy, mode concentration, packet rate, etc. -
actually does WORSE. Recall drops from 0.958 to 0.917. The extra features
add noise. Logistic regression catches everything but pays for it with
about 3 percent false positives.

On the right: confusion matrix on top - 1058 background correctly
classified as background, 23 of 24 WG correctly classified as WG, exactly
one missed. ROC curve on the bottom hugs the top-left corner; AUC is 1.0.

The take-away: this isn't a fragile statistical artifact. Two features
that are mechanical consequences of the protocols' implementations give
us essentially perfect separation.""")

    # ============= 8. RELATED WORK + LIMITS =============
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s, "Where this sits in the literature",
                 "Narrow contribution alongside two recent Xue et al. papers")

    # Two columns
    _add_text(s, Inches(0.6), Inches(1.6), Inches(6.0), Inches(0.4),
              "Closely related",
              size=18, bold=True, color=NAVY)
    _bullet_list(s, Inches(0.6), Inches(2.1), Inches(6.0), Inches(4.5), [
        "Xue et al., USENIX Security ’22 - passive + active for OpenVPN. Method template.",
        "Xue et al., USENIX Security ’24 - encapsulated-TLS-handshake fingerprint. Doesn’t fire on WG (no nested TLS).",
        "Xue et al., NDSS ’25 - cross-layer RTT. Attenuated on UDP-only short flows.",
        "Wu et al., USENIX Security ’23 - GFW entropy detector. Adjacent.",
        "Alice et al., IMC ’20 - Shadowsocks active probes. Probe taxonomy.",
        "Frolov & Wustrow, NDSS ’20 - probe-resistant proxies.",
    ], size=15)

    _add_text(s, Inches(7.0), Inches(1.6), Inches(5.8), Inches(0.4),
              "Honest limitations",
              size=18, bold=True, color=ACCENT)
    _bullet_list(s, Inches(7.0), Inches(2.1), Inches(5.8), Inches(4.5), [
        "Single client/server pair - no ISP-scale measurement.",
        "udp2raw v20230206.0 only; later forks may behave differently.",
        "Static defenses: a delayed-ACK patch + WG MTU below the bulk threshold would weaken C2.",
        "C1’s P3 (bogus ACK) is mildly hostile - adversary should fire it only on already-suspected hosts.",
        "Not benchmarked against AmneziaWG / swgp-go / wstunnel - future work.",
    ], size=15)

    _footer(s, 8, 0)
    _notes(s, """Quick lit positioning so the audience knows we did our reading.

Xue's group at Michigan has the dominant line of work on this. Their 2022
paper on OpenVPN gave us our methodology template. Their 2024 paper does
encapsulated-TLS-handshake fingerprinting - that doesn't fire on WireGuard
because there's no nested TLS. Their 2025 NDSS paper does cross-layer
RTT - that signal attenuates on the short, UDP-only flows we have. So
their protocol-AGNOSTIC methods don't already solve the WireGuard-specific
case. Protocol-specific structural features remain the available approach.

On the right: the things we are NOT claiming. We don't have ISP-scale
deployment. We tested one version of udp2raw. A motivated maintainer
could patch it to defeat both attacks. We didn't extend to the other
shims. All of that is honest scope-limiting, not handwaving.""")

    # ============= 9. CONCLUSION =============
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s, "Takeaway",
                 None)

    msgs = [
        ("WireGuard's wire format leaks.", NAVY,
         "A 25-line classifier handles bare WG.  This is the existing problem the udp2raw shim is supposed to fix."),
        ("udp2raw doesn't fix it.", ACCENT,
         "Five TCP probes in 8.5 seconds (C1).  Two flow features, RF, AUC = 1.0 (C2)."),
        ("Both signals are structural.", NAVY,
         "udp2raw silently drops unfamiliar TCP shapes; WireGuard pads to MTU; udp2raw acks 1:1.  None of these are statistical luck."),
        ("Defenses are obvious but un-implemented in upstream.", ACCENT,
         "Delayed-ACK and a sub-bulk MTU close C2.  More-conformant TCP emulation closes C1.  Both are upstream patches we did not write."),
    ]

    y = Inches(1.7)
    for headline, color, body in msgs:
        _add_text(s, Inches(0.6), y, Inches(12.1), Inches(0.45),
                  headline, size=22, bold=True, color=color)
        _add_text(s, Inches(0.6), y + Inches(0.5), Inches(12.1), Inches(0.55),
                  body, size=14, color=BLACK)
        y += Inches(1.2)

    _add_text(s, Inches(0.6), Inches(6.55), Inches(12.1), Inches(0.5),
              "Code, configs, evidence, and the report are in master_set/ and the repo.",
              size=14, color=GREY)

    _footer(s, 9, 0)
    _notes(s, """The four take-aways.

One: WireGuard's format leaks. Known result. We re-derived it as our
baseline so we could honestly compare against it.

Two: udp2raw doesn't actually fix the leak. Eight and a half seconds with
a five-packet active prober, or two passive features at AUC 1.0 - pick
your weapon.

Three: this isn't a statistical fluke. Both detectors are grounded in
how the protocols are implemented. WireGuard pads to MTU because it does.
udp2raw acks one-to-one because it has to. udp2raw silently drops weird
TCP shapes because its parser was written with one shape in mind.

Four - and this is the constructive note for the upstream maintainers -
the defenses are obvious. Delayed ACK and a smaller WG MTU kill C2. More
conformant TCP emulation kills C1. We sketch both in the paper but didn't
patch the upstream tool. That's somebody else's pull request to write.

Happy to take questions.""")

    # ============= 10. APPENDIX (optional) - Q&A safety net =============
    # Skipping for brevity; we have a tight 9-slide deck.

    # Patch all footers to reflect total
    total = len(slides)
    for i, _s in enumerate(slides, 1):
        # remove and re-add footer with corrected total
        for sh in list(_s.shapes):
            if sh.has_text_frame:
                txt = sh.text_frame.text
                if " / 0" in txt:
                    sp = sh._element
                    sp.getparent().remove(sp)
        _footer(_s, i, total)

    prs.save(OUT)
    print(f"wrote {OUT}  ({total} slides)")


if __name__ == "__main__":
    build()
