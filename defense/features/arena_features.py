"""
Arena Feature Extractor — turns arena transactions into a feature matrix.

Three feature families (heterogeneous ensemble input):
  1. Behavioral: amount, cyclical hour, night flag, distance, channel one-hots,
     amount-vs-user-median ratio
  2. Velocity (windowed per user/device): counts, sums, distinct merchants
  3. Graph (entity graph, networkx): device shared-user count, merchant
     unique-user count, user-merchant pair repeat count

Deterministic, no LLM. Fit-free (stateless given the full stream) — features
for a campaign are computed on the campaign+context stream so velocity windows
see real history.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

FEATURE_NAMES = [
    "amount", "hour_sin", "hour_cos", "is_night", "distance_km",
    "channel_cnp", "channel_atm",
    "amt_vs_user_median",
    "user_cnt_1h", "user_sum_1h", "user_merchants_1h",
    "device_cnt_1h", "device_users",
    "merchant_users", "user_merchant_repeats",
    "memo_injection_score",
]

# heuristic prompt-injection markers for the memo/invoice text field (P2.4:
# minimum-viable Category D — the semantic tier's deterministic stand-in)
_INJECTION_PATTERNS = [
    "ignore previous", "ignore all previous", "ignore the above",
    "system:", "assistant:", "agent context", "<|", "override",
    "beneficiary", "approve invoice", "release payment", "wire to",
    "auto-approve", "supersedes prior instructions", "without user confirmation",
]


def _memo_score(text: Any) -> float:
    t = str(text or "").lower()
    if not t:
        return 0.0
    hits = sum(1 for pat in _INJECTION_PATTERNS if pat in t)
    return min(hits, 3.0) / 3.0


def _epoch_h(ts: datetime) -> float:
    return ts.timestamp() / 3600.0


def build_features(txns: list[dict[str, Any]]) -> pd.DataFrame:
    """Compute the feature matrix for a stream of arena transactions.
    Order matters: velocity windows are causal (only look backwards)."""
    if not txns:
        return pd.DataFrame(columns=FEATURE_NAMES)

    df = pd.DataFrame(txns)
    df["_ts"] = pd.to_datetime(df["timestamp"], utc=True)
    df["_orig_pos"] = np.arange(len(df))
    df = df.sort_values("_ts").reset_index(drop=True)
    df["hour_frac"] = df["_ts"].apply(lambda t: t.hour + t.minute / 60.0)
    df["epoch_h"] = df["_ts"].apply(_epoch_h)

    out = pd.DataFrame(index=df.index)
    out["amount"] = df["amount"].astype(float)
    out["hour_sin"] = np.sin(2 * np.pi * df["hour_frac"] / 24.0)
    out["hour_cos"] = np.cos(2 * np.pi * df["hour_frac"] / 24.0)
    out["is_night"] = ((df["hour_frac"] < 6) | (df["hour_frac"] >= 23)).astype(float)
    out["distance_km"] = df.get("location_distance_km", 0.0)
    out["distance_km"] = out["distance_km"].astype(float)
    out["channel_cnp"] = (df["channel"] == "card_not_present").astype(float)
    out["channel_atm"] = (df["channel"] == "atm").astype(float)

    # ---- velocity: per-user rolling 1h windows (causal)
    user_cnt, user_sum, user_merchants = [], [], []
    device_cnt = []
    amt_ratio_vals: list[float] = []
    by_user: dict[str, list[tuple[float, str, float]]] = {}
    by_device: dict[str, list[float]] = {}
    user_median: dict[str, list[float]] = {}
    for row in df.itertuples(index=False):
        eh = row.epoch_h
        u_hist = by_user.setdefault(row.user_id, [])
        u_hist[:] = [h for h in u_hist if eh - h[0] <= 1.0]
        user_cnt.append(len(u_hist))
        user_sum.append(sum(h[2] for h in u_hist))
        user_merchants.append(len({h[1] for h in u_hist}))
        u_hist.append((eh, row.merchant_id, float(row.amount)))

        d_hist = by_device.setdefault(row.device_id, [])
        d_hist[:] = [h for h in d_hist if eh - h <= 1.0]
        device_cnt.append(len(d_hist))
        d_hist.append(eh)

        med = user_median.setdefault(row.user_id, [])
        hist = med[:-1]
        if hist:
            # clipped: unbounded ratios (2.5e9 seen in audit 11/S3) saturate LR
            amt_ratio_vals.append(min(float(row.amount) / max(float(np.median(hist)), 1e-6), 50.0))
        else:
            amt_ratio_vals.append(1.0)
        med.append(float(row.amount))

    out["user_cnt_1h"] = user_cnt
    out["user_sum_1h"] = user_sum
    out["user_merchants_1h"] = user_merchants
    out["device_cnt_1h"] = device_cnt

    # ---- graph features: causal-window fan-out (stationary over time,
    # unlike cumulative counts which drift upward through a stream)
    device_events: dict[str, list[tuple[float, str]]] = {}
    merchant_events: dict[str, list[tuple[float, str]]] = {}
    pair_events: dict[tuple[str, str], list[float]] = {}
    dev_users_col, merch_users_col, pair_col = [], [], []
    for row in df.itertuples(index=False):
        eh = row.epoch_h
        de = device_events.setdefault(row.device_id, [])
        de[:] = [(t, u) for (t, u) in de if eh - t <= 1.0]
        de.append((eh, row.user_id))
        dev_users_col.append(len({u for _, u in de}))

        me = merchant_events.setdefault(row.merchant_id, [])
        me[:] = [(t, u) for (t, u) in me if eh - t <= 1.0]
        me.append((eh, row.user_id))
        merch_users_col.append(len({u for _, u in me}))

        pk = (row.user_id, row.merchant_id)
        pe = pair_events.setdefault(pk, [])
        pe[:] = [t for t in pe if eh - t <= 24.0]
        pair_col.append(len(pe))
        pe.append(eh)
    out["device_users"] = dev_users_col
    out["merchant_users"] = merch_users_col
    out["user_merchant_repeats"] = pair_col

    # amount ratio (computed in the user loop above)
    out["amt_vs_user_median"] = amt_ratio_vals[: len(out)]

    # memo/invoice text: heuristic prompt-injection score (Category D signal)
    if "memo_text" in df.columns:
        out["memo_injection_score"] = df["memo_text"].map(_memo_score)
    else:
        out["memo_injection_score"] = 0.0

    out = out[FEATURE_NAMES].astype(float)
    # return in the ORIGINAL stream order (we computed in time order so the
    # causal velocity windows see real history; callers index by stream order)
    return out.set_index(df["_orig_pos"].values).sort_index().set_axis(
        np.arange(len(out)), axis=0)
