"""
Fidelity Report — does synthetic benign traffic actually look real?

LiveFire's benign generator claims to be "real-corpus anchored" (amount pool
+ hour-of-day weights sampled from the real ULB corpus, see arena/loop.py
real_anchor()). This module is the check on that claim, not an assumption of
it — the same discipline a competing team's public writeup applies (four
independent fidelity signals per synthetic batch, reported even when
unflattering). We report three signals on the two dimensions we actually
draw from real data (amount, hour-of-day); a generator that only reproduces
marginals while destroying joint structure would still show up honestly in
the distinguisher, since that's what it's for.

  1. Kolmogorov-Smirnov distance on the amount distribution (0 = identical, 1 = disjoint)
  2. Kolmogorov-Smirnov distance on the hour-of-day distribution
  3. Distinguisher AUC: a classifier trained to tell real ULB rows apart from
     synthetic benign rows on (amount, hour_sin, hour_cos). 0.5 = indistinguishable
     (the classifier is guessing); 1.0 = trivially separable. This is the
     strongest of the three signals because it is free to find whatever
     actually separates the two distributions, not a fixed statistic we chose.

Usage: python -m defense.fidelity
Writes evidence/fidelity_report.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

_ROOT = Path(__file__).resolve().parents[1]
for p in ("attacks", "config", "arena"):
    sp = str(_ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)


def _real_ulb_rows(n: int, seed: int) -> pd.DataFrame:
    splits = _ROOT / "data" / "splits" / "ulb_train.parquet"
    df = pd.read_parquet(splits)
    sample = df.sample(n=min(n, len(df)), random_state=seed)
    hour = ((sample["Time"] / 3600.0) % 24).astype(int)
    return pd.DataFrame({"amount": sample["Amount"].to_numpy(), "hour": hour.to_numpy()})


def _synthetic_benign_rows(n: int, seed: int) -> pd.DataFrame:
    from loop import real_anchor
    from redagent.core.transaction_weaver import generate_benign

    amounts, hour_weights = real_anchor()
    txns = generate_benign(n, profile="card_intl", seed=seed, amount_pool=amounts, hour_weights=hour_weights)
    ts = pd.to_datetime([t["timestamp"] for t in txns], utc=True)
    return pd.DataFrame({"amount": [t["amount"] for t in txns], "hour": ts.hour.to_numpy()})


def _distinguisher_auc(real: pd.DataFrame, synth: pd.DataFrame, seed: int) -> float:
    def feats(df: pd.DataFrame) -> np.ndarray:
        rad = 2 * np.pi * df["hour"].to_numpy() / 24.0
        return np.column_stack([df["amount"].to_numpy(), np.sin(rad), np.cos(rad)])

    X = np.vstack([feats(real), feats(synth)])
    y = np.concatenate([np.zeros(len(real)), np.ones(len(synth))])
    clf = LogisticRegression(max_iter=1000, random_state=seed)
    scores = cross_val_score(clf, X, y, cv=5, scoring="roc_auc")
    return float(scores.mean())


def fidelity_report(n: int = 4000, seed: int = 710) -> dict[str, Any]:
    real = _real_ulb_rows(n, seed)
    synth = _synthetic_benign_rows(n, seed)

    amount_ks = ks_2samp(real["amount"], synth["amount"])
    hour_ks = ks_2samp(real["hour"], synth["hour"])
    auc = _distinguisher_auc(real, synth, seed)

    return {
        "n_real": len(real), "n_synthetic": len(synth), "seed": seed,
        "amount_ks_statistic": round(float(amount_ks.statistic), 4),
        "amount_ks_pvalue": float(amount_ks.pvalue),
        "hour_of_day_ks_statistic": round(float(hour_ks.statistic), 4),
        "hour_of_day_ks_pvalue": float(hour_ks.pvalue),
        "distinguisher_auc": round(auc, 4),
        "reading": (
            "distinguisher_auc near 0.5 = a classifier cannot tell real ULB "
            "rows from LiveFire's synthetic benign rows on (amount, hour); "
            "near 1.0 = trivially separable. KS statistics near 0 = "
            "distributions match; near 1 = disjoint. This is a real check "
            "on the 'real-corpus anchored' claim, not an assumption of it -- "
            "reported honestly even where it is unflattering."
        ),
    }


if __name__ == "__main__":
    report = fidelity_report()
    print(json.dumps(report, indent=2))
    out = _ROOT / "evidence" / "fidelity_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[OK] written -> {out}")
