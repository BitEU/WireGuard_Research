"""Train a flow-feature classifier and produce report-ready artifacts.

Inputs: one or more CSV files emitted by flow_features.py, each tagged with
a `label` column. Labels are mapped to a binary classification:

    positive class (1): wg-direct, wg-udp2raw  (any WireGuard variant)
    negative class (0): everything else

Outputs (under /media/sf_Git/evidence/<ts>_classifier_*):
    - features.csv         all flows, one per row, with derived columns
    - metrics.txt          accuracy, precision, recall, F1, ROC AUC
    - confusion.png        2x2 matrix
    - roc.png              ROC curve
    - feature_importance.png  permutation importance from RF
    - per_feature.txt      class means/stdevs of each feature

Run:
    python3 train_classifier.py \
        evidence/*wg-direct*.csv evidence/*wg-udp2raw*.csv \
        evidence/*background*.csv
"""
import argparse
import csv
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_auc_score, roc_curve,
)
from sklearn.inspection import permutation_importance


WG_LABELS = {"wg-direct", "wg-udp2raw"}

FEATURES = [
    "bulk_fraction",
    "ack60_fraction",
    "len_entropy",
    "dominant_size_fraction",
    "top3_size_fraction",
    "ack_to_data_ratio",
    "n_unique_sizes",
    "rate_pps",
]
TWO_FEATURE_SET = ["bulk_fraction", "ack60_fraction"]


def load(csv_paths):
    frames = []
    for p in csv_paths:
        if not os.path.exists(p):
            print(f"warning: {p} missing, skipping", file=sys.stderr)
            continue
        frames.append(pd.read_csv(p))
    if not frames:
        sys.exit("error: no input CSVs found")
    df = pd.concat(frames, ignore_index=True)
    df["is_wg"] = df["label"].isin(WG_LABELS).astype(int)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+", help="feature CSVs from flow_features.py")
    ap.add_argument("--out-dir", default="/media/sf_Git/evidence")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(args.out_dir, f"{ts}_classifier")

    df = load(args.csvs)
    print(f"loaded {len(df)} flows total")
    print(df["label"].value_counts())
    print(f"  positive (WG): {df['is_wg'].sum()}  negative: {(df['is_wg']==0).sum()}")

    if df["is_wg"].sum() < 5 or (df["is_wg"]==0).sum() < 5:
        sys.exit("error: need at least 5 flows in each class to do CV")

    df.to_csv(f"{base}_features.csv", index=False)

    use_two = os.environ.get("TWO_FEATURE", "0") == "1"
    feats_full = [f for f in FEATURES if f in df.columns]
    feats_min = [f for f in TWO_FEATURE_SET if f in df.columns]
    feats = feats_min if use_two else feats_full
    X = df[feats].fillna(0.0).values
    y = df["is_wg"].values

    n_pos = int(y.sum())
    n_neg = int(len(y) - n_pos)
    n_splits = min(5, n_pos, n_neg)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=0)
    rf = RandomForestClassifier(n_estimators=200, random_state=0, class_weight="balanced")
    lr = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=0)

    metrics_lines = []
    metrics_lines.append(f"# classifier evaluation, {ts}")
    metrics_lines.append(f"# flows: {len(df)} ({n_pos} WG, {n_neg} non-WG)")
    metrics_lines.append(f"# features used: {', '.join(feats)}")
    metrics_lines.append(f"# CV: {n_splits}-fold stratified\n")

    for name, clf in [("RandomForest", rf), ("LogisticRegression", lr)]:
        try:
            y_pred = cross_val_predict(clf, X, y, cv=skf, method="predict")
            y_proba = cross_val_predict(clf, X, y, cv=skf, method="predict_proba")[:, 1]
        except ValueError as e:
            metrics_lines.append(f"=== {name} === FAILED: {e}")
            continue

        acc = accuracy_score(y, y_pred)
        prec = precision_score(y, y_pred, zero_division=0)
        rec = recall_score(y, y_pred, zero_division=0)
        f1 = f1_score(y, y_pred, zero_division=0)
        try:
            auc = roc_auc_score(y, y_proba)
        except ValueError:
            auc = float("nan")
        cm = confusion_matrix(y, y_pred)

        metrics_lines.append(f"=== {name} ===")
        metrics_lines.append(f"  accuracy:  {acc:.4f}")
        metrics_lines.append(f"  precision: {prec:.4f}")
        metrics_lines.append(f"  recall:    {rec:.4f}")
        metrics_lines.append(f"  f1:        {f1:.4f}")
        metrics_lines.append(f"  roc_auc:   {auc:.4f}")
        metrics_lines.append(f"  confusion (rows=true, cols=pred):")
        metrics_lines.append(f"            pred=non-WG  pred=WG")
        metrics_lines.append(f"  true=non-WG   {cm[0,0]:6d}    {cm[0,1]:6d}")
        metrics_lines.append(f"  true=WG       {cm[1,0]:6d}    {cm[1,1]:6d}\n")

        if name == "RandomForest":
            fig, ax = plt.subplots(figsize=(4.0, 3.5))
            im = ax.imshow(cm, cmap="Blues")
            ax.set_xticks([0, 1]); ax.set_xticklabels(["non-WG", "WG"])
            ax.set_yticks([0, 1]); ax.set_yticklabels(["non-WG", "WG"])
            for i in range(2):
                for j in range(2):
                    ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                            color="white" if cm[i, j] > cm.max()/2 else "black", fontsize=14)
            ax.set_xlabel("predicted"); ax.set_ylabel("true")
            ax.set_title(f"Random Forest, n={len(df)}")
            fig.colorbar(im, ax=ax)
            fig.tight_layout()
            fig.savefig(f"{base}_confusion.png", dpi=140)
            plt.close(fig)

            fig, ax = plt.subplots(figsize=(4.5, 3.5))
            fpr, tpr, _ = roc_curve(y, y_proba)
            ax.plot(fpr, tpr, label=f"RF (AUC={auc:.3f})")
            ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
            ax.set_xlabel("False positive rate"); ax.set_ylabel("True positive rate")
            ax.set_title("ROC: WireGuard vs background")
            ax.legend(loc="lower right")
            fig.tight_layout()
            fig.savefig(f"{base}_roc.png", dpi=140)
            plt.close(fig)

            rf.fit(X, y)
            r = permutation_importance(rf, X, y, n_repeats=20, random_state=0, n_jobs=-1)
            order = np.argsort(r.importances_mean)[::-1]
            fig, ax = plt.subplots(figsize=(5.0, max(2.5, 0.35 * len(feats))))
            ax.barh(range(len(feats)), r.importances_mean[order],
                    xerr=r.importances_std[order])
            ax.set_yticks(range(len(feats)))
            ax.set_yticklabels([feats[i] for i in order])
            ax.invert_yaxis()
            ax.set_xlabel("Permutation importance (mean accuracy drop)")
            ax.set_title("Per-feature importance (Random Forest)")
            fig.tight_layout()
            fig.savefig(f"{base}_feature_importance.png", dpi=140)
            plt.close(fig)

    metrics_lines.append("=== per-feature class means ===")
    for f in feats:
        wg = df[df["is_wg"] == 1][f]
        bg = df[df["is_wg"] == 0][f]
        metrics_lines.append(
            f"  {f:25s}  WG: {wg.mean():.3f}±{wg.std():.3f}   "
            f"non-WG: {bg.mean():.3f}±{bg.std():.3f}"
        )

    text = "\n".join(metrics_lines)
    with open(f"{base}_metrics.txt", "w") as f:
        f.write(text + "\n")
    print()
    print(text)
    print()
    print(f"# artifacts written to {base}_*")


if __name__ == "__main__":
    main()
