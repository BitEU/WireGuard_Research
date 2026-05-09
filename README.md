# Fingerprinting WireGuard-in-udp2raw

Capstone project for CYB623, Pace University.
Steven Schiavone & Nicholas Johannsen.

A WireGuard server on Oracle Cloud, a Kali client in VirtualBox, two
detectors against the udp2raw obfuscation shim:

1. **Active prober** that distinguishes a udp2raw faketcp listener from a
   real Linux kernel TCP listener in ~8 seconds with five stateless probes.
2. **Two-feature passive classifier** that separates 24 WireGuard flows
   from 1058 non-VPN flows in ISCXVPN2016 at 99.9% accuracy / AUC 1.000.

The full writeup is in [`latex-paper/report.tex`](latex-paper/report.tex).

---

## What's where

```
scripts/        deploy + tear down server (OCI) and client (Kali)
configs/        client WireGuard config (regenerated per peer)
creds/          SSH key for the OCI VM (gitignored)
dpi-baseline/   Section 4 of the paper: trivial passive WG fingerprint
novel/          Sections 5-6: active prober + flow-feature classifier
evidence/       timestamped artifacts from every run
latex-paper/    IEEE conference template with report.tex
master_set/     canonical artifacts the paper's numbers are pulled from
notes/          lit-review and dataset citation notes
slides/         presentation deck (build_slides.py + .pptx)
demo/           live TUI demo for the in-person presentation
```

---

## Setup, first time

You need:

* A Windows host (this guide assumes 11). Mac/Linux works with minor adjustments.
* An Oracle Cloud Free Tier account.
* VirtualBox installed.
* A Kali Linux 2025.x VM in VirtualBox. Adapter set to **NAT** (`10.0.2.15`).
  Wi-Fi bridging on consumer NICs is broken; do not use bridged.
* The project folder (this repo) shared into the Kali VM at `/media/sf_Git`.

### 1. Spin up the OCI VM

* Region: any. Free tier eligible.
* Shape: `VM.Standard.A1.Flex`, **Oracle Linux 9** image (aarch64).
* SSH key: generate or upload, save private key to `creds/ssh-key-XXX.key`.
* Note the public IP; you'll set it as `SERVER_IP` later.

In the OCI console, open ingress rules on the subnet's default security list:

* `UDP 51820` from `0.0.0.0/0`  bare WireGuard
* `TCP 4096`  from `0.0.0.0/0`  udp2raw faketcp
* `TCP 22`    from your IP (or anywhere)  SSH

### 2. Install the server

From PowerShell on Windows:

```powershell
$key = ".\creds\ssh-key-XXXX.key"
$ip  = "<your.oci.public.ip>"

scp -i $key .\scripts\01_server_install.sh .\scripts\02_add_peer.sh "opc@${ip}:/home/opc/"
ssh -i $key "opc@$ip" "bash ~/01_server_install.sh"
ssh -i $key "opc@$ip" "sudo bash ~/02_add_peer.sh lab-client"
```

The second command prints the client config block. Copy the
`[Interface]…[Peer]` content and save it to `configs/lab-client.conf`,
overwriting the placeholder.

### 3. Install the client

In the Kali VM:

```bash
sudo bash /media/sf_Git/scripts/03_client_install.sh
```

This installs WireGuard, Scapy, tshark, tcpdump, scikit-learn, and udp2raw,
plus drops in two configs: `wg-direct` (bare) and `wg-obfuscated` (via udp2raw).

---

## Running the demo

In Kali, three steps for the full paper reproduction.

### Step 1  Trivial passive fingerprint (Section 4)

Show that bare WireGuard is detected, and that udp2raw hides it from the
byte-level classifier.

```bash
sudo wg-quick up wg-direct
PROTO=udp PORT=51820 /media/sf_Git/dpi-baseline/run_demo.sh baseline
sudo wg-quick down wg-direct

sudo wg-quick up wg-obfuscated
PROTO=any PORT=4096 /media/sf_Git/dpi-baseline/run_demo.sh udp2raw
sudo wg-quick down wg-obfuscated
```

Outputs land in `evidence/<timestamp>_*.{pcap,txt}`.

### Step 2  Active prober (Contribution 1)

```bash
sudo python3 /media/sf_Git/novel/active_probe.py <SERVER_IP> 4096   # udp2raw
sudo python3 /media/sf_Git/novel/active_probe.py <SERVER_IP> 22     # real TCP
sudo python3 /media/sf_Git/novel/active_probe.py <SERVER_IP> 9999   # closed
```

Each emits a verdict: `UDP2RAW_FAKETCP_SUSPECTED`, `REAL_TCP`, or
`UNREACHABLE_OR_FILTERED`.

### Step 3  Flow-feature classifier (Contribution 2)

Capture WireGuard samples (90s each, with two tunnel modes, with six trials):

```bash
for trial in 1 2 3 4 5 6; do
  sudo wg-quick up wg-direct
  DURATION=90 PROTO=udp PORT=51820 \
    /media/sf_Git/dpi-baseline/run_demo.sh wg-direct-trial$trial
  sudo wg-quick down wg-direct

  sudo wg-quick up wg-obfuscated
  DURATION=90 PROTO=any PORT=4096 \
    /media/sf_Git/dpi-baseline/run_demo.sh wg-udp2raw-trial$trial
  sudo wg-quick down wg-obfuscated
done
```

Get the negative class (ISCXVPN2016 NonVPN-PCAPs-01.zip from the CIC,
~800 MB):

```bash
mkdir -p ~/iscx-nonvpn && cd ~/iscx-nonvpn
unzip -q /path/to/NonVPN-PCAPs-01.zip
bash /media/sf_Git/novel/extract_dataset.sh ~/iscx-nonvpn background
```

Extract features from positives:

```bash
cd /media/sf_Git/novel
for p in /media/sf_Git/evidence/*wg-direct*.pcap; do
  python3 flow_features.py "$p" --label wg-direct
done
for p in /media/sf_Git/evidence/*wg-udp2raw*.pcap; do
  python3 flow_features.py "$p" --label wg-udp2raw
done
```

Train and evaluate (full and minimal models):

```bash
python3 train_classifier.py \
  /media/sf_Git/evidence/*wg-direct*_features.csv \
  /media/sf_Git/evidence/*wg-udp2raw*_features.csv \
  /media/sf_Git/evidence/*background*_combined.csv

TWO_FEATURE=1 python3 train_classifier.py \
  /media/sf_Git/evidence/*wg-direct*_features.csv \
  /media/sf_Git/evidence/*wg-udp2raw*_features.csv \
  /media/sf_Git/evidence/*background*_combined.csv
```

The two-feature run is the headline (`bulk_fraction` and `ack60_fraction` only,
~99.9% accuracy, AUC 1.000). Confusion matrix, ROC, and feature-importance
plots land in `evidence/<timestamp>_classifier_*.png`.

---

## Live demo (in-person presentation)

For the actual in-person demo, use the snappy TUI dashboard instead of
running the steps above one at a time. Five scenes, manual advance with
SPACE, runs in about 90 seconds:

```bash
sudo apt install -y python3-rich python3-scapy python3-sklearn python3-pandas
sudo python3 /media/sf_Git/demo/demo.py
```

See [`demo/RUNBOOK.md`](demo/RUNBOOK.md) for the talking-points cheat sheet.

---

## Tear down

```powershell
ssh -i $key "opc@$ip" "bash ~/99_server_teardown.sh"
```

```bash
sudo bash /media/sf_Git/scripts/99_client_teardown.sh
```

OCI ingress rules and the VM itself are not touched; remove them manually.

---

## Building the report PDF

Or, with `latexmk` (cleaner; runs only as many passes as needed):

```powershell
cd latex-paper
latexmk -pdf -halt-on-error report.tex
```

Output is `latex-paper/report.pdf`. To clean intermediate files: `latexmk -C`.

---

## Building the slides

The deck is a generated artifact, not hand-edited. Regenerate after any
change to `master_set/`:

```powershell
python -m pip install python-pptx
python slides\build_slides.py
```

Output is `slides/WireGuard-udp2raw-detection.pptx`.

---

## Reading order if you want to understand the project

1. `latex-paper/report.tex`  the writeup.
2. `dpi-baseline/wg_classify.py`  the 25-line WireGuard detector.
3. `novel/active_probe.py`  Contribution 1.
4. `novel/flow_features.py` and `novel/train_classifier.py`  Contribution 2.
5. `evidence/`  every number in the paper has a timestamped artifact here.
