"""
BREAKTHROUGH HUNT (P1.1 + P1.3) — manufactures the thesis artifact.

Phase 1: grid-search LOW-SIGNATURE attack plans (sub-threshold amounts, long
         windows that starve 1h velocity, per-user devices, high merchant
         entropy) against the CURRENT blue ensemble until detection genuinely
         dips.
Phase 2: per-tier forensics on the breakthrough family — does the Isolation
         Forest novelty tier catch what XGBoost misses? (P2.3 evidence)
Phase 3: blue retrains WITH the breakthrough family -> recovery measured on a
         FRESH weave (new seed) of the same family.
Phase 4: bootstrap CIs (2000 resamples) on both deltas.

Run: .venv\\Scripts\\python.exe tests\\breakthrough_hunt.py
Output: tests/_breakthrough_report.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for p in ("attacks", "config", "defense", "arena"):
    sp = str(Path(__file__).resolve().parents[1] / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from features.arena_features import FEATURE_NAMES, build_features  # noqa: E402
from models.backbone import BlueEnsemble  # noqa: E402
from rail_profiles import get_profile  # noqa: E402
from redagent.core.transaction_weaver import weave_attack_plan  # noqa: E402
from loop import generate_benign, real_anchor, run_round, template_plan  # noqa: E402
from redagent.core.strategy_memory import StrategyMemory  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
P = get_profile("card_intl")
SEED = 710


def det_rate(ens, benign, txns):
    """Detection rate of txns appended after a benign context stream."""
    stream = benign + txns
    X = build_features(stream).to_numpy()[len(benign):]
    if len(X) == 0:
        return 0.0, None
    res = ens.predict(X)
    return float(res["flagged"].mean()), res


def bootstrap_ci(flags_a: np.ndarray, flags_b: np.ndarray, n_boot: int = 2000):
    """95% CI for mean(A) - mean(B) via resampling both."""
    rng = np.random.default_rng(SEED)
    deltas = []
    for _ in range(n_boot):
        a = flags_a[rng.integers(0, len(flags_a), len(flags_a))]
        b = flags_b[rng.integers(0, len(flags_b), len(flags_b))]
        deltas.append(a.mean() - b.mean())
    return float(np.quantile(deltas, 0.025)), float(np.quantile(deltas, 0.975))


def main() -> None:
    report: dict = {"seed": SEED, "rail": "card_intl"}

    # ---------------- Phase 0: baseline blue (fresh round, template mode) ----------------
    mem = StrategyMemory(ROOT / "arena_ledger.db")
    base = run_round(profile_key="card_intl", n_benign=2400, seed=SEED,
                     use_llm=False, memory=mem)
    ens = base["_ensemble"]
    amounts, hour_w = real_anchor()
    benign_train = generate_benign(1200, profile=P, seed=SEED, amount_pool=amounts, hour_weights=hour_w)
    benign_calib = generate_benign(600, profile=P, seed=SEED + 555, amount_pool=amounts, hour_weights=hour_w)
    benign_eval = generate_benign(600, profile=P, seed=SEED + 999, amount_pool=amounts, hour_weights=hour_w)

    # baseline difficulty reference: a standard template campaign
    t_ref = weave_attack_plan(template_plan("A1", "card_intl"), profile=P, seed=SEED + 42)
    base_det, _ = det_rate(ens, benign_eval, t_ref["txns"])
    report["baseline_template_det"] = round(base_det, 4)
    print(f"[0] baseline ensemble vs standard template campaign: det={base_det:.3f}")

    # ---------------- Phase 1: low-signature grid search ----------------
    ch = P.channels["card_not_present"]
    results = []
    i = 0
    for amt in (3.0, 8.0, 15.0, 30.0):
        for count in (30, 60, 100):
            for window in (48, 96):
                for users in (40, 80):
                    i += 1
                    plan = {
                        "vector": "low_signature_dispersion", "channel": "card_not_present",
                        "merchant_categories": list(ch.categories)[:3],
                        "structuring": [{"amount": min(amt, ch.max_amount), "count": count}],
                        "inter_arrival_s": {"distribution": "uniform", "min": 1800, "max": 14000},
                        "entity_cardinality": {"users": users, "devices": users,
                                               "merchants": max(25, users // 2)},
                        "window_h": window, "amount_jitter_pct": 0.30,
                    }
                    out = weave_attack_plan(plan, profile=P, seed=SEED + 1000 + i)
                    if not out["ok"] or not out["txns"]:
                        continue
                    d, _ = det_rate(ens, benign_eval, out["txns"])
                    results.append({"grid": {"amount": amt, "count": count, "window": window,
                                             "users": users},
                                    "det": round(d, 4), "plan": plan, "seed": SEED + 1000 + i})
    results.sort(key=lambda r: r["det"])
    best = results[0]
    report["grid_size"] = len(results)
    report["breakthrough"] = {"det": best["det"], "grid": best["grid"],
                              "plan": best["plan"]}
    print(f"[1] grid of {len(results)} low-signature plans -> best det={best['det']:.3f} "
          f"(grid={best['grid']})")

    # breakthrough family flags vs baseline-template flags (same ensemble)
    bt = weave_attack_plan(best["plan"], profile=P, seed=best["seed"])
    _, res_bt = det_rate(ens, benign_eval, bt["txns"])
    _, res_ref = det_rate(ens, benign_eval, t_ref["txns"])
    lo, hi = bootstrap_ci(res_ref["flagged"].astype(float), res_bt["flagged"].astype(float))
    report["breakthrough"]["delta_vs_template"] = {
        "delta": round(base_det - best["det"], 4), "ci95": [round(lo, 4), round(hi, 4)]}
    print(f"    dip vs template: {base_det - best['det']:+.3f}  95% CI [{lo:.3f}, {hi:.3f}]"
          f"  {'SIGNIFICANT' if lo > 0 else 'not significant'}")

    # ---------------- Phase 2: per-tier forensics on the breakthrough ----------------
    stream = benign_eval + bt["txns"]
    X = build_features(stream).to_numpy()[len(benign_eval):]
    s_xgb = ens.xgb.score(X)
    s_if = ens.iforest.score(X) if ens.iforest.fitted else np.zeros(len(X))
    xgb_caught = s_xgb >= 0.7
    if_top = float((s_if >= 0.8).mean())
    if_catches_missed = float((s_if[~xgb_caught] >= 0.8).mean()) if (~xgb_caught).any() else 0.0
    report["forensics"] = {
        "xgb_confident_fraud_rate": round(float(xgb_caught.mean()), 4),
        "iforest_high_anomaly_rate": round(if_top, 4),
        "iforest_anomaly_rate_on_xgb_misses": round(if_catches_missed, 4),
        "fused_threshold": round(ens.threshold, 4),
    }
    print(f"[2] forensics: xgb-confident={xgb_caught.mean():.3f}  iforest-high={if_top:.3f}  "
          f"iforest-catches-xgb-misses={if_catches_missed:.3f}")

    # ---------------- Phase 3: blue retrains -> recovery on FRESH weave ----------------
    ref2 = weave_attack_plan(template_plan("A3", "card_intl"), profile=P, seed=SEED + 77)
    X_train = build_features(benign_train + bt["txns"] + ref2["txns"]).to_numpy()
    y_train = np.array([0] * len(benign_train) + [1] * len(bt["txns"]) + [1] * len(ref2["txns"]))
    ens2 = BlueEnsemble(FEATURE_NAMES).fit(X_train, y_train)
    ens2.calibrate(build_features(benign_calib).to_numpy(), target_fp=0.005)

    fresh = weave_attack_plan(best["plan"], profile=P, seed=best["seed"] + 4242)  # never seen
    rec_det, res_fresh = det_rate(ens2, benign_eval, fresh["txns"])
    rec_fp = float((ens2.predict(build_features(benign_eval).to_numpy())["flagged"]).mean())
    lo2, hi2 = bootstrap_ci(res_fresh["flagged"].astype(float), res_bt["flagged"].astype(float))
    report["recovery"] = {
        "fresh_weave_seed": best["seed"] + 4242,
        "det_after_retrain": round(rec_det, 4), "fp_after_retrain": round(rec_fp, 4),
        "delta_vs_breakthrough": {"delta": round(rec_det - best["det"], 4),
                                  "ci95": [round(lo2, 4), round(hi2, 4)]}}
    print(f"[3] recovery: fresh-weave det after retrain={rec_det:.3f} (FP={rec_fp:.4f})  "
          f"delta={rec_det - best['det']:+.3f}  95% CI [{lo2:.3f}, {hi2:.3f}]")

    report["chart"] = {
        "labels": ["template (baseline blue)", "breakthrough (baseline blue)",
                   "breakthrough (retrained blue)"],
        "values": [round(base_det, 4), round(best["det"], 4), round(rec_det, 4)],
    }
    out_path = ROOT / "tests" / "_breakthrough_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n[done] report -> {out_path}")
    print("THE CHART:", json.dumps(report["chart"]))


if __name__ == "__main__":
    main()
