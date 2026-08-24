"""
ARGUS Unified Feature Extractor v4.0
=====================================
Single source of truth for feature extraction.
Used by BOTH training pipeline AND runtime inference.

34 features grouped into 7 categories:
  Core Transaction (4), Channel & Category (6), Temporal (6),
  Device & Location (6), Behavioral (6), Regulatory (4), Merchant (2)
"""
import math
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

try:
    from .dataset_config import (
        CHANNEL_RISK, CATEGORY_RISK, CHANNELS, REGULATORY_LIMITS,
    )
except ImportError:
    from dataset_config import (
        CHANNEL_RISK, CATEGORY_RISK, CHANNELS, REGULATORY_LIMITS,
    )

# Ordered channel encoding
CHANNEL_ENCODING = {'upi': 0, 'pos': 1, 'card_online': 2, 'netbanking': 3, 'wallet': 4, 'atm': 5}

# All 35+ categories → ordinal
_ALL_CATEGORIES = sorted(set(
    cat for ch in CHANNELS.values() for cat in ch['categories']
))
CATEGORY_ENCODING = {cat: i for i, cat in enumerate(_ALL_CATEGORIES)}

# Channel max limits for ratio calculation
CHANNEL_MAX = {
    'upi': 100000, 'pos': 500000, 'card_online': 200000,
    'netbanking': 1000000, 'wallet': 10000, 'atm': 25000,
}

# Valid channel-category pairs for channel_category_valid feature
VALID_PAIRS = {ch: set(cfg['categories']) for ch, cfg in CHANNELS.items()}

# Feature names in exact order (34 features)
FEATURE_NAMES = [
    # Core Transaction (4)
    'amount', 'amount_log', 'balance_delta_ratio', 'amount_to_channel_limit_ratio',
    # Channel & Category (6)
    'channel_encoded', 'channel_risk_score', 'category_risk_score',
    'category_encoded', 'is_high_risk_category', 'channel_category_valid',
    # Temporal (6)
    'hour', 'is_night', 'is_weekend', 'is_salary_period',
    'is_month_end', 'hour_sin',
    # Device & Location (6)
    'is_new_device', 'device_age_hours', 'is_new_location',
    'location_distance_km', 'is_cross_state', 'device_location_risk',
    # Behavioral (6)
    'amount_zscore', 'amount_deviation_ratio', 'txn_velocity',
    'amount_velocity', 'daily_cumulative_ratio', 'is_unusual_channel',
    # Regulatory (4)
    'exceeds_channel_limit', 'near_str_threshold',
    'is_round_structuring_amount', 'cooling_period_risk',
    # Merchant (2)
    'merchant_risk_score', 'is_new_beneficiary',
]

NUM_FEATURES = len(FEATURE_NAMES)  # 34

HIGH_RISK_CATEGORIES = {
    'Jewellery', 'Electronics', 'Electronics Online',
    'Large Transfer', 'Cash Withdrawal', 'P2P Transfer',
}

STRUCTURING_ROUND_AMOUNTS = {10000, 25000, 50000, 100000, 200000, 500000, 1000000}


def extract_features(
    txn: Dict[str, Any],
    user_profile: Optional[Any] = None,
    anomaly_info: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """
    Extract exactly 34 features from a transaction.

    Args:
        txn: Transaction dict with standard ARGUS fields
        user_profile: Optional UserBehaviorProfile for behavioral features
        anomaly_info: Optional anomaly indicators from user_profile.add_transaction()

    Returns:
        np.ndarray of shape (34,)
    """
    amount = float(txn.get('amount', 0))
    channel = str(txn.get('channel', 'upi')).lower()
    category = str(txn.get('merchant_category', 'Local Shop'))

    # Parse timestamp
    timestamp = txn.get('timestamp', datetime.now())
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except Exception:
            timestamp = datetime.now()

    hour = timestamp.hour
    day = timestamp.day
    weekday = timestamp.weekday()

    # ===== CORE TRANSACTION (4) =====
    amount_log = math.log1p(amount)
    balance_delta_ratio = 0.0  # Not available in live txn, default 0
    ch_max = CHANNEL_MAX.get(channel, 100000)
    amount_to_limit = amount / ch_max if ch_max > 0 else 0

    # ===== CHANNEL & CATEGORY (6) =====
    ch_enc = CHANNEL_ENCODING.get(channel, 0)
    ch_risk = CHANNEL_RISK.get(channel, 0.15)
    cat_risk = CATEGORY_RISK.get(category, 0.10)
    cat_enc = CATEGORY_ENCODING.get(category, 0)
    is_high_risk = 1 if category in HIGH_RISK_CATEGORIES else 0
    ch_cat_valid = 1 if category in VALID_PAIRS.get(channel, set()) else 0

    # ===== TEMPORAL (6) =====
    is_night = 1 if (hour >= 23 or hour < 5) else 0
    is_weekend = 1 if weekday >= 5 else 0
    is_salary = 1 if 1 <= day <= 7 else 0
    is_month_end = 1 if day >= 25 else 0
    hour_sin = math.sin(2 * math.pi * hour / 24)

    # ===== DEVICE & LOCATION (6) =====
    is_new_dev = 1 if txn.get('is_new_device', False) else 0
    dev_age = float(txn.get('device_age_hours', 1000))
    is_new_loc = 1 if txn.get('is_new_location', False) else 0
    loc_dist = float(txn.get('location_distance_km', 0))
    # Cross-state: infer from is_new_location + distance > 200km
    is_cross_state = 1 if (is_new_loc and loc_dist > 200) else 0
    # Composite risk: new device + new location + high amount
    dev_loc_risk = 0.0
    if is_new_dev and is_new_loc and amount > 10000:
        dev_loc_risk = 1.0
    elif is_new_dev and amount > 25000:
        dev_loc_risk = 0.7
    elif is_new_loc and amount > 50000:
        dev_loc_risk = 0.5

    # ===== BEHAVIORAL (6) =====
    if anomaly_info:
        amt_zscore = float(anomaly_info.get('amount_zscore', 0))
        amt_dev_ratio = float(anomaly_info.get('amount_deviation_ratio', 1))
    elif user_profile and hasattr(user_profile, 'avg_amount') and user_profile.txn_count > 3:
        std = user_profile.std_amount if user_profile.std_amount > 0 else 1
        amt_zscore = (amount - user_profile.avg_amount) / std
        amt_dev_ratio = amount / user_profile.avg_amount if user_profile.avg_amount > 0 else 1
    else:
        amt_zscore = 0.0
        amt_dev_ratio = 1.0

    txn_vel = 0.1
    amt_vel = 0.1
    daily_cum_ratio = 1.0
    is_unusual_ch = 0

    if user_profile and hasattr(user_profile, 'txn_velocity'):
        txn_vel = float(getattr(user_profile, 'txn_velocity', 0.1))
        amt_vel = float(getattr(user_profile, 'amount_velocity', 0.1))

    if anomaly_info:
        daily_cum_ratio = float(anomaly_info.get('daily_total_deviation', 1.0))

    # ===== REGULATORY (4) =====
    exceeds_limit = 0
    if channel == 'upi' and amount > REGULATORY_LIMITS['upi_single']:
        exceeds_limit = 1
    elif channel == 'atm' and amount > REGULATORY_LIMITS['atm_single']:
        exceeds_limit = 1
    elif channel == 'wallet' and amount > REGULATORY_LIMITS['wallet_single']:
        exceeds_limit = 1

    near_str = 1 if (REGULATORY_LIMITS['str_threshold'] * 0.9 <= amount <= REGULATORY_LIMITS['str_threshold'] * 1.05) else 0
    is_round_struct = 1 if amount in STRUCTURING_ROUND_AMOUNTS else 0

    # Cooling period: new account (<1 day effective) + high value
    acct_age = float(txn.get('account_age_days', 999))
    cooling_risk = 0.0
    if acct_age <= 1 and amount > REGULATORY_LIMITS['upi_new_user_24h']:
        cooling_risk = 1.0
    elif acct_age <= 7 and amount > 25000:
        cooling_risk = 0.5
    elif acct_age <= 30 and amount > 50000:
        cooling_risk = 0.3

    # ===== MERCHANT (2) =====
    merch_risk = float(txn.get('merchant_risk_score', 0.15))
    is_new_benef = 1 if txn.get('is_new_beneficiary', False) else 0

    # ===== ASSEMBLE =====
    features = np.array([
        amount, amount_log, balance_delta_ratio, amount_to_limit,
        ch_enc, ch_risk, cat_risk, cat_enc, is_high_risk, ch_cat_valid,
        hour, is_night, is_weekend, is_salary, is_month_end, hour_sin,
        is_new_dev, dev_age, is_new_loc, loc_dist, is_cross_state, dev_loc_risk,
        amt_zscore, amt_dev_ratio, txn_vel, amt_vel, daily_cum_ratio, is_unusual_ch,
        exceeds_limit, near_str, is_round_struct, cooling_risk,
        merch_risk, is_new_benef,
    ], dtype=np.float64)

    assert features.shape == (NUM_FEATURES,), f"Expected {NUM_FEATURES} features, got {features.shape[0]}"
    return features


def extract_features_batch(transactions: list, user_profiles=None) -> np.ndarray:
    """Extract features for a batch of transactions. Returns (N, 34) array."""
    results = []
    for txn in transactions:
        results.append(extract_features(txn))
    return np.array(results)
