"""Build the CYB623 presentation deck from master_set artifacts.

Plain academic style, 16:9 widescreen. Strict layout discipline:
  * Title strip:   y = 0.30 to 1.10
  * Subtitle:      y = 1.15 to 1.50
  * Body region:   y = 1.65 to 6.65
  * Footer strip:  y = 6.85 to 7.20  (no body content past y = 6.70)

Run:
    python -m pip install python-pptx pillow
    python build_slides.py
"""
import os
from datetime import datetime, timezone
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MASTER = os.path.join(ROOT, "master_set")
LATEX = os.path.join(ROOT, "latex-paper")
OUT = os.path.join(HERE, "WireGuard-udp2raw-detection.pptx")

CONFUSION_2F = os.path.join(MASTER, "20260509-132138_classifier_confusion.png")
ROC_2F       = os.path.join(MASTER, "20260509-132138_classifier_roc.png")
IMPORT_8F    = os.path.join(MASTER, "20260509-132129_classifier_feature_importance.png")
SCATTER      = os.path.join(LATEX,  "scatter.png")

# ---------- palette ----------
NAVY   = RGBColor(0x10, 0x2A, 0x43)
ACCENT = RGBColor(0xC9, 0x46, 0x2C)
GREY   = RGBColor(0x55, 0x55, 0x55)
LIGHT  = RGBColor(0xF2, 0xF2, 0xF2)
BLACK  = RGBColor(0x10, 0x10, 0x10)

# ---------- layout constants (inches, 13.333 x 7.5 widescreen) ----------
SLIDE_W  = 13.333
SLIDE_H  = 7.5
LMARGIN  = 0.55
RMARGIN  = 0.55
WIDTH    = SLIDE_W - LMARGIN - RMARGIN
TITLE_TOP    = 0.30
TITLE_H      = 0.80
ACCENT_Y     = 1.10
SUBTITLE_TOP = 1.18
SUBTITLE_H   = 0.40
BODY_TOP     = 1.70
BODY_BOTTOM  = 6.55     # NOTHING past this Y in body content
FOOTER_TOP   = 6.85
FOOTER_H     = 0.30


# ---------- text primitives ----------
def _para(p, text, *, size=18, bold=False, color=BLACK, align=PP_ALIGN.LEFT,
          space_after=4, line_spacing=None, font="Calibri"):
    p.text = ""
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    p.alignment = align
    p.space_after = Pt(space_after)
    if line_spacing is not None:
        p.line_spacing = line_spacing
    return run


def _add_text(slide, left, top, width, height, text, *, size=18, bold=False,
              color=BLACK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
              font="Calibri"):
    box = slide.shapes.add_textbox(Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Pt(0); tf.margin_right = Pt(0)
    tf.margin_top = Pt(0); tf.margin_bottom = Pt(0)
    _para(tf.paragraphs[0], text, size=size, bold=bold, color=color,
          align=align, font=font)
    return box


def _bullet_list(slide, left, top, width, height, items, *, size=16,
                 color=BLACK, line_spacing=1.18, space_after=6, font="Calibri"):
    """items: list of strings or (level, string) tuples (level 0 = top)."""
    box = slide.shapes.add_textbox(Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(0); tf.margin_right = Pt(0)
    tf.margin_top = Pt(0); tf.margin_bottom = Pt(0)
    first = True
    for it in items:
        if isinstance(it, tuple):
            level, txt = it
        else:
            level, txt = 0, it
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        bullet = "•   " if level == 0 else "       –   "
        _para(p, bullet + txt, size=size, color=color, font=font,
              align=PP_ALIGN.LEFT, space_after=space_after,
              line_spacing=line_spacing)
    return box


def _accent_bar(slide, left, top, width, color=ACCENT, height_pt=2.5):
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(left), Inches(top), Inches(width), Pt(height_pt))
    bar.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    return bar


def _title_block(slide, title, subtitle=None, *, title_size=28):
    _add_text(slide, LMARGIN, TITLE_TOP, WIDTH, TITLE_H,
              title, size=title_size, bold=True, color=NAVY,
              anchor=MSO_ANCHOR.TOP)
    _accent_bar(slide, LMARGIN, ACCENT_Y, 1.0)
    if subtitle:
        _add_text(slide, LMARGIN, SUBTITLE_TOP, WIDTH, SUBTITLE_H,
                  subtitle, size=14, color=GREY)


def _footer(slide, page_no, total):
    _add_text(slide, LMARGIN, FOOTER_TOP, 9.0, FOOTER_H,
              "Schiavone & Johannsen   ·   CYB623   ·   Pace University",
              size=10, color=GREY, align=PP_ALIGN.LEFT)
    _add_text(slide, SLIDE_W - 2.0, FOOTER_TOP, 1.5, FOOTER_H,
              f"{page_no} / {total}",
              size=10, color=GREY, align=PP_ALIGN.RIGHT)


def _notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def _add_picture_fit(slide, path, left, top, max_w, max_h):
    """Add a picture, scaling to fit within (max_w x max_h) inches without
    cropping. Returns (left, top, width, height) actually used (inches)."""
    with Image.open(path) as img:
        iw, ih = img.size
    img_aspect = iw / ih
    box_aspect = max_w / max_h
    if img_aspect >= box_aspect:
        w = max_w
        h = max_w / img_aspect
    else:
        h = max_h
        w = max_h * img_aspect
    used_left = left + (max_w - w) / 2
    used_top  = top  + (max_h - h) / 2
    slide.shapes.add_picture(path,
                             Inches(used_left), Inches(used_top),
                             Inches(w), Inches(h))
    return used_left, used_top, w, h


# ---------- slide builders ----------
def build():
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    blank = prs.slide_layouts[6]
    slides = []

    # ============================================================
    # Slide 1 — Title
    # ============================================================
    s = prs.slides.add_slide(blank)
    slides.append(s)

    _add_text(s, LMARGIN, 2.20, WIDTH, 1.10,
              "Two-Feature Detection of",
              size=42, bold=True, color=NAVY)
    _add_text(s, LMARGIN, 3.00, WIDTH, 1.10,
              "WireGuard-in-udp2raw",
              size=42, bold=True, color=NAVY)
    _accent_bar(s, LMARGIN, 4.05, 2.5)
    _add_text(s, LMARGIN, 4.20, WIDTH, 0.50,
              "A Probe-and-Classify Methodology",
              size=20, color=GREY)
    _add_text(s, LMARGIN, 5.70, WIDTH, 0.40,
              "Steven Schiavone   ·   Nicholas Johannsen",
              size=18, color=BLACK)
    _add_text(s, LMARGIN, 6.10, WIDTH, 0.35,
              "Seidenberg School of CSIS · Pace University · CYB623, May 2026",
              size=12, color=GREY)
    _notes(s, """Setup
  • WireGuard = modern VPN. Encrypts well, but doesn't try to hide that it IS a VPN.
  • Hiding the VPN is explicitly out of scope per Donenfeld's 2017 paper.
  • Question: does the most popular hiding tool actually hide it?

The tool: udp2raw
  • Used in Iran and China for censorship circumvention.
  • Zero peer-reviewed analysis before this paper.

Two results we'll show
  • Active attack: 5 test packets, identifies udp2raw server in 8.5 s.
  • Passive attack: 2 traffic features, classifier at 99.9% accuracy.""")

    # ============================================================
    # Slide 2 — Problem
    # ============================================================
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s,
                 "WireGuard is encrypted, but not unobservable",
                 "Strong cryptography is not the same as traffic that hides itself")

    _add_text(s, LMARGIN, BODY_TOP, WIDTH, 0.40,
              "Every WireGuard message starts with this 4-byte header:",
              size=16, color=BLACK)

    code = ("+---------+-------------------+\n"
            "| type(1) | reserved zero (3) | …rest of message\n"
            "+---------+-------------------+")
    _add_text(s, LMARGIN, 2.20, 8.5, 1.30,
              code, size=16, font="Consolas", color=NAVY)

    _bullet_list(s, LMARGIN, 3.65, WIDTH, 2.50, [
        "type byte ∈ {0x01, 0x02, 0x03, 0x04}; the next three bytes are zero.",
        "Handshake messages are exactly 148 / 92 / 64 bytes.",
        "Three concatenated checks identify a WireGuard handshake with negligible false-positive risk.",
        "A 25-line Python predicate is the full detector. We re-implement it as our baseline.",
        "Reported in production by the Great Firewall (Wu et al., USENIX Security ’23).",
    ], size=17)

    _add_text(s, LMARGIN, 5.95, WIDTH, 0.50,
              "Donenfeld’s WireGuard whitepaper (NDSS ’17) explicitly leaves obfuscation out of scope.",
              size=14, color=ACCENT, bold=True)

    _footer(s, 2, 0)
    _notes(s, """Why WireGuard is easy to spot
  • First byte = message type, always 1, 2, 3, or 4.
  • Next 3 bytes = always zero.
  • Handshake packets = fixed sizes: 148, 92, 64 bytes.
  • → Identify WireGuard from first 4 bytes + packet length. No decryption needed.
  • 25-line Python detector is the whole thing.
  • Wu et al., USENIX Security 2023: Great Firewall does exactly this.

Important caveat — not a vulnerability
  • Donenfeld's 2017 paper says hiding the VPN's existence is out of scope.
  • That's a job for a separate tool on top.
  • Real question: can you detect WireGuard once it's wrapped in the popular hiding tool?
  • → That tool is udp2raw. Next slide.""")

    # ============================================================
    # Slide 3 — udp2raw and the literature gap
    # ============================================================
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s,
                 "udp2raw: the obfuscation shim, and the literature gap",
                 "Wraps WireGuard's UDP datagrams as TCP-shaped packets in userspace")

    _add_text(s, LMARGIN, BODY_TOP, WIDTH, 0.40,
              "End-to-end paths under test (same WG keys, same inner IPs; only the transport differs):",
              size=14, color=GREY)

    box_w = (WIDTH - 0.4) / 2
    # Direct path card
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(LMARGIN), Inches(2.20),
                             Inches(box_w), Inches(1.40))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = NAVY
    tf = box.text_frame
    tf.margin_left = Pt(10); tf.margin_top = Pt(8); tf.margin_right = Pt(10)
    tf.word_wrap = True
    _para(tf.paragraphs[0], "Direct (passive-detectable)",
          size=15, bold=True, color=NAVY, align=PP_ALIGN.CENTER, space_after=6)
    p = tf.add_paragraph()
    _para(p, "Kali wg client", size=14, color=BLACK, font="Consolas",
          align=PP_ALIGN.CENTER, space_after=2)
    p = tf.add_paragraph()
    _para(p, "↓  UDP / 51820", size=14, color=ACCENT, font="Consolas",
          align=PP_ALIGN.CENTER, space_after=2)
    p = tf.add_paragraph()
    _para(p, "OCI wg server", size=14, color=BLACK, font="Consolas",
          align=PP_ALIGN.CENTER, space_after=2)

    # Obfuscated path card
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(LMARGIN + box_w + 0.4), Inches(2.20),
                             Inches(box_w), Inches(1.40))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = ACCENT
    tf = box.text_frame
    tf.margin_left = Pt(10); tf.margin_top = Pt(8); tf.margin_right = Pt(10)
    tf.word_wrap = True
    _para(tf.paragraphs[0], "Obfuscated (this paper's target)",
          size=15, bold=True, color=ACCENT, align=PP_ALIGN.CENTER, space_after=6)
    p = tf.add_paragraph()
    _para(p, "wg client  →  udp2raw client", size=13, color=BLACK,
          font="Consolas", align=PP_ALIGN.CENTER, space_after=2)
    p = tf.add_paragraph()
    _para(p, "↓  TCP / 4096  (faketcp)", size=13, color=ACCENT,
          font="Consolas", align=PP_ALIGN.CENTER, space_after=2)
    p = tf.add_paragraph()
    _para(p, "udp2raw server  →  wg server", size=13, color=BLACK,
          font="Consolas", align=PP_ALIGN.CENTER, space_after=2)

    _add_text(s, LMARGIN, 3.85, WIDTH, 0.40,
              "Why udp2raw, specifically:",
              size=17, bold=True, color=NAVY)
    _bullet_list(s, LMARGIN, 4.30, WIDTH, 2.20, [
        "≈259,000 release-binary downloads on the primary repo, "
        "+41,000 on the multiplatform fork (GitHub API, May 2026).",
        "Reported blocked by state-level DPI in Iran and elsewhere "
        "(udp2raw issue #505, net4people thread #253).",
        "Cited in the WireGuard project's own “Known Limitations” page.",
        "No peer-reviewed analysis. Searched USENIX, NDSS, IMC, FOCI, PETS, CCS.",
    ], size=15, line_spacing=1.20)

    _footer(s, 3, 0)
    _notes(s, """Two paths in our lab (same WG keys, only the outer transport differs)
  • Direct: WireGuard over UDP. What the Great Firewall already blocks.
  • Obfuscated: udp2raw rewraps each WG packet as a TCP segment on port 4096.
  • "faketcp" = shaped like TCP but not a real TCP connection.
  • Why TCP? Looks normal — it's what web browsers use.

Why udp2raw specifically
  • ~259,000 binary downloads (actual runs, not GitHub stars).
  • Reportedly blocked at ISP level in Iran (issue #505, net4people #253).
  • Zero peer-reviewed analysis. Searched USENIX, NDSS, IMC, FOCI, PETS, CCS.

Why not other tools?
  • AmneziaWG, swgp-go = modify WireGuard itself. Different category.
  • udp2raw = only big, unstudied tool in the "wrap it generically" category.""")

    # ============================================================
    # Slide 4 — Methodology overview
    # ============================================================
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s,
                 "Two attacks, one lab",
                 "Following Xue et al.'s active-then-passive pattern (USENIX Security ’22) for OpenVPN")

    box_w = (WIDTH - 0.5) / 2
    # C1 card
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(LMARGIN), Inches(BODY_TOP),
                             Inches(box_w), Inches(4.50))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = NAVY
    tf = box.text_frame
    tf.margin_left = Pt(16); tf.margin_top = Pt(14); tf.margin_right = Pt(16)
    tf.word_wrap = True
    _para(tf.paragraphs[0], "C1 · Active prober",
          size=22, bold=True, color=NAVY, space_after=10)
    for line in [
        "Send 5 stateless TCP probes to (IP, port).",
        "Real Linux TCP answers all 5.",
        "udp2raw answers SYN, drops 3 of 4 follow-ups.",
        "Verdict in ≤ 9 seconds. Same verdict 5/5 trials.",
    ]:
        p = tf.add_paragraph()
        _para(p, "•   " + line, size=14, color=BLACK, space_after=6,
              line_spacing=1.18)
    p = tf.add_paragraph(); p.space_before = Pt(12)
    _para(p, "Adversary cost:  ≈ 1.7 KB and ≈ 9 s per host.",
          size=12, color=GREY, space_after=2)

    # C2 card
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(LMARGIN + box_w + 0.5), Inches(BODY_TOP),
                             Inches(box_w), Inches(4.50))
    box.fill.solid(); box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = ACCENT
    tf = box.text_frame
    tf.margin_left = Pt(16); tf.margin_top = Pt(14); tf.margin_right = Pt(16)
    tf.word_wrap = True
    _para(tf.paragraphs[0], "C2 · Two-feature classifier",
          size=22, bold=True, color=ACCENT, space_after=10)
    for line in [
        "bulk_fraction:  share of MTU-class packets.",
        "ack60_fraction:  share of 60-byte TCP ACKs.",
        "Both fall out of how the protocols are written, "
        "not statistical luck.",
        "Random Forest:  99.9 % accuracy, AUC = 1.000.",
    ]:
        p = tf.add_paragraph()
        _para(p, "•   " + line, size=14, color=BLACK, space_after=6,
              line_spacing=1.18)
    p = tf.add_paragraph(); p.space_before = Pt(12)
    _para(p, "Trained on 24 WG flows + 1058 ISCXVPN2016 non-VPN flows.",
          size=12, color=GREY, space_after=2)

    _footer(s, 4, 0)
    _notes(s, """Two attacks, definitions
  • Active = send packets, watch the reply.
  • Passive = just watch traffic going by.
  • Template from Xue et al., USENIX Security 2022 Distinguished Paper (did OpenVPN, not WireGuard).

C1 — Active (left card)
  • 5 TCP probes, under 9 seconds.
  • Same answer every time. Details next slide.

C2 — Passive (right card)
  • Flow = one conversation between two computers.
  • For each flow, compute 2 numbers, feed to a Random Forest.
  • Random Forest (RF) = standard ML model that learns rules from examples.
  • Features are mechanical, not statistical:
      – WireGuard pads every packet to max size.
      – udp2raw acks every wrapped packet 1:1.

Training data
  • 24 WireGuard flows we captured ourselves.
  • 1058 normal flows from ISCXVPN2016 (standard public dataset for this work).""")

    # ============================================================
    # Slide 5 — C1 results
    # ============================================================
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s,
                 "C1: one set of probes distinguishes udp2raw from real TCP",
                 "Three targets on the same OCI host. Same verdict in 5/5 repeated trials.")

    headers = ["Probe", "TCP/22  (real SSH)", "TCP/4096  (udp2raw)", "TCP/9999  (closed)"]
    rows = [
        ["P1   SYN",                "SYN-ACK in 181 ms",   "SYN-ACK in 163 ms",   "no response"],
        ["P2   SYN + 32 B payload", "SYN-ACK + 2 B echo",  "silent",              "no response"],
        ["P3   bogus-seq ACK",      "RST in 81 ms",        "RST in 91 ms",        "no RST"],
        ["P4   SYN, WS = 14",       "SYN-ACK",             "silent",              "no response"],
        ["P5   FIN to unopened",    "RST",                 "silent",              "no response"],
    ]

    top = BODY_TOP
    col_lefts  = [LMARGIN, 3.40, 6.50, 9.80]
    col_widths = [2.85,    3.10, 3.30, 2.85]
    row_h = 0.42

    for i, h in enumerate(headers):
        _add_text(s, col_lefts[i], top, col_widths[i], row_h,
                  h, size=13, bold=True, color=NAVY)
    _accent_bar(s, LMARGIN, top + row_h, WIDTH, color=NAVY)

    for r, row in enumerate(rows):
        y = top + row_h + 0.10 + r * 0.40
        for i, val in enumerate(row):
            color = ACCENT if val == "silent" else BLACK
            font = "Consolas" if i > 0 else "Calibri"
            _add_text(s, col_lefts[i], y, col_widths[i], row_h,
                      val, size=13, color=color, font=font)

    # Summary band
    y = top + row_h + 0.10 + len(rows) * 0.40 + 0.15
    _accent_bar(s, LMARGIN, y, WIDTH, color=NAVY)
    sum_y = y + 0.18

    _add_text(s, col_lefts[0], sum_y, col_widths[0], row_h,
              "Total time", size=13, bold=True, color=NAVY)
    for i, val in enumerate(["0.5 s", "8.5 s", "15.5 s"]):
        _add_text(s, col_lefts[i+1], sum_y, col_widths[i+1], row_h,
                  val, size=13, bold=True, color=BLACK, font="Consolas")
    sum_y2 = sum_y + 0.40
    _add_text(s, col_lefts[0], sum_y2, col_widths[0], row_h,
              "Verdict", size=13, bold=True, color=NAVY)
    for i, val in enumerate(["REAL_TCP", "UDP2RAW_FAKETCP", "UNREACHABLE"]):
        c = ACCENT if "UDP2RAW" in val else BLACK
        _add_text(s, col_lefts[i+1], sum_y2, col_widths[i+1], row_h,
                  val, size=13, bold=True, color=c, font="Consolas")

    _add_text(s, LMARGIN, 6.20, WIDTH, 0.40,
              "Discriminator: count silent responses among {P2, P4, P5}.  Real TCP answers all three.  udp2raw answers none.",
              size=14, color=GREY)

    _footer(s, 5, 0)
    _notes(s, """Setup — three columns, same server, three ports
  • TCP/22 = real SSH (real-TCP control).
  • TCP/4096 = udp2raw.
  • TCP/9999 = closed (negative control).

TCP terms for the table
  • SYN starts a connection. SYN-ACK accepts. RST rejects. FIN closes.

Probes that DON'T discriminate (answered by both)
  • P1 (SYN): udp2raw answers — that's the disguise.
  • P3 (bogus ACK): kernel (not udp2raw) generates the RST.

The signal — probes 2, 4, 5
  • P2: SYN with 32 bytes of payload.
  • P4: SYN with unusual TCP option.
  • P5: FIN to a port with no connection.
  • Real Linux kernel answers all three. udp2raw drops all three.
  • udp2raw's parser was written for one TCP shape; anything else, it ignores.

Rule
  • Count silent responses among {P2, P4, P5}.
  • Real TCP = 0 silent. udp2raw = 3 silent.

Timing
  • Real TCP: 0.5 s.
  • udp2raw: 8.5 s (we wait out timeouts on the silent probes).
  • Closed port: 15.5 s.
  • Same verdict 5/5 trials.""")

    # ============================================================
    # Slide 6 — C2 features (table + scatter)
    # ============================================================
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s,
                 "C2: two features carry the entire signal",
                 "Class means across 24 WireGuard flows and 1058 ISCXVPN2016 non-VPN flows")

    # Left half: feature table
    headers = ["Feature", "WireGuard", "Non-VPN", "Cohen's d"]
    rows_top = [
        ["bulk_fraction",   "0.553 ± 0.186", "0.019 ± 0.066", "3.83"],
        ["ack60_fraction",  "0.295 ± 0.187", "0.069 ± 0.169", "1.27"],
    ]
    rows_dim = [
        ["len_entropy",          "1.94 ± 0.82", "1.23 ± 1.42",  "—"],
        ["dominant_size_frac.",  "0.50 ± 0.19", "0.71 ± 0.30",  "(inv.)"],
        ["top3_size_fraction",   "0.88 ± 0.15", "0.87 ± 0.19",  "—"],
        ["rate_pps",             "3.23 ± 0.90", "3.37 ± 30.27", "—"],
    ]

    top = BODY_TOP
    col_lefts  = [LMARGIN, 2.70, 4.70, 6.40]
    col_widths = [2.10,    1.95, 1.65, 0.85]

    for i, h in enumerate(headers):
        _add_text(s, col_lefts[i], top, col_widths[i], 0.32,
                  h, size=12, bold=True, color=NAVY)
    _accent_bar(s, LMARGIN, top + 0.32, 6.85, color=NAVY)

    y = top + 0.42
    for row in rows_top:
        for i, val in enumerate(row):
            font = "Consolas" if i > 0 else "Calibri"
            color = ACCENT if i == 3 else BLACK
            bold = (i == 3)
            _add_text(s, col_lefts[i], y, col_widths[i], 0.30,
                      val, size=12, color=color, bold=bold, font=font)
        y += 0.36

    _accent_bar(s, LMARGIN, y + 0.04, 6.85, color=GREY, height_pt=1.0)
    y += 0.16

    for row in rows_dim:
        for i, val in enumerate(row):
            font = "Consolas" if i > 0 else "Calibri"
            _add_text(s, col_lefts[i], y, col_widths[i], 0.30,
                      val, size=11, color=GREY, font=font)
        y += 0.32

    # Right half: scatter plot, fitted to a strict box
    SCATTER_BOX_LEFT = 7.55
    SCATTER_BOX_TOP  = BODY_TOP - 0.05
    SCATTER_BOX_W    = SLIDE_W - SCATTER_BOX_LEFT - RMARGIN
    SCATTER_BOX_H    = 4.20
    if os.path.exists(SCATTER):
        _add_picture_fit(s, SCATTER,
                         SCATTER_BOX_LEFT, SCATTER_BOX_TOP,
                         SCATTER_BOX_W, SCATTER_BOX_H)
    _add_text(s, SCATTER_BOX_LEFT, SCATTER_BOX_TOP + SCATTER_BOX_H + 0.05,
              SCATTER_BOX_W, 0.50,
              "All 1082 flows in the two-feature space. "
              "24/24 WG flows have bulk_fraction ≥ 0.32; only 4/1058 "
              "non-VPN flows fall in the (≥0.2, ≥0.15) corner.",
              size=10, color=GREY)

    _add_text(s, LMARGIN, 6.05, 6.85, 0.50,
              "Naive intuition picked dominant_size_fraction. "
              "Real-world background INVERTS that signal "
              "(many idle flows are degenerately concentrated).",
              size=11, color=ACCENT)

    _footer(s, 6, 0)
    _notes(s, """Feature 1 — bulk_fraction
  • Share of packets in a flow that are "big" (≥1200 bytes).
  • Why it works: WireGuard pads every packet up to near MTU (~1500 B).
  • MTU (or Maximum Transmission Unit)= max packet size the link will carry.
  • WireGuard: 55% big packets. Normal: 2%.
  • Cohen's d = 3.83.
  • Cohen's d = "A measurement that quantifies the difference between two averages in units of standard deviation" Or, how cleanly two groups separate. Over 0.8 is "large." We have 3.83.

Feature 2 — ack60_fraction
  • Share of 60-byte TCP ACK packets.
  • Normal TCP uses "delayed ACK" — 1 ACK per 2 data packets, so ~33% ACKs.
  • udp2raw breaks this: each WG packet wrapped as 1 separate TCP segment.
  • Kernel ACKs each arrival individually → ACK fraction climbs.
  • WG-in-udp2raw: 30%. Normal: 7%. Cohen's d = 1.27 (still large).

Scatter plot (right)
  • 1082 flows total. Orange = WireGuard. Grey = normal.
  • Barely overlap.
  • All 24 WG flows have bulk_fraction ≥ 0.32.
  • Only 4 of 1058 normal flows are anywhere near the WG cluster.

Orange note (bottom-left) — scientific honesty
  • I expected dominant_size_fraction to be the killer feature.
  • Real data inverted it: public dataset has idle keepalive flows where every packet is identical.
  • Those flows score HIGHER than WireGuard on that feature.
  • We dropped it. Surviving features are grounded in protocol mechanics, not intuition.""")

    # ============================================================
    # Slide 7 — C2 classifier results
    # ============================================================
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s,
                 "C2: two-feature Random Forest hits 99.9 %",
                 "5-fold stratified cross-validation; class-balanced; n = 1082")

    # Left: the four big numbers
    big_y = BODY_TOP + 0.10
    _add_text(s, LMARGIN, big_y, 5.5, 0.40,
              "Two-feature Random Forest", size=18, bold=True, color=NAVY)

    metrics = [
        ("99.91 %", "Accuracy"),
        ("1.000",   "Precision  (zero false positives in 1058)"),
        ("0.958",   "Recall  (23 of 24 WG flows caught)"),
        ("1.000",   "ROC AUC"),
    ]
    y = big_y + 0.55
    for big, label in metrics:
        _add_text(s, LMARGIN, y, 2.30, 0.55,
                  big, size=28, bold=True, color=ACCENT, font="Consolas")
        _add_text(s, LMARGIN + 2.45, y + 0.12, 3.60, 0.45,
                  label, size=13, color=BLACK)
        y += 0.62

    # Comparison table
    cmp_y = y + 0.20
    _accent_bar(s, LMARGIN, cmp_y, 6.0, color=NAVY)
    _add_text(s, LMARGIN, cmp_y + 0.10, 6.0, 0.32,
              "Adding more features does not help.",
              size=13, bold=True, color=NAVY)
    rows = [
        ["RF, 2 features", "0.999", "1.000", "0.958"],
        ["RF, 8 features", "0.998", "1.000", "0.917"],
        ["LR, 2 features", "0.969", "0.414", "1.000"],
    ]
    headers = ["model", "acc", "prec", "rec"]
    cl = [LMARGIN, 3.10, 4.10, 5.10]
    cw = [2.50, 1.00, 1.00, 1.00]
    yy = cmp_y + 0.50
    for i, h in enumerate(headers):
        _add_text(s, cl[i], yy, cw[i], 0.30,
                  h, size=10, bold=True, color=GREY)
    yy += 0.30
    for row in rows:
        for i, v in enumerate(row):
            font = "Consolas" if i > 0 else "Calibri"
            _add_text(s, cl[i], yy, cw[i], 0.30,
                      v, size=11, color=BLACK, font=font)
        yy += 0.30

    # Right: confusion + ROC, fitted into strict boxes
    PLOT_LEFT = 7.55
    PLOT_W    = SLIDE_W - PLOT_LEFT - RMARGIN  # ~5.2 inches
    PLOT_H    = (BODY_BOTTOM - BODY_TOP - 0.20) / 2  # ~2.3 inches each
    if os.path.exists(CONFUSION_2F):
        _add_picture_fit(s, CONFUSION_2F,
                         PLOT_LEFT, BODY_TOP,
                         PLOT_W, PLOT_H)
    if os.path.exists(ROC_2F):
        _add_picture_fit(s, ROC_2F,
                         PLOT_LEFT, BODY_TOP + PLOT_H + 0.20,
                         PLOT_W, PLOT_H)

    _footer(s, 7, 0)
    _notes(s, """Headline numbers (with definitions)
  • Accuracy 99.91% — overall fraction labeled correctly.
  • Precision 1.000 — when we say "WireGuard," we're always right. Zero false alarms on 1058 normal flows.
  • Recall 0.958 — we catch 23 of 24 actual WG flows. One slips through.
  • ROC AUC 1.000 — single score from 0.5 (random) to 1.0 (perfect), across all sensitivity settings. We're at the ceiling.

Adding more features doesn't help (small table)
  • RF 8 features catches 1 FEWER WG flow than RF 2 features.
  • Extra features added noise, not signal.
  • LR = Logistic Regression, simpler model that draws a straight line between classes.
  • LR catches everything but raises ~3% false alarms — real boundary isn't straight.

Plots on the right
  • Top = confusion matrix: 2x2 grid of correct vs incorrect labels. Almost everything on the diagonal.
  • Bottom = ROC curve hugs the top-left corner. Shape of a near-perfect classifier.""")

    # ============================================================
    # Slide 8 — Related work and limitations
    # ============================================================
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s,
                 "Where this sits in the literature",
                 "Narrow contribution alongside the recent Xue et al. line of work")

    col_w = (WIDTH - 0.5) / 2
    _add_text(s, LMARGIN, BODY_TOP, col_w, 0.38,
              "Closely related",
              size=17, bold=True, color=NAVY)
    _bullet_list(s, LMARGIN, BODY_TOP + 0.45, col_w, 4.20, [
        "Xue et al., USENIX Sec ’22.  Passive + active for OpenVPN. Methodological template.",
        "Xue et al., USENIX Sec ’24.  Encapsulated TLS handshakes. Doesn’t fire on WireGuard (no nested TLS).",
        "Xue et al., NDSS ’25.  Cross-layer RTT. Attenuated on UDP-only short flows.",
        "Wu et al., USENIX Sec ’23.  GFW entropy detector for fully-encrypted protocols.",
        "Alice et al., IMC ’20.  Shadowsocks active probes. Probe taxonomy.",
        "Frolov & Wustrow, NDSS ’20.  Probe-resistant proxy detection.",
    ], size=13, line_spacing=1.16, space_after=6)

    right_x = LMARGIN + col_w + 0.5
    _add_text(s, right_x, BODY_TOP, col_w, 0.38,
              "What this paper does NOT claim",
              size=17, bold=True, color=ACCENT)
    _bullet_list(s, right_x, BODY_TOP + 0.45, col_w, 4.20, [
        "Single client/server pair. No ISP-scale deployment trace.",
        "udp2raw v20230206.0 only. Later forks may behave differently.",
        "Static defenses: a delayed-ACK patch + WG MTU below the bulk threshold weakens C2.",
        "C1’s P3 (bogus ACK) is mildly hostile. Adversary should fire only at already-suspected hosts.",
        "Not benchmarked against AmneziaWG, a more popular obfuscator for WG, or swgp-go, wstunnel. Future work.",
    ], size=13, line_spacing=1.16, space_after=6)

    _footer(s, 8, 0)
    _notes(s, """Lit positioning — Xue group at Michigan dominates this space
  • 2022 OpenVPN paper → our methodology template.
  • 2024 paper detects nested TLS handshakes → doesn't fire (WG has no TLS).
  • 2025 NDSS uses cross-layer RTT anomalies → attenuates on our short UDP flows.
  • → Protocol-agnostic methods don't solve our case. Protocol-specific structural features remain the approach.

What we are NOT claiming
  • Single client/server. No ISP-scale data.
  • One version of udp2raw (v20230206.0). Later forks may differ.
  • Defeatable by a maintainer:
      – Delayed ACK + smaller WG MTU weakens C2.
      – More conformant TCP emulation weakens C1.
  • Bogus-ACK probe (P3) is mildly hostile → fire only at already-suspected hosts.
  • Not benchmarked against AmneziaWG, a more popular obfuscator for WG, or swgp-go, wstunnel. Future work.""")

    # ============================================================
    # Slide 9 — Takeaways
    # ============================================================
    s = prs.slides.add_slide(blank)
    slides.append(s)
    _title_block(s, "Takeaway")

    msgs = [
        ("WireGuard's wire format leaks.", NAVY,
         "A 25-line classifier handles bare WG. udp2raw is the deployed fix."),
        ("udp2raw doesn't actually fix it.", ACCENT,
         "Five TCP probes in 8.5 seconds (C1).  Two flow features, RF, AUC = 1.0 (C2)."),
        ("Both signals are structural.", NAVY,
         "udp2raw drops unfamiliar TCP shapes; WG pads to MTU; udp2raw acks 1:1. None are statistical luck."),
        ("Defenses are obvious; the upstream tool does not implement them.", ACCENT,
         "Delayed-ACK plus a sub-bulk WG MTU closes C2. More-conformant TCP emulation closes C1."),
    ]

    y = BODY_TOP
    for headline, color, body in msgs:
        _add_text(s, LMARGIN, y, WIDTH, 0.40,
                  headline, size=20, bold=True, color=color)
        _add_text(s, LMARGIN, y + 0.45, WIDTH, 0.50,
                  body, size=13, color=BLACK)
        y += 1.10

    _add_text(s, LMARGIN, 6.30, WIDTH, 0.30,
              "Code, configs, evidence, paper, and slides are in the project repository.",
              size=12, color=GREY)

    _footer(s, 9, 0)
    _notes(s, """1. WireGuard's wire format leaks
  • Known result. Re-implemented as our baseline.

2. udp2raw doesn't fix it
  • 8.5 s with the 5-packet prober (C1).
  • 2 passive features, AUC = 1.0 (C2).
  • Pick your weapon.

3. Not a statistical fluke — mechanical
  • WG pads to MTU because that's its design.
  • udp2raw acks 1:1 because that's how it wraps.
  • udp2raw drops unfamiliar TCP shapes — parser was written for one shape.
  • This is because udp2raw fakes TCP in userspace with a minimal parser to only handle the packet shapes it needs, everything else gets dropped.
           
4. Defenses are obvious
  • Delayed ACK + smaller WG MTU kills C2.
  • More conformant TCP emulation kills C1.
  • Sketched in the paper, not patched upstream. Somebody else's PR.

Happy to take questions. LIVE DEMO NEXT.""")

    # ============================================================
    # Patch footers with actual total
    # ============================================================
    total = len(slides)
    for i, s in enumerate(slides, 1):
        # remove placeholder footers (the "X / 0" boxes added by _footer)
        for sh in list(s.shapes):
            if sh.has_text_frame:
                txt = sh.text_frame.text
                if " / 0" in txt:
                    sh._element.getparent().remove(sh._element)
        _footer(s, i, total)

    now = datetime.now(timezone.utc)
    cp = prs.core_properties
    cp.author = "Steven Schiavone"
    cp.last_modified_by = "Steven Schiavone"
    cp.title = "Two-Feature Detection of WireGuard-in-udp2raw"
    cp.created = now
    cp.modified = now

    prs.save(OUT)
    print(f"wrote {OUT}  ({total} slides)")


if __name__ == "__main__":
    build()
