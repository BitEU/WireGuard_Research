import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from wg_classify import classify

EVIDENCE_DIR = "/media/sf_Git/evidence"


def init():
    return b"\x01\x00\x00\x00" + b"\x00"*4 + b"\x11"*32 + b"\x22"*48 + b"\x33"*28 + b"\x44"*16 + b"\x55"*16

def resp():
    return b"\x02\x00\x00\x00" + b"\x00"*4 + b"\x00"*4 + b"\x11"*32 + b"\x22"*16 + b"\x44"*16 + b"\x55"*16

def cookie():
    return b"\x03\x00\x00\x00" + b"\x00"*4 + b"\x77"*24 + b"\x88"*32

def data(n=80):
    return b"\x04\x00\x00\x00" + b"\x00"*4 + b"\x00"*8 + b"\xaa"*n


def short():        return b"\x01\x00\x00"
def bad_type():     return b"\x09\x00\x00\x00" + b"\x00"*144
def bad_reserved(): return b"\x01\x01\x00\x00" + b"\x00"*144
def wrong_len():    return b"\x01\x00\x00\x00" + b"\x00"*100


cases = [
    ("init",          init(),          ("HANDSHAKE_INIT", 1, True)),
    ("response",      resp(),          ("HANDSHAKE_RESPONSE", 2, True)),
    ("cookie",        cookie(),        ("COOKIE_REPLY", 3, True)),
    ("data80",        data(80),        ("TRANSPORT_DATA", 4, False)),
    ("too short",     short(),         None),
    ("bad type",      bad_type(),      None),
    ("nonzero rsvd",  bad_reserved(),  None),
    ("wrong length",  wrong_len(),     None),
]


class Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, s):
        for st in self.streams: st.write(s); st.flush()
    def flush(self):
        for st in self.streams: st.flush()


def main():
    write_evidence = "--no-evidence" not in sys.argv
    if write_evidence:
        os.makedirs(EVIDENCE_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(EVIDENCE_DIR, f"{ts}_classifier-selftest.txt")
        f = open(path, "w")
        out = Tee(sys.stdout, f)
    else:
        path = None
        out = sys.stdout

    print(f"# classifier self-test at {datetime.now().isoformat(timespec='seconds')}", file=out)
    if path:
        print(f"# evidence: {path}", file=out)

    ok = True
    for name, payload, expected in cases:
        got = classify(payload)
        status = "OK" if got == expected else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"[{status}] {name:18s} -> {got!r}", file=out)

    print(f"\nresult: {'PASS (8/8)' if ok else 'FAIL'}", file=out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
