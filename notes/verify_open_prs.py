"""Check open PRs in udp2raw to verify the 'no TCP-conformance changes queued' claim."""
import json
import urllib.request

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "udp2raw-pr-audit"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main():
    prs = fetch("https://api.github.com/repos/wangyu-/udp2raw/pulls?state=open&per_page=100")
    print(f"open PRs: {len(prs)}\n")
    for p in prs:
        title = p['title'][:90]
        date = p['updated_at']
        print(f"  {date}  #{p['number']:4d}  {title}")


if __name__ == "__main__":
    main()
