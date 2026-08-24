"""
Feature extraction facade over the vendored ARGUS extractor.

Single source of truth: vendor/argus/backend/ml/feature_extractor.py (34 features).
This wrapper exists so our pipeline has one import path and can later add
arena-specific features WITHOUT touching training or inference parity.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

_VENDOR_ML = Path(__file__).resolve().parents[2] / "vendor" / "argus" / "backend" / "ml"
if str(_VENDOR_ML) not in sys.path:
    sys.path.insert(0, str(_VENDOR_ML))

from feature_extractor import extract_features as _argus_extract  # noqa: E402
from feature_extractor import FEATURE_NAMES, NUM_FEATURES  # noqa: E402,F401

__all__ = ["extract_features", "extract_batch", "FEATURE_NAMES", "NUM_FEATURES"]


def extract_features(
    txn: Dict[str, Any],
    user_profile: Optional[Any] = None,
    anomaly_info: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Extract exactly NUM_FEATURES (34) from one transaction dict."""
    return _argus_extract(txn, user_profile=user_profile, anomaly_info=anomaly_info)


def extract_batch(txns: list[Dict[str, Any]]) -> np.ndarray:
    """Vectorized-ish batch extraction. NOTE: still row-wise internally; used only
    for training-time featurization. The hot scoring path must use cached profiles
    and batched numpy transforms (see defense/features/hotpath.py, Phase C)."""
    return np.array([_argus_extract(t) for t in txns], dtype=np.float64)


def _selftest() -> None:
    txn = {
        "amount": 42000.0,
        "channel": "upi",
        "merchant_category": "P2P Transfer",
        "timestamp": "2026-08-24T02:15:00+05:30",
        "is_new_device": True,
        "device_age_hours": 0.5,
        "is_new_location": True,
        "location_distance_km": 812.0,
    }
    vec = extract_features(txn)
    assert vec.shape == (NUM_FEATURES,), f"expected ({NUM_FEATURES},), got {vec.shape}"
    names = dict(zip(FEATURE_NAMES, vec))
    assert names["is_new_device"] == 1 and names["is_night"] == 1
    assert names["is_cross_state"] == 1 and names["device_location_risk"] == 1.0
    print(f"[OK] extractor selftest passed: {NUM_FEATURES} features, spot-checks correct")


if __name__ == "__main__":
    _selftest()
