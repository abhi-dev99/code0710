"""
Build + LOCK evaluation splits from real corpora.

Outputs data/splits/:
    split_manifest.json   — file hashes, seed, stratification stats
    ulb_train.parquet / ulb_test.parquet
    ieee_train.parquet / ieee_test.parquet

Rules enforced here (the "data honesty protocol"):
- Splits are stratified by fraud label, seeded ONCE, and hashed.
- Test sets are NEVER used for threshold tuning or model selection.
- Attack campaigns (synthetic, from red agents) join ONLY the test side later,
  plus >=1 held-out attack family the defender never sees during training.

Usage:
    python data/build_splits.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
SPLITS_DIR = Path(__file__).resolve().parents[1] / "data" / "splits"
SEED = 710  # team number; fixed forever — changing it invalidates all results
TEST_FRACTION = 0.2


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _split_stratified(df: pd.DataFrame, label: str, name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    from sklearn.model_selection import train_test_split

    train, test = train_test_split(
        df, test_size=TEST_FRACTION, random_state=SEED, stratify=df[label]
    )
    train.to_parquet(SPLITS_DIR / f"{name}_train.parquet", index=False)
    test.to_parquet(SPLITS_DIR / f"{name}_test.parquet", index=False)
    stats = {
        "total": len(df),
        "train": len(train),
        "test": len(test),
        "fraud_rate_total": round(float(df[label].mean()), 6),
        "fraud_rate_train": round(float(train[label].mean()), 6),
        "fraud_rate_test": round(float(test[label].mean()), 6),
    }
    print(f"  [{name}] {stats}")
    return train, test


def _split_temporal(df: pd.DataFrame, time_col: str, label: str, name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Time-ordered split: earliest (1-test_fraction) = train, latest = test.

    Methodologically stronger than random splits for transaction data —
    mimics real deployment (train on the past, score the future) and
    prevents leakage-by-time. Label stratification is checked, not enforced.
    """
    df = df.sort_values(time_col).reset_index(drop=True)
    cutoff = int(len(df) * (1 - TEST_FRACTION))
    train, test = df.iloc[:cutoff], df.iloc[cutoff:]
    train.to_parquet(SPLITS_DIR / f"{name}_train.parquet", index=False)
    test.to_parquet(SPLITS_DIR / f"{name}_test.parquet", index=False)
    stats = {
        "total": len(df),
        "train": len(train),
        "test": len(test),
        "fraud_rate_total": round(float(df[label].mean()), 6),
        "fraud_rate_train": round(float(train[label].mean()), 6),
        "fraud_rate_test": round(float(test[label].mean()), 6),
        f"{time_col}_train_max": str(train[time_col].max()),
        f"{time_col}_test_min": str(test[time_col].min()),
    }
    print(f"  [{name}] {stats}")
    return train, test


def main() -> int:
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {"seed": SEED, "test_fraction": TEST_FRACTION,
                      "ulb_split": "stratified_random (2-day window; no time axis)",
                      "ieee_split": "temporal (train=past, test=latest 20%)",
                      "files": {}}

    ulb_path = RAW_DIR / "ulb_creditcard.csv"
    if ulb_path.exists():
        print("[1/2] ULB creditcard ...")
        df = pd.read_csv(ulb_path)
        _split_stratified(df.rename(columns={"Class": "is_fraud"}), "is_fraud", "ulb")
        manifest["files"]["ulb_source"] = {"sha256": _sha256(ulb_path), "rows": len(df)}
    else:
        print(f"[WARN] missing {ulb_path} — run download_datasets.py first")

    ieee_path = RAW_DIR / "ieee_cis_train_transaction.csv"
    if ieee_path.exists():
        print("[2/2] IEEE-CIS (Vesta) ...")
        df = pd.read_csv(ieee_path)
        # TransactionDT: seconds from a reference point, monotonic per Vesta docs
        _split_temporal(df, "TransactionDT", "isFraud", "ieee")
        manifest["files"]["ieee_source"] = {"sha256": _sha256(ieee_path), "rows": len(df)}
    else:
        print(f"[WARN] missing {ieee_path} — run download_datasets.py first")

    out = SPLITS_DIR / "split_manifest.json"
    out.write_text(json.dumps(manifest, indent=2))
    print(f"[OK] splits locked -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
