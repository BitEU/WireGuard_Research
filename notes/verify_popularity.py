"""Verify GitHub popularity stats we cite in the paper.

Pulls release downloads + star counts directly from the GitHub API
so the numbers in the paper match a re-runnable artifact, not a screenshot.
"""
import json
import sys
import urllib.request
import urllib.error

REPOS = [
    ("wangyu-",  "udp2raw",                  "udp2raw (faketcp shim)"),
    ("wangyu-",  "udp2raw-multiplatform",    "udp2raw-multiplatform fork"),
    ("amnezia-vpn", "amneziawg-go",          "AmneziaWG (Go userspace)"),
    ("amnezia-vpn", "amneziawg-linux-kernel-module", "AmneziaWG (kernel module)"),
    ("amnezia-vpn", "amnezia-client",        "Amnezia desktop client"),
    ("database64128", "swgp-go",                "swgp-go"),
    ("erebe",      "wstunnel",               "wstunnel"),
    ("cbeuw",      "Cloak",                  "Cloak"),
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "udp2raw-popularity-audit"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}", "_url": url}


def all_releases(owner, repo):
    """Walk all release pages until empty."""
    out, page = [], 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=100&page={page}"
        data = fetch(url)
        if isinstance(data, dict) and "_error" in data:
            return data
        if not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
        page += 1
    return out


def main():
    print(f"{'repo':45s}  {'stars':>7s}  {'releases':>9s}  {'downloads':>10s}")
    print("-" * 80)
    for owner, repo, label in REPOS:
        meta = fetch(f"https://api.github.com/repos/{owner}/{repo}")
        if "_error" in meta:
            print(f"{label:45s}  {'?':>7s}  {'?':>9s}  {'?':>10s}   ({meta['_error']})")
            continue
        stars = meta.get("stargazers_count", "?")
        rels = all_releases(owner, repo)
        if isinstance(rels, dict) and "_error" in rels:
            print(f"{label:45s}  {stars:>7d}  {'?':>9s}  {'?':>10s}   ({rels['_error']})")
            continue
        n_rels = len(rels)
        downloads = sum(a.get("download_count", 0) for r in rels for a in r.get("assets", []))
        print(f"{label:45s}  {stars:>7d}  {n_rels:>9d}  {downloads:>10d}")
    print()
    print("Sources:")
    print("  https://api.github.com/repos/<owner>/<repo>            (star count)")
    print("  https://api.github.com/repos/<owner>/<repo>/releases   (per-asset downloads)")


if __name__ == "__main__":
    main()
