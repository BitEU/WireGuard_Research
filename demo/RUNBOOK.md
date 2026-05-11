# Demo runbook · WireGuard-in-udp2raw

A one-page cheat sheet for the in-person presentation. Run order, fall-backs,
and what to say while each scene runs.

---

## 5 minutes before

In the Kali VM, in **one terminal**, full-screen the window:

```bash
sudo apt install -y python3-rich python3-scapy python3-sklearn python3-pandas tcpdump
sudo bash /media/sf_Git/scripts/03_client_install.sh   # if not already
```

Confirm the OCI server is up:

```bash
ssh -i /media/sf_Git/creds/ssh-key-2026-05-10.key opc@150.136.195.244 \
  "sudo systemctl is-active wg-quick@wg0 udp2raw-server"
# both should print 'active'
```

If it isn't, `sudo systemctl start wg-quick@wg0 udp2raw-server` on the OCI box.

---

## Launch

Press **F11** (or whatever fullscreens your terminal). Then:

```bash
sudo python3 /media/sf_Git/demo/demo.py
```

You're now in the TUI. Cover the title slide while you greet the room.

| key       | action                          |
| --------- | ------------------------------- |
| SPACE / ENTER | next scene                  |
| Q         | quit                            |

---

## What to say at each scene

The TUI does the showing. Your job is the talking. Suggested script ≤ 2 minutes.

### Scene 1 · Bare WireGuard (≈ 15 s of capture)

> *WireGuard's wire format is so regular that a 25-line classifier identifies it
> with negligible false-positive rate. Watch what happens when we point it at
> a real WireGuard tunnel.*

When the result panel populates: read the `HANDSHAKE_INIT (148 B)` and
`HANDSHAKE_RESPONSE (92 B)` numbers out loud. *That's the byte signature
WireGuard's whitepaper says is out of scope to hide. The Great Firewall blocks
this in production.*

### Scene 2 · udp2raw wraps it (≈ 20 s of capture)

> *Same classifier, same predicate, but now WireGuard is wrapped inside
> udp2raw faketcp. Same machine, same keys, only the transport changed.*

When the result panel hits **BYTE FINGERPRINT NEUTRALIZED**: *Zero matches.
This is what udp2raw is sold as doing. It works. The byte fingerprint is gone.*

Then pivot: *But that's only one kind of detection. Next we'll show two
others that go straight through.*

### Scene 3 · Active prober (≈ 25 s for three targets)

> *We send five stateless TCP probes to three different ports on the same OCI
> host: udp2raw, real SSH, a closed port. Real Linux kernels answer every
> probe. udp2raw drops three of four. Watch the verdicts.*

When all three rows fill: read the udp2raw row. *Eight and a half seconds,
deterministic on five repeated trials, no traffic capture required.*

### Scene 4 · Live features overlay (≈ 5 s of work)

> *Now we extract two features from the pcaps we just captured: the fraction
> of MTU-class packets and the fraction of 60-byte TCP ACKs. We plot them
> against eleven hundred non-VPN flows from ISCXVPN2016.*

When the scatter renders: *The yellow stars are this session, in this room.
The orange dots are the WireGuard training set. The grey dust is real-world
non-VPN traffic. They don't overlap.*

### Scene 5 · Classifier verdict (≈ 5 s)

> *Random Forest trained on twenty-four WireGuard flows and a thousand
> background flows. Two features. Cross-validated AUC of one. We feed it
> the flows we just captured.*

Read the predictions. *Every live flow flagged, high confidence. The
fingerprint that udp2raw was supposed to hide is still there — udp2raw just
moved it from the byte layer to the flow layer.*

Press SPACE one more time to land on the **Q&A** panel and stop talking.

---

## If it breaks

| symptom                                | fix                                                                                                                                       |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Scene 1 finds 0 packets                | OCI server is down. `ssh opc@... 'sudo systemctl restart wg-quick@wg0'` and retry.                                                        |
| Scene 2 udp2raw doesn't connect        | Wait 12 s on scene 2 setup; if still 0, OCI's udp2raw-server is down: `ssh opc@... 'sudo systemctl restart udp2raw-server'`.              |
| Scene 3 probes all "unreachable"       | OCI security list dropped. `ssh opc@... 'sudo iptables -L INPUT -n'` and reapply `01_server_install.sh`.                                  |
| Scene 4 / 5 says "0 live flows"        | Scenes 1 and 2 didn't capture; loop back to fix scene 1 first.                                                                            |
| TUI looks broken in your terminal      | Resize the terminal window before launching. Needs ≥ 100 cols × 40 rows. Press Q, resize, relaunch.                                       |
| You need to bail mid-scene             | Press Q. Tear down with `sudo wg-quick down wg-direct; sudo wg-quick down wg-obfuscated` so the next launch starts clean.                 |

---

## Hard fallback

If the network is hostile and live capture is impossible, the report's
`master_set/` folder has frozen pcaps that prove every claim. Open the PDF
to page 5 (the C1 results table) and page 6 (the scatter plot) and walk
through those instead. The TUI is a nice-to-have; the paper is the deliverable.

---

## After the demo

```bash
sudo wg-quick down wg-direct 2>/dev/null
sudo wg-quick down wg-obfuscated 2>/dev/null
```

Press Q to leave the TUI cleanly. The terminal will restore.
