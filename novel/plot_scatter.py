"""Two-feature scatter plot for the C2 results figure.

Loads the canonical classifier_features.csv from master_set/ and produces
a publication-ready scatter of (bulk_fraction, ack60_fraction) colored by
class. Saved as PNG and PDF for LaTeX inclusion.
"""
import argparse
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", default="../master_set/20260509-132129_classifier_features.csv",
                    nargs="?")
    ap.add_argument("--out-png", default="../latex-paper/scatter.png")
    ap.add_argument("--out-pdf", default="../latex-paper/scatter.pdf")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    bg = df[df["is_wg"] == 0]
    wg = df[df["is_wg"] == 1]

    fig, ax = plt.subplots(figsize=(3.5, 3.0), dpi=200)
    ax.scatter(bg["bulk_fraction"], bg["ack60_fraction"],
               s=6, alpha=0.35, color="#666666",
               edgecolors="none", label=f"non-VPN (n={len(bg)})")
    ax.scatter(wg["bulk_fraction"], wg["ack60_fraction"],
               s=28, alpha=0.95, color="#C9462C",
               edgecolors="white", linewidths=0.6, marker="o",
               label=f"WireGuard (n={len(wg)})")

    ax.set_xlabel("bulk_fraction\n(packets ≥ 1200 B / total)", fontsize=8)
    ax.set_ylabel("ack60_fraction\n(60-byte packets / total)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.25, linewidth=0.4)
    ax.legend(loc="upper right", fontsize=7, framealpha=0.92,
              borderpad=0.4, handletextpad=0.3)

    # Sanity: no WG flow has bulk < 0.2 in our captures, no non-VPN flow has
    # both bulk >= 0.2 AND ack60 >= 0.15. Mark a rough decision corner.
    ax.axvline(0.2, color="#102A43", linestyle=":", linewidth=0.8, alpha=0.5)
    ax.axhline(0.15, color="#102A43", linestyle=":", linewidth=0.8, alpha=0.5)

    fig.tight_layout(pad=0.3)
    os.makedirs(os.path.dirname(args.out_png), exist_ok=True)
    fig.savefig(args.out_png, dpi=300, bbox_inches="tight")
    fig.savefig(args.out_pdf, bbox_inches="tight")
    print(f"wrote: {args.out_png}")
    print(f"wrote: {args.out_pdf}")

    # Also report the empirical separation we'll cite
    in_wg_box = ((wg["bulk_fraction"] >= 0.2) & (wg["ack60_fraction"] >= 0.0)).sum()
    bg_in_wg_corner = ((bg["bulk_fraction"] >= 0.2) & (bg["ack60_fraction"] >= 0.15)).sum()
    print(f"\nWG flows with bulk_fraction >= 0.2: {in_wg_box} / {len(wg)}")
    print(f"non-VPN flows in (bulk>=0.2, ack60>=0.15) corner: {bg_in_wg_corner} / {len(bg)}")


if __name__ == "__main__":
    main()
