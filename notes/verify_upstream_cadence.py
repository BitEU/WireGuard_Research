"""Verify the claim that udp2raw upstream development cadence is low."""
import json
import urllib.request

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "udp2raw-cadence-audit"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main():
    repo = fetch("https://api.github.com/repos/wangyu-/udp2raw")
    print(f"udp2raw default branch:      {repo['default_branch']}")
    print(f"updated_at (any push/issue): {repo['updated_at']}")
    print(f"pushed_at  (last code push): {repo['pushed_at']}")
    print(f"open_issues_count:           {repo['open_issues_count']}")
    print()

    commits = fetch("https://api.github.com/repos/wangyu-/udp2raw/commits?per_page=10")
    print(f"latest 10 commits on default branch:")
    for c in commits:
        msg = c['commit']['message'].splitlines()[0][:80]
        date = c['commit']['committer']['date']
        print(f"  {date}  {msg}")
    print()

    rels = fetch("https://api.github.com/repos/wangyu-/udp2raw/releases?per_page=5")
    print(f"latest releases:")
    for r in rels:
        print(f"  {r['published_at']}  {r['tag_name']}  {r['name']}")


if __name__ == "__main__":
    main()
