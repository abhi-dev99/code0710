"""
LiveFire API — serves the arena as a product.

Endpoints:
  GET  /                  -> web UI (static/index.html)
  GET  /api/health        -> liveness + component status
  GET  /api/vectors       -> attack taxonomy
  GET  /api/profiles      -> rail profiles
  GET  /api/real-metrics  -> honest ULB real-data backbone metrics
  POST /api/round         -> run one arena round (red->weave->blue->explain->ledger)
  POST /api/multi-rail    -> same vectors across ALL rail profiles
  GET  /api/ledger        -> Robustness Ledger (campaigns)
  GET  /api/rounds        -> round history
  POST /api/detect        -> score transactions with the current ensemble

Run: uvicorn app.api:app --reload --port 8000
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parents[1]
for p in ("attacks", "config", "defense", "arena"):
    sp = str(_ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from arena.loop import VECTORS, run_multi_rail, run_round  # noqa: E402
from rail_profiles import PROFILES  # noqa: E402
from redagent.core.strategy_memory import StrategyMemory  # noqa: E402

app = FastAPI(title="LiveFire — Adversarial Co-Evolution Arena", version="1.0.0")
memory = StrategyMemory()
_state_lock = threading.Lock()
_state: dict[str, Any] = {"last_round": None, "rounds_run": 0, "ensemble": None}


class RoundRequest(BaseModel):
    rail_profile: str = Field(default="card_intl")
    vector_ids: list[str] | None = None
    n_benign: int = Field(default=2400, ge=400, le=20000)
    seed: int = Field(default=710)
    use_llm: bool = Field(default=False, description="true = ox-alpha plans (needs quota); false = deterministic templates")


class DetectRequest(BaseModel):
    transactions: list[dict[str, Any]]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_ROOT / "app" / "static" / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "rounds_run": _state["rounds_run"],
        "vectors": len(VECTORS),
        "rail_profiles": sorted(PROFILES),
        "ledger_campaigns": len(memory.ledger(limit=10000)),
    }


@app.get("/api/vectors")
def vectors() -> dict:
    return {"vectors": list(VECTORS.values())}


@app.get("/api/profiles")
def profiles() -> dict:
    return {
        key: {
            "display_name": p.display_name,
            "currency": p.currency,
            "timezone": p.timezone_name,
            "channels": {n: {"max": c.max_amount, "categories": list(c.categories)}
                          for n, c in p.channels.items()},
            "sca_step_up": p.sca_step_up,
            "chargebacks": p.chargebacks,
            "notes": p.notes,
        }
        for key, p in PROFILES.items()
    }


@app.get("/api/real-metrics")
def real_metrics() -> dict:
    f = _ROOT / "defense" / "models" / "metadata" / "ulb_backbone_metrics.json"
    if not f.exists():
        raise HTTPException(404, "real-data metrics not trained yet — run defense/train_real_backbone.py")
    return json.loads(f.read_text(encoding="utf-8"))


@app.post("/api/round")
def post_round(req: RoundRequest) -> dict:
    if req.rail_profile not in PROFILES:
        raise HTTPException(400, f"unknown rail profile: {req.rail_profile}")
    if req.vector_ids:
        bad = [v for v in req.vector_ids if v not in VECTORS]
        if bad:
            raise HTTPException(400, f"unknown vector ids: {bad}")
    try:
        summary = run_round(
            profile_key=req.rail_profile, vector_ids=req.vector_ids,
            n_benign=req.n_benign, seed=req.seed, use_llm=req.use_llm, memory=memory,
        )
    except Exception as e:  # surface failures to the UI, never 500-silently
        raise HTTPException(500, f"round failed: {type(e).__name__}: {e}") from e
    with _state_lock:
        _state["ensemble"] = summary.pop("_ensemble", None)
        _state["last_round"] = summary
        _state["rounds_run"] += 1
    return summary


@app.post("/api/multi-rail")
def post_multi_rail(req: RoundRequest) -> dict:
    try:
        out = run_multi_rail(vector_ids=req.vector_ids, n_benign=min(req.n_benign, 1500),
                             seed=req.seed, use_llm=False)
    except Exception as e:
        raise HTTPException(500, f"multi-rail failed: {type(e).__name__}: {e}") from e
    with _state_lock:
        _state["rounds_run"] += 1
    return out


@app.get("/api/ledger")
def ledger(limit: int = 100) -> dict:
    rows = memory.ledger(limit=limit)
    for r in rows:
        r["plan"] = json.loads(r.pop("plan_json", "{}"))
    return {"campaigns": rows, "vector_stats": memory.vector_stats()}


@app.get("/api/rounds")
def rounds(limit: int = 50) -> dict:
    return {"rounds": memory.round_history(limit=limit)}


@app.post("/api/detect")
def detect(req: DetectRequest) -> dict:
    """Score transactions with the ensemble fitted in the last round.
    Cold-start caveat: velocity/graph windows only see this batch."""
    ens = _state.get("ensemble")
    if ens is None:
        raise HTTPException(409, "no ensemble ready — POST /api/round first")
    from features.arena_features import build_features

    txns = []
    for i, t in enumerate(req.transactions):
        t = dict(t)
        t.setdefault("txn_id", f"api_{i}")
        t.setdefault("user_id", t.get("user_id") or f"api_user_{i}")
        t.setdefault("device_id", "api_dev")
        t.setdefault("merchant_id", t.get("merchant_id") or "api_merchant")
        t.setdefault("location_distance_km", 0.0)
        txns.append(t)
    try:
        X = build_features(txns).to_numpy()
    except Exception as e:
        raise HTTPException(400, f"feature extraction failed: {type(e).__name__}: {e}") from e
    res = ens.predict(X)
    return {
        "blue_version": ens.version,
        "threshold": round(ens.threshold, 4),
        "results": [
            {
                "txn_id": txns[i].get("txn_id", str(i)),
                "flagged": bool(res["flagged"][i]),
                "fused_score": round(float(res["fused_score"][i]), 4),
                "score_xgb": round(float(res["score_xgb"][i]), 4),
                "score_lr": round(float(res["score_lr"][i]), 4),
                "rules_hit": bool(res["score_rules"][i] > 0),
                "novelty_flag": bool(res["novelty_flag"][i]),
            }
            for i in range(len(txns))
        ],
    }
