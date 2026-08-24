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
]


def _epoch_h(ts: datetime) -> float:
    return ts.timestamp() / 3600.0


def build_features(txns: list[dict[str, Any]]) -> pd.DataFrame:
    """Compute the feature matrix for a stream of arena transactions.
    Order matters: velocity windows are causal (only look backwards)."""
    if not txns:
        return pd.DataFrame(columns=FEATURE_NAMES)

    df = pd.DataFrame(txns)
    df["_ts"] = pd.to_datetime(df["timestamp"], utc=True)
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
            amt_ratio_vals.append(float(row.amount) / max(float(np.median(hist)), 1e-6))
        else:
            amt_ratio_vals.append(1.0)
        med.append(float(row.amount))

    out["user_cnt_1h"] = user_cnt
    out["user_sum_1h"] = user_sum
    out["user_merchants_1h"] = user_merchants
    out["device_cnt_1h"] = device_cnt

    # ---- graph features: shared-device users, merchant fan-out, pair repeats
    device_users: dict[str, set[str]] = {}
    merchant_users: dict[str, set[str]] = {}
    pair_counts: dict[tuple[str, str], int] = {}
    dev_users_col, merch_users_col, pair_col = [], [], []
    for row in df.itertuples(index=False):
        du = device_users.setdefault(row.device_id, set())
        du.add(row.user_id)
        dev_users_col.append(len(du))
        mu = merchant_users.setdefault(row.merchant_id, set())
        mu.add(row.user_id)
        merch_users_col.append(len(mu))
        k = (row.user_id, row.merchant_id)
        pair_counts[k] = pair_counts.get(k, 0) + 1
        pair_col.append(pair_counts[k])
    out["device_users"] = dev_users_col
    out["merchant_users"] = merch_users_col
    out["user_merchant_repeats"] = pair_col

    # amount ratio (computed in the user loop above)
    out["amt_vs_user_median"] = amt_ratio_vals[: len(out)]

    return out[FEATURE_NAMES].astype(float)
