"""
Blue Team Backbone — XGBoost + Logistic Regression heterogeneous ensemble.

Components:
  - XGBDetector: gradient-boosted trees (the explainable workhorse; SHAP-ready)
  - LRDetector: linear fallback / disagreement source
  - RulesDetector: deterministic velocity/amount/travel rules (auditable)
  - BlueEnsemble: weighted score fusion + disagreement→novelty flag

Evaluation protocol (honesty first):
  - Cross-vector: train on attacks from a subset of vectors, evaluate on a
    HELD-OUT vector — measures detection of never-before-seen attack types,
    which is the entire point of an adaptive-adversary arena.
  - Benign FP rate is reported separately and is the hard constraint.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

BLUE_VERSION = "blue_v1"

# Rules tier: deterministic, auditable, per-rail-tunable
RULE_VELOCITY_1H = 5        # >5 txns per user in 1h
RULE_DEVICE_VELOCITY = 8    # >8 txns per device in 1h
RULE_NIGHT_AMOUNT = 5_000.0 # night + big amount
RULE_DISTANCE = 800.0       # >800 km within the hour window


class RulesDetector:
    """Deterministic tier. Fires 0/1. Fully auditable: every hit has a rule name."""

    def __init__(self, feature_names: list[str]):
        self.names = feature_names
        self.idx = {n: i for i, n in enumerate(feature_names)}
        self.last_rule_hits: list[str] = []

    def predict(self, X: np.ndarray) -> np.ndarray:
        hits = (
            (X[:, self.idx["user_cnt_1h"]] > RULE_VELOCITY_1H)
            | (X[:, self.idx["device_cnt_1h"]] > RULE_DEVICE_VELOCITY)
            | ((X[:, self.idx["is_night"]] > 0) & (X[:, self.idx["amount"]] > RULE_NIGHT_AMOUNT))
            | (X[:, self.idx["distance_km"]] > RULE_DISTANCE)
        )
        return hits.astype(int)


class XGBDetector:
    def __init__(self, seed: int = 710):
        self.model = XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.08,
            subsample=0.9, colsample_bytree=0.9,
            scale_pos_weight=10.0,          # imbalance-robust
            eval_metric="aucpr", random_state=seed, n_jobs=4,
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> "XGBDetector":
        self.model.fit(X, y)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]


class LRDetector:
    def __init__(self, seed: int = 710):
        self.scaler = StandardScaler()
        self.model = LogisticRegression(max_iter=2000, C=0.5, random_state=seed)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LRDetector":
        self.model.fit(self.scaler.fit_transform(X), y)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(self.scaler.transform(X))[:, 1]


class BlueEnsemble:
    """Fuses ML scores with the rules tier; disagreement → novelty flag."""

    def __init__(self, feature_names: list[str], seed: int = 710):
        self.feature_names = feature_names
        self.xgb = XGBDetector(seed)
        self.lr = LRDetector(seed)
        self.rules = RulesDetector(feature_names)
        self.threshold = 0.5
        self.fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BlueEnsemble":
        self.xgb.fit(X, y)
        self.lr.fit(X, y)
        self.fitted = True
        return self

    def predict(self, X: np.ndarray) -> dict[str, Any]:
        if not self.fitted:
            raise RuntimeError("BlueEnsemble not fitted")
        s_xgb = self.xgb.score(X)
        s_lr = self.lr.score(X)
        s_rules = self.rules.predict(X).astype(float)
        fused = 0.55 * s_xgb + 0.25 * s_lr + 0.20 * s_rules
        flagged = fused >= self.threshold
        # disagreement: ML confident-fraud but rules silent, or vice versa
        disagree = ((s_xgb >= 0.7) & (s_rules == 0)) | ((s_xgb < 0.3) & (s_rules == 1))
        return {
            "flagged": flagged,
            "fused_score": fused,
            "score_xgb": s_xgb,
            "score_lr": s_lr,
            "score_rules": s_rules,
            "novelty_flag": disagree & ~flagged,   # suspicious-but-under-threshold
            "novelty_count": int(disagree.sum()),
        }

    def confusion(self, X: np.ndarray, y: np.ndarray, threshold: float | None = None) -> dict[str, float]:
        res = self.predict(X)
        thr = self.threshold if threshold is None else threshold
        pred = (res["fused_score"] >= thr).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4),
            "fp_rate_on_benign": round(fp / max(tn + fp, 1), 6),
            "detection_rate": round(rec, 4),
        }
