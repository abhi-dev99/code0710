"""
Download REAL anchor datasets.

Requires a free Kaggle API token (kaggle.com/settings -> Create New Token),
which kagglehub picks up automatically.

Datasets (REAL transactions only â€” see docs/data_provenance.md):
1. ULB creditcardfraud   â€” 284,807 real European card txns, 492 labeled frauds
2. IEEE-CIS Fraud Detection (Vesta) â€” ~590k real e-commerce transactions

Usage:
    python data/download_datasets.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
MANIFEST = RAW_DIR / "MANIFEST.json"


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import kagglehub
    except ImportError:
        print("[ERR] kagglehub missing. Run: pip install -r requirements.txt")
        return 1

    entries: dict[str, dict] = {}

    print("[1/2] ULB creditcardfraud ...")
    ulb_dir = Path(kagglehub.dataset_download("mlg-ulb/creditcardfraud"))
    src = next(ulb_dir.rglob("creditcard.csv"))
    dst = RAW_DIR / "ulb_creditcard.csv"
    shutil.copyfile(src, dst)
    entries[str(dst.relative_to(RAW_DIR))] = {
        "sha256": _sha256(dst), "bytes": dst.stat().st_size,
        "source": "kaggle:mlg-ulb/creditcardfraud", "real_data": True,
    }
    print(f"      saved -> {dst.name} ({entries[str(dst.relative_to(RAW_DIR))]['bytes']:,} B)")

    print("[2/2] IEEE-CIS Fraud Detection (train_transaction subset) ...")
    # NOTE: this fails unless someone on the team accepted the competition
    # rules once at kaggle.com/competitions/ieee-fraud-detection/rules
    # while logged in with the same account whose API token kagglehub uses.
    ieee_dir = Path(kagglehub.competition_download("ieee-fraud-detection"))
    # Full set is ~500MB compressed; keep train_transaction.csv as the anchor.
    src = next(ieee_dir.rglob("train_transaction.csv"))
    dst = RAW_DIR / "ieee_cis_train_transaction.csv"
    shutil.copyfile(src, dst)
    entries[str(dst.relative_to(RAW_DIR))] = {
        "sha256": _sha256(dst), "bytes": dst.stat().st_size,
        "source": "kaggle:ieee-fraud-detection (Vesta)", "real_data": True,
    }
    print(f"      saved -> {dst.name} ({entries[str(dst.relative_to(RAW_DIR))]['bytes']:,} B)")

    MANIFEST.write_text(json.dumps({"datasets": entries}, indent=2))
    print(f"[OK] manifest written: {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
