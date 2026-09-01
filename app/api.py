"""
LiveFire API — serves the arena as a product.

Endpoints:
  GET  /                  -> web UI (static/index.html)
  GET  /api/health        -> liveness + component status
  GET  /api/vectors       -> attack taxonomy
  GET  /api/profiles      -> rail profiles
  GET  /api/real-metrics  -> honest ULB real-data backbone metrics
  POST /api/round         -> run one arena round (red->weave->blue->explain->ledger)
  POST /api/tournament    -> RED TOURNAMENT (squad-based population red-teaming)
  POST /api/multi-rail    -> same vectors across ALL rail profiles
  GET  /api/ledger        -> Robustness Ledger (campaigns)
  GET  /api/ledger/export -> full ledger as CSV download
  GET  /api/rounds        -> round history
  POST /api/detect        -> score transactions with the current ensemble
  GET  /api/llm-config    -> current red-team provider/model (no raw key)
  POST /api/llm-config    -> swap provider/key/model at runtime, live-tested

Run: uvicorn app.api:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import sys
import threading
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

RailProfileKey = Literal["card_intl", "eu_psd2", "us_cnp", "upi_in"]
MAX_SEED = 2_147_483_647  # fits int32; safe across numpy default_rng and random.Random
MAX_VECTOR_IDS = 14  # taxonomy size; a request can't sensibly name more distinct vectors
MAX_TOURNAMENT_WORKLOAD = 500_000  # squad_size * generations * n_benign per anonymous call

_ROOT = Path(__file__).resolve().parents[1]
for p in ("attacks", "config", "defense", "arena"):
    sp = str(_ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from env_bootstrap import load_env  # noqa: E402

load_env()  # P0.1: .env at every entry point (external-audit/08 P0.1)

from arena.loop import VECTORS, run_multi_rail, run_round, run_tournament  # noqa: E402
from rail_profiles import PROFILES  # noqa: E402
from redagent.core.strategy_memory import StrategyMemory  # noqa: E402

app = FastAPI(title="LiveFire — Adversarial Co-Evolution Arena", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
memory = StrategyMemory()
_state_lock = threading.Lock()
_state: dict[str, Any] = {"last_round": None, "rounds_run": 0, "ensemble": None}

# ---- ensemble persistence: the fitted blue team survives server restarts ----
ENSEMBLE_ARTIFACT = _ROOT / "defense" / "models" / "artifacts" / "arena_ensemble.joblib"


def _persist_ensemble(ens: Any) -> bool:
    """Best-effort disk persistence; detection keeps working in-memory if it fails."""
    try:
        ens.save(ENSEMBLE_ARTIFACT)
        return True
    except Exception:
        return False


def _load_persisted_ensemble() -> bool:
    if not ENSEMBLE_ARTIFACT.exists():
        return False
    try:
        from models.backbone import BlueEnsemble

        _state["ensemble"] = BlueEnsemble.load(ENSEMBLE_ARTIFACT)
        return True
    except Exception:
        return False


ENSEMBLE_RELOADED = _load_persisted_ensemble()

# ---- lazy red-team LLM client: the dashboard's use_llm checkbox must actually
# reach the planner (audit finding: use_llm was silently a no-op via the API) ----
_llm_client: Any = None
_llm_tried = False


def get_llm() -> Any:
    global _llm_client, _llm_tried
    if _llm_client is None and not _llm_tried:
        _llm_tried = True
        try:
            from redagent.core.llm_client import LLMClient

            _llm_client = LLMClient.from_env()
            print("[api] red-team LLM client configured")
        except Exception as e:
            print(f"[api] LLM client unavailable ({type(e).__name__}: {e}) — template mode only")
    return _llm_client


class LLMConfigRequest(BaseModel):
    """Bring-your-own-provider: swap the red-team model at runtime, no .env
    edit or restart needed. Provider-agnostic -- any OpenAI-compatible chat
    completions endpoint works, OpenRouter is just the default because one
    key covers every model below without separate provider accounts."""
    base_url: str = Field(default="https://openrouter.ai/api/v1", min_length=8, max_length=300)
    api_key: str = Field(min_length=8, max_length=300)
    model_strategy: str = Field(default="google/gemini-3-flash-preview", min_length=1, max_length=200)
    model_bulk: str | None = Field(default=None, max_length=200)
    reasoning_effort: str = Field(default="max", pattern="^(max|high|medium|low|minimal)$")


class RoundRequest(BaseModel):
    rail_profile: RailProfileKey = Field(default="card_intl")
    vector_ids: list[str] | None = Field(default=None, max_length=MAX_VECTOR_IDS)
    n_benign: int = Field(default=2400, ge=400, le=20000)
    seed: int = Field(default=710, ge=0, le=MAX_SEED)
    use_llm: bool = Field(default=False, description="true = LLM-generated plans (needs a configured provider, see /api/llm-config); false = deterministic templates")


class DetectRequest(BaseModel):
    transactions: list[dict[str, Any]] = Field(max_length=5000)


class TournamentRequest(BaseModel):
    rail_profile: RailProfileKey = Field(default="card_intl")
    vector_ids: list[str] | None = Field(default=None, max_length=MAX_VECTOR_IDS)
    n_benign: int = Field(default=2400, ge=400, le=20000)
    seed: int = Field(default=710, ge=0, le=MAX_SEED)
    use_llm: bool = Field(default=False)
    squad_size: int = Field(default=10, ge=2, le=32, description="red candidates per vector per generation")
    generations: int = Field(default=2, ge=1, le=5)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_ROOT / "app" / "static" / "index.html")


_TERMINAL_DIR = _ROOT / "app" / "frontend" / "dist"
if _TERMINAL_DIR.exists():
    app.mount("/terminal", StaticFiles(directory=str(_TERMINAL_DIR), html=True), name="terminal")

_STATIC_DIR = _ROOT / "app" / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "rounds_run": _state["rounds_run"],
        "vectors": len(VECTORS),
        "rail_profiles": sorted(PROFILES),
        "ledger_campaigns": len(memory.ledger(limit=10000)),
        "ensemble_ready": _state["ensemble"] is not None,
        "ensemble_artifact": str(ENSEMBLE_ARTIFACT.relative_to(_ROOT))
        if ENSEMBLE_ARTIFACT.exists() else None,
        "llm_configured": get_llm() is not None,
        "llm_info": get_llm().describe() if get_llm() is not None else None,
        "detect_latency_ms": _latency_summary(),
    }


@app.get("/api/llm-config")
def get_llm_config() -> dict:
    llm = get_llm()
    if llm is None:
        return {"configured": False}
    return {"configured": True, **llm.describe()}


@app.post("/api/llm-config")
def post_llm_config(req: LLMConfigRequest) -> dict:
    """Swap the red-team provider/key/model at runtime. Validated with a real
    (cheap, non-JSON) call before it's accepted, so a bad key or a dead model
    slug fails loudly here instead of silently degrading every round after
    this to template mode."""
    global _llm_client, _llm_tried
    from redagent.core.llm_client import LLMClient, LLMError

    models = {"strategy": req.model_strategy, "bulk": req.model_bulk or req.model_strategy}
    try:
        candidate = LLMClient(
            base_url=req.base_url.rstrip("/"), api_key=req.api_key, models=models,
            reasoning_effort=req.reasoning_effort,
        )
    except LLMError as e:
        raise HTTPException(400, str(e)) from e
    try:
        asyncio.run(candidate.complete("strategy", system="Reply with exactly: OK", user="ping"))
    except Exception as e:
        raise HTTPException(400, f"provider rejected a live test call: {type(e).__name__}: {e}") from e
    with _state_lock:
        _llm_client = candidate
        _llm_tried = True
    return {"ok": True, **candidate.describe()}


def _latency_summary() -> dict | None:
    """p50/p99 scoring latency over the rolling /api/detect window (P2.2)."""
    lat = _state.get("latency_ms") or []
    if not lat:
        return None
    xs = sorted(lat)
    return {
        "n_calls": len(xs),
        "p50_ms": round(xs[len(xs) // 2], 2),
        "p99_ms": round(xs[min(len(xs) - 1, int(len(xs) * 0.99))], 2),
        "throughput_per_sec": round(1000.0 / max(xs[len(xs) // 2], 0.01), 0),
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
            llm=get_llm() if req.use_llm else None,
        )
    except Exception as e:  # surface failures to the UI, never 500-silently
        raise HTTPException(500, f"round failed: {type(e).__name__}: {e}") from e
    ens = None
    with _state_lock:
        ens = summary.pop("_ensemble", None)
        _state["ensemble"] = ens
        _state["last_round"] = summary
        _state["rounds_run"] += 1
    if ens is not None:
        _persist_ensemble(ens)
    return summary


@app.post("/api/multi-rail")
def post_multi_rail(req: RoundRequest) -> dict:
    try:
        out = run_multi_rail(vector_ids=req.vector_ids, n_benign=min(req.n_benign, 1500),
                             seed=req.seed, use_llm=req.use_llm)
    except Exception as e:
        raise HTTPException(500, f"multi-rail failed: {type(e).__name__}: {e}") from e
    with _state_lock:
        _state["rounds_run"] += 1
    return out


@app.post("/api/tournament")
def post_tournament(req: TournamentRequest) -> dict:
    """RED TOURNAMENT: squad_size red candidates per vector per generation,
    tournament-selected for maximum evasion, mutating across generations via
    SHAP feedback. The 10x red-vs-blue capacity mode."""
    if req.rail_profile not in PROFILES:
        raise HTTPException(400, f"unknown rail profile: {req.rail_profile}")
    if req.vector_ids:
        bad = [v for v in req.vector_ids if v not in VECTORS]
        if bad:
            raise HTTPException(400, f"unknown vector ids: {bad}")
    workload = req.squad_size * req.generations * req.n_benign
    if workload > MAX_TOURNAMENT_WORKLOAD:
        raise HTTPException(
            400,
            f"squad_size*generations*n_benign={workload} exceeds the per-call cap "
            f"({MAX_TOURNAMENT_WORKLOAD}); lower one of squad_size/generations/n_benign",
        )
    try:
        summary = run_tournament(
            profile_key=req.rail_profile, vector_ids=req.vector_ids,
            n_benign=req.n_benign, seed=req.seed, use_llm=req.use_llm,
            squad_size=req.squad_size, generations=req.generations, memory=memory,
            llm=get_llm() if req.use_llm else None,
        )
    except Exception as e:
        raise HTTPException(500, f"tournament failed: {type(e).__name__}: {e}") from e
    ens = None
    with _state_lock:
        ens = summary.pop("_ensemble", None)
        _state["ensemble"] = ens
        _state["last_round"] = {"mode": "tournament", "rail_profile": summary["rail_profile"],
                                "escalation": summary["escalation"]}
        _state["rounds_run"] += 1
    if ens is not None:
        _persist_ensemble(ens)
    return summary


@app.get("/api/ledger")
def ledger(limit: int = 100) -> dict:
    rows = memory.ledger(limit=limit)
    for r in rows:
        r["plan"] = json.loads(r.pop("plan_json", "{}"))
    return {"campaigns": rows, "vector_stats": memory.vector_stats()}


@app.get("/api/ledger/export")
def ledger_export() -> Response:
    """Full Robustness Ledger as CSV — the evidence artifact judges can take away."""
    rows = memory.ledger(limit=1000000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ts", "vector", "rail_profile", "n_txns", "n_dropped",
                "detection_rate", "evasion_notes", "plan_json"])
    for r in rows:
        w.writerow([r["ts"], r["vector"], r["rail_profile"], r["n_txns"],
                    r["n_dropped"], r["detection_rate"], r["evasion_notes"] or "",
                    r["plan_json"]])
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=livefire_robustness_ledger.csv"},
    )


@app.get("/api/rounds")
def rounds(limit: int = 50) -> dict:
    return {"rounds": memory.round_history(limit=limit)}


@app.post("/api/detect")
def detect(req: DetectRequest) -> dict:
    """Score transactions with the ensemble from the last round (auto-reloaded
    from the persisted artifact after a server restart).
    Cold-start caveat: velocity/graph windows only see this batch."""
    import math
    import time

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
        amt = t.get("amount")
        try:
            if amt is None or not math.isfinite(float(amt)):
                raise ValueError
        except (TypeError, ValueError):
            raise HTTPException(400, f"transaction {t.get('txn_id', i)}: "
                                     f"'amount' must be a finite number (got {amt!r})")
        txns.append(t)
    t0 = time.perf_counter()
    try:
        X = build_features(txns).to_numpy()
    except Exception as e:
        raise HTTPException(400, f"feature extraction failed: {type(e).__name__}: {e}") from e
    t1 = time.perf_counter()
    try:
        res = ens.predict(X)
    except Exception as e:
        raise HTTPException(400, f"scoring failed: {type(e).__name__}: {e}") from e
    t2 = time.perf_counter()
    feat_ms, score_ms = round((t1 - t0) * 1000, 2), round((t2 - t1) * 1000, 2)
    with _state_lock:
        lat = _state.setdefault("latency_ms", [])
        lat.append(score_ms)
        del lat[:-500]  # rolling window
    return {
        "blue_version": ens.version,
        "threshold": round(ens.threshold, 4),
        "latency_ms": {"features": feat_ms, "scoring": score_ms,
                       "total": round(feat_ms + score_ms, 2), "n_txns": len(txns)},
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
