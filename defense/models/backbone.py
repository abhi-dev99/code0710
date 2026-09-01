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

from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

BLUE_VERSION = "blue_v2"

# Fusion weights (P2.3: four tiers; IF at low weight as the zero-day catcher).
# calibrate() MUST use the identical weights — the v1 bug was calibrating the
# threshold against 0.55/0.25 while predict() fused 0.55/0.25/0.20.
W_XGB, W_LR, W_RULES, W_IF = 0.50, 0.20, 0.20, 0.10

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
        # account-reference binding: settlement payee != mandate payee is
        # fraud by construction (Category D), no probabilistic judgment needed
        if "beneficiary_mismatch" in self.idx:
            hits = hits | (X[:, self.idx["beneficiary_mismatch"]] > 0)
        return hits.astype(int)


class IFDetector:
    """Unsupervised novelty tier (P2.3): Isolation Forest fitted on BENIGN
    traffic only. Catches families the supervised tiers have no training
    signal for — the zero-day story. Score normalized to [0,1] against the
    benign anomaly distribution."""

    def __init__(self, seed: int = 710):
        self.model = IsolationForest(n_estimators=200, contamination=0.02,
                                     random_state=seed)
        self._mid = 0.0
        self._scale = 1.0
        self.fitted = False

    def fit(self, X: np.ndarray) -> "IFDetector":
        self.model.fit(X)
        s = -self.model.score_samples(X)          # higher = more anomalous
        self._mid = float(np.quantile(s, 0.50))
        self._scale = max(float(np.quantile(s, 0.999)) - self._mid, 1e-9)
        self.fitted = True
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        s = -self.model.score_samples(X)
        return np.clip((s - self._mid) / self._scale, 0.0, 1.0)


class XGBDetector:
    def __init__(self, seed: int = 710):
        self.model = XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.08,
            subsample=0.9, colsample_bytree=0.9,
            scale_pos_weight=10.0,          # imbalance-robust
            eval_metric="aucpr", random_state=seed,
            n_jobs=1,                       # K1: multithreaded hist is nondeterministic
            tree_method="hist",             # deterministic histogram builder
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
        self.version = BLUE_VERSION
        self.xgb = XGBDetector(seed)
        self.lr = LRDetector(seed)
        self.rules = RulesDetector(feature_names)
        self.iforest = IFDetector(seed)
        self.threshold = 0.5
        self.fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BlueEnsemble":
        self.xgb.fit(X, y)
        self.lr.fit(X, y)
        benign = X[y == 0]
        if len(benign) >= 50:
            self.iforest.fit(benign)   # unsupervised tier learns benign only
        self.fitted = True
        return self

    def calibrate(self, X_benign: np.ndarray, target_fp: float = 0.005) -> float:
        """Set threshold on a HELD-OUT benign slice so the FP rate hits the
        target. Uses the IDENTICAL fusion as predict() (v1 calibrated against
        the wrong weights) and a near-zero floor — the old max(0.5,…) floor
        made tight FP regimes unreachable by construction (P2.1).
        Default operating point 0.5% FP (was 2%); the strict literature
        regime recall@FPR≤0.001 is reported separately by confusion()."""
        s = self._fuse(X_benign)
        self.threshold = float(max(0.05, np.quantile(s, 1.0 - target_fp)))
        return self.threshold

    def _fuse(self, X: np.ndarray) -> np.ndarray:
        s = W_XGB * self.xgb.score(X) + W_LR * self.lr.score(X) + W_RULES * self.rules.predict(X)
        if self.iforest.fitted:
            s = s + W_IF * self.iforest.score(X)
        return s

    def save(self, path: str | Path) -> Path:
        """Persist the fitted ensemble (joblib) so /api/detect survives restarts."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @classmethod
    def load(cls, path: str | Path) -> "BlueEnsemble":
        """Reload a fitted ensemble from disk; rejects corrupt/foreign artifacts."""
        ens = joblib.load(path)
        if not isinstance(ens, cls) or not getattr(ens, "fitted", False):
            raise ValueError(f"{path} is not a fitted BlueEnsemble artifact")
        return ens

    def predict(self, X: np.ndarray) -> dict[str, Any]:
        if not self.fitted:
            raise RuntimeError("BlueEnsemble not fitted")
        s_xgb = self.xgb.score(X)
        s_lr = self.lr.score(X)
        s_rules = self.rules.predict(X).astype(float)
        s_if = self.iforest.score(X) if self.iforest.fitted else np.zeros(len(X))
        fused = self._fuse(X)   # single fusion path (audit 12: no inline re-implementation)
        flagged = fused >= self.threshold
        # disagreement: ML confident-fraud but rules silent, or vice versa
        disagree = ((s_xgb >= 0.7) & (s_rules == 0)) | ((s_xgb < 0.3) & (s_rules == 1))
        return {
            "flagged": flagged,
            "fused_score": fused,
            "score_xgb": s_xgb,
            "score_lr": s_lr,
            "score_rules": s_rules,
            "score_iforest": s_if,
            "novelty_flag": disagree & ~flagged,   # suspicious-but-under-threshold
            "novelty_count": int(disagree.sum()),
        }

    def confusion(self, X: np.ndarray, y: np.ndarray, threshold: float | None = None) -> dict[str, float]:
        res = self.predict(X)
        thr = self.threshold if threshold is None else threshold
        fused = res["fused_score"]
        pred = (fused >= thr).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        rec_at_fpr, realized_at_fpr = self._recall_at_fpr(X[y == 0], X[y == 1], 0.001)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4),
            "fp_rate_on_benign": round(fp / max(tn + fp, 1), 6),
            "detection_rate": round(rec, 4),
            "pr_auc": round(float(average_precision_score(y, fused)), 4) if len(set(y)) > 1 else 0.0,
            "recall_at_fpr_0.001": rec_at_fpr,
            "recall_at_fpr_0.001_realized_fpr": realized_at_fpr,   # audit 11: report realized, not nominal
        }

    def _recall_at_fpr(self, X_ben: np.ndarray, X_atk: np.ndarray,
                       fpr_target: float = 0.001) -> tuple[float, float]:
        """Literature-protocol metric: best detection achievable when the
        benign FP budget is fpr_target — REALIZED, not nominal (audit 11:
        ceil() let k=ceil(0.001*n) through, i.e. a 0.00133 realized budget
        against a 0.001 nominal one). floor() now guarantees
        realized_fpr <= fpr_target; the realized rate is returned alongside
        so callers report both."""
        if len(X_ben) == 0 or len(X_atk) == 0:
            return 0.0, 0.0
        s_ben = self._fuse(X_ben)
        s_atk = self._fuse(X_atk)
        k = int(np.floor(fpr_target * len(s_ben)))   # benign rows allowed through
        s_sorted = np.sort(s_ben)
        if k <= 0:
            thr = float(np.nextafter(s_sorted[-1], np.inf))   # strict: zero benign may fire
        else:
            thr = float(s_sorted[-k])
        recall = round(float((s_atk >= thr).mean()), 4)
        realized = round(float((s_ben >= thr).mean()), 6)
        return recall, realized
