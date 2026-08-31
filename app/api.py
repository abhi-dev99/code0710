"""
LiveFire API — serves the arena as a product.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parents[1]
for p in ("attacks", "config", "defense", "arena"):
    sp = str(_ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from env_bootstrap import load_env

load_env()

from arena.loop import VECTORS, run_multi_rail, run_round, run_tournament
from rail_profiles import PROFILES
from redagent.core.strategy_memory import StrategyMemory

app = FastAPI(title="LiveFire — Adversarial Co-Evolution Arena", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

memory = StrategyMemory()
_state_lock = threading.Lock()
_state: dict[str, Any] = {"last_round": None, "rounds_run": 0, "ensemble": None}

ENSEMBLE_ARTIFACT = _ROOT / "defense" / "models" / "artifacts" / "arena_ensemble.joblib"

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

def _persist_ensemble(ens: Any) -> bool:
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

_llm_client: Any = None
_llm_tried = False

def get_llm() -> Any:
    global _llm_client, _llm_tried
    if _llm_client is None and not _llm_tried:
        _llm_tried = True
        try:
            from redagent.core.llm_client import LLMClient
            _llm_client = LLMClient.from_env()
        except Exception as e:
            pass
    return _llm_client

class RoundRequest(BaseModel):
    rail_profile: str = Field(default="card_intl")
    vector_ids: list[str] | None = None
    n_benign: int = Field(default=2400, ge=400, le=20000)
    seed: int = Field(default=710)
    use_llm: bool = Field(default=False)

class DetectRequest(BaseModel):
    transactions: list[dict[str, Any]]

class TournamentRequest(BaseModel):
    rail_profile: str = Field(default="card_intl")
    vector_ids: list[str] | None = None
    n_benign: int = Field(default=2400, ge=400, le=20000)
    seed: int = Field(default=710)
    use_llm: bool = Field(default=False)
    squad_size: int = Field(default=10, ge=2, le=32)
    generations: int = Field(default=2, ge=1, le=5)

@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "rounds_run": _state["rounds_run"],
        "vectors": len(VECTORS),
        "rail_profiles": sorted(PROFILES),
        "ledger_campaigns": len(memory.ledger(limit=10000)),
        "ensemble_ready": _state["ensemble"] is not None,
        "llm_configured": get_llm() is not None,
        "detect_latency_ms": _latency_summary(),
    }

def _latency_summary() -> dict | None:
    lat = _state.get("latency_ms") or []
    if not lat: return None
    xs = sorted(lat)
    return {
        "n_calls": len(xs),
        "p50_ms": round(xs[len(xs) // 2], 2),
        "p99_ms": round(xs[min(len(xs) - 1, int(len(xs) * 0.99))], 2),
    }

@app.get("/api/vectors")
def vectors() -> dict:
    return {"vectors": list(VECTORS.values())}

@app.get("/api/profiles")
def profiles() -> dict:
    return {key: {"display_name": p.display_name} for key, p in PROFILES.items()}

@app.post("/api/round")
def post_round(req: RoundRequest) -> dict:
    import asyncio
    try:
        summary = run_round(
            profile_key=req.rail_profile, vector_ids=req.vector_ids,
            n_benign=req.n_benign, seed=req.seed, use_llm=req.use_llm, memory=memory,
            llm=get_llm() if req.use_llm else None,
        )
    except Exception as e:
        raise HTTPException(500, f"round failed: {e}")
    ens = None
    with _state_lock:
        ens = summary.pop("_ensemble", None)
        _state["ensemble"] = ens
        _state["last_round"] = summary
        _state["rounds_run"] += 1
    if ens is not None:
        _persist_ensemble(ens)
    
    # Broadcast to UI
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(json.dumps({"type": "round_complete", "summary": summary})))
    except Exception:
        pass

    return summary

@app.post("/api/tournament")
def post_tournament(req: TournamentRequest) -> dict:
    try:
        summary = run_tournament(
            profile_key=req.rail_profile, vector_ids=req.vector_ids,
            n_benign=req.n_benign, seed=req.seed, use_llm=req.use_llm,
            squad_size=req.squad_size, generations=req.generations, memory=memory,
            llm=get_llm() if req.use_llm else None,
        )
    except Exception as e:
        raise HTTPException(500, f"tournament failed: {e}")
    ens = None
    with _state_lock:
        ens = summary.pop("_ensemble", None)
        _state["ensemble"] = ens
        _state["last_round"] = summary
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

@app.post("/api/detect")
def detect(req: DetectRequest) -> dict:
    import time
    ens = _state.get("ensemble")
    if ens is None:
        raise HTTPException(409, "no ensemble ready")
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
        
    t0 = time.perf_counter()
    X = build_features(txns).to_numpy()
    t1 = time.perf_counter()
    res = ens.predict(X)
    t2 = time.perf_counter()
    
    feat_ms, score_ms = round((t1 - t0) * 1000, 2), round((t2 - t1) * 1000, 2)
    with _state_lock:
        lat = _state.setdefault("latency_ms", [])
        lat.append(score_ms)
        del lat[:-500]
        
    out_results = [
        {
            "txn_id": txns[i].get("txn_id"),
            "flagged": bool(res["flagged"][i]),
            "fused_score": round(float(res["fused_score"][i]), 4),
        }
        for i in range(len(txns))
    ]
    
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(json.dumps({"type": "detect", "results": out_results})))
    except Exception:
        pass
        
    return {
        "latency_ms": {"features": feat_ms, "scoring": score_ms},
        "results": out_results,
    }

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
