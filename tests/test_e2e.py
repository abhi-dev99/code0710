"""
E2E Test Suite — the whole product, no LLM required (deterministic).

Run: python tests/test_e2e.py
Exit 0 = all green.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ("attacks", "config", "defense", "arena"):
    sp = str(ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

passed = failed = 0


def check(name: str, fn) -> None:
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        failed += 1
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")


# ---------------------------------------------------------------- 1. profiles
def t_profiles():
    from rail_profiles import PROFILES, get_profile
    assert len(PROFILES) == 4
    assert get_profile("card_intl").sca_step_up
    assert not get_profile("upi_in").chargebacks
    assert get_profile(None).key == "upi_in"


# ---------------------------------------------------------------- 2. weaver
def t_weaver():
    from rail_profiles import get_profile
    from redagent.core.transaction_weaver import validate_plan, weave_attack_plan
    p = get_profile("eu_psd2")
    bad = {"vector": "x", "channel": "carrier_pigeon"}
    assert validate_plan(bad, p)  # errors non-empty
    plan = {
        "vector": "card_testing", "channel": "card_not_present",
        "merchant_categories": ["Digital Goods"],
        "structuring": [{"amount": 1.0, "count": 30}, {"amount": 9.0, "count": 20}],
        "inter_arrival_s": {"distribution": "exponential", "min": 3, "max": 45},
        "entity_cardinality": {"users": 12, "devices": 4, "merchants": 2},
        "window_h": 5,
    }
    out = weave_attack_plan(plan, profile="eu_psd2", seed=42)
    assert out["ok"] and len(out["txns"]) >= 40
    # determinism: same seed -> same txns
    out2 = weave_attack_plan(plan, profile="eu_psd2", seed=42)
    assert [t["txn_id"] for t in out["txns"]] == [t["txn_id"] for t in out2["txns"]]
    assert all(t["is_attack"] and t["rail_profile"] == "eu_psd2" for t in out["txns"])


# ---------------------------------------------------------------- 3. features
def t_features():
    from features.arena_features import FEATURE_NAMES, build_features
    from redagent.core.transaction_weaver import generate_benign, weave_attack_plan
    from loop import real_anchor
    am, hw = real_anchor()
    ben = generate_benign(200, profile="card_intl", seed=1, amount_pool=am, hour_weights=hw)
    atk = weave_attack_plan({
        "vector": "v", "channel": "card_not_present", "merchant_categories": ["Digital Goods"],
        "structuring": [{"amount": 2.0, "count": 25}],
        "inter_arrival_s": {"distribution": "uniform", "min": 5, "max": 30},
        "entity_cardinality": {"users": 5, "devices": 2, "merchants": 1}, "window_h": 2,
    }, profile="card_intl", seed=2)["txns"]
    X = build_features(ben + atk)
    assert X.shape == (len(ben) + len(atk), len(FEATURE_NAMES))
    assert not X.isna().any().any() and not np.isinf(X.to_numpy()).any()


import numpy as np  # noqa: E402


# ---------------------------------------------------------------- 4. arena round
def t_arena_round():
    from redagent.core.strategy_memory import StrategyMemory
    from loop import run_round
    with tempfile.TemporaryDirectory() as td:
        m = StrategyMemory(Path(td) / "t.db")
        try:
            s = run_round(profile_key="card_intl", vector_ids=["A1", "B1", "C1", "D1"],
                          n_benign=1500, use_llm=False, memory=m)
            assert 0 <= s["held_out_detection_rate"] <= 1
            assert s["benign_fp_rate"] <= 0.05, f"FP too high: {s['benign_fp_rate']}"
            assert s["overall"]["f1"] >= 0.5, f"F1 too low: {s['overall']['f1']}"
            assert s["shap_why"]
            assert len(m.ledger()) == 4 and len(m.round_history()) == 1
        finally:
            m.close()  # always release the sqlite handle before tempdir cleanup


# ---------------------------------------------------------------- 5. ledger
def t_ledger_memory():
    from redagent.core.strategy_memory import StrategyMemory
    with tempfile.TemporaryDirectory() as td:
        m = StrategyMemory(Path(td) / "t.db")
        m.record_campaign(campaign_id="x", vector="v", rail_profile="us_cnp",
                          plan={}, n_txns=10, n_dropped=0, detection_rate=0.9)
        assert m.caught_plans()[0]["vector"] == "v"
        m.close()


# ---------------------------------------------------------------- 6. API
def t_api():
    from fastapi.testclient import TestClient
    from app.api import app
    c = TestClient(app)
    assert c.get("/api/health").json()["status"] == "ok"
    assert len(c.get("/api/vectors").json()["vectors"]) == 14
    assert "card_intl" in c.get("/api/profiles").json()
    r = c.post("/api/round", json={"rail_profile": "us_cnp", "n_benign": 800, "use_llm": False})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["benign_fp_rate"] <= 0.05
    d = c.post("/api/detect", json={"transactions": [{
        "amount": 1.5, "channel": "card_not_present", "merchant_category": "Digital Goods",
        "timestamp": "2026-08-25T03:00:00-04:00", "user_id": "u1"}]})
    assert d.status_code == 200, d.text
    assert "fused_score" in d.json()["results"][0]
    html = c.get("/")
    assert html.status_code == 200 and "LiveFire" in html.text


if __name__ == "__main__":
    print("E2E TEST SUITE — LiveFire end-to-end")
    check("rail profiles (4 rails, mechanics)", t_profiles)
    check("transaction weaver (valid, deterministic, provenance)", t_weaver)
    check("arena features (shape, no NaN/Inf)", t_features)
    check("arena round (cross-vector, FP<=5%, F1>=0.5, ledger)", t_arena_round)
    check("strategy memory (caught/evaded queries)", t_ledger_memory)
    check("API (health/vectors/profiles/round/detect/UI)", t_api)
    print(f"\nE2E: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
