"""
Real-Data Backbone Training — the honesty anchor (docs/AUDIT.md rule 1).

Trains an XGBoost detector on the REAL ULB corpus (native features, no
simulator involvement) with the committed time/stratified split, and reports
honest holdout metrics. This number — NOT arena metrics — is the model's
real-world credibility. Arena metrics are reported separately and labeled.

Usage: python defense/train_real_backbone.py [--dataset ulb|ieee]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import average_precision_score, roc_auc_score
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "data" / "splits"
OUT = ROOT / "defense" / "models" / "metadata"
ARTIFACTS = ROOT / "defense" / "models" / "artifacts"
SEED = 710


def _fit_and_score(train: pd.DataFrame, test: pd.DataFrame, feats: list[str]) -> tuple[XGBClassifier, float, float]:
    Xtr, ytr = train[feats].to_numpy(), train["is_fraud"].to_numpy()
    Xte, yte = test[feats].to_numpy(), test["is_fraud"].to_numpy()
    pos = ytr.sum()
    # K1 determinism: n_jobs=1 + hist — multithreaded hist hist-building is not
    # bit-reproducible run-to-run, which is what made the breakthrough evidence
    # wobble (audit 11). Same pin as the arena XGBDetector.
    model = XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.06,
        subsample=0.85, colsample_bytree=0.85,
        scale_pos_weight=float((len(ytr) - pos) / max(pos, 1)),
        eval_metric="aucpr", random_state=SEED,
        n_jobs=1, tree_method="hist",
    )
    model.fit(Xtr, ytr)
    proba = model.predict_proba(Xte)[:, 1]
    return model, float(roc_auc_score(yte, proba)), float(average_precision_score(yte, proba))


def train_ulb() -> tuple[dict, XGBClassifier]:
    train = pd.read_parquet(SPLITS / "ulb_train.parquet")
    test = pd.read_parquet(SPLITS / "ulb_test.parquet")
    ytr = train["is_fraud"].to_numpy()

    # "Time" is seconds-since-capture-start in ULB's own 2-day collection
    # window -- a dataset artifact, not something a live authorization scorer
    # would ever have. Including it as "everything except the label" is
    # exactly the training/serving skew this project's own honesty protocol
    # (docs/AUDIT.md rule 1) exists to catch. Ablate it, report both numbers,
    # ship the deployment-representative one.
    feats_with_time = [c for c in train.columns if c not in ("is_fraud",)]
    feats_no_time = [c for c in feats_with_time if c != "Time"]

    _, roc_with_time, ap_with_time = _fit_and_score(train, test, feats_with_time)
    model, roc_auc, average_precision = _fit_and_score(train, test, feats_no_time)
    feats = feats_no_time

    metrics = {
        "dataset": "ulb_real",
        "n_train": int(len(ytr)), "n_test": int(len(test)),
        "fraud_rate_train": round(float(ytr.mean()), 6),
        "fraud_rate_test": round(float(test["is_fraud"].mean()), 6),
        "roc_auc": round(roc_auc, 4),
        "average_precision": round(average_precision, 4),
        "capture_clock_ablation": {
            "note": "Time (seconds since ULB's capture start) excluded from the "
                    "shipped model -- no live-scoring equivalent exists. Reported "
                    "for transparency, identical recipe/split/seed, only Time differs.",
            "roc_auc_with_time": round(roc_with_time, 4),
            "average_precision_with_time": round(ap_with_time, 4),
            "roc_auc_without_time": round(roc_auc, 4),
            "average_precision_without_time": round(average_precision, 4),
        },
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "features": feats,
        "artifact": "defense/models/artifacts/ulb_backbone.joblib",
        "xgb_params": {
            "n_estimators": 400, "max_depth": 6, "learning_rate": 0.06,
            "subsample": 0.85, "colsample_bytree": 0.85,
            "n_jobs": 1, "tree_method": "hist", "random_state": SEED,
        },
        "honesty_note": (
            "Native real features (Time excluded, see capture_clock_ablation), "
            "committed split, no synthetic data involved. This is the "
            "real-world credibility metric. Trained with the same determinism "
            "pin as the arena ensemble (K1); the fitted model is persisted "
            "alongside these metrics."
        ),
    }
    return metrics, model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["ulb"], default="ulb")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    if args.dataset == "ulb":
        metrics, model = train_ulb()
        out_path = OUT / "ulb_backbone_metrics.json"
        artifact_path = ARTIFACTS / "ulb_backbone.joblib"
        joblib.dump(model, artifact_path)
        print(f"[OK] model artifact saved -> {artifact_path}")
    out_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in metrics.items() if k != "features"}, indent=2))
    print(f"[OK] metrics saved -> {out_path}")


if __name__ == "__main__":
    main()
