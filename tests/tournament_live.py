"""
LIVE ox-alpha RED TOURNAMENT validation — burns real tokens on purpose.
Small squad (3) x 2 vectors x 2 generations = up to 12 LLM calls.
Run: .venv\\Scripts\\python.exe tests\\tournament_live.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]

from env_bootstrap import load_env  # noqa: E402

load_env()

from arena.loop import run_tournament  # noqa: E402
from attacks.redagent.core.llm_client import LLMClient  # noqa: E402
from redagent.core.strategy_memory import StrategyMemory  # noqa: E402

mem = StrategyMemory(ROOT / "arena_ledger.db")
llm = LLMClient.from_env()

s = run_tournament(
    profile_key="card_intl",
    vector_ids=["A1", "B3"],
    n_benign=600,
    seed=710,
    use_llm=True,
    squad_size=3,
    generations=2,
    memory=mem,
    llm=llm,
)

print("\n=== LIVE TOURNAMENT RESULT ===")
print(f"escalation: {s['escalation']}  red_advantage: {s['red_advantage']}")
for g in s["generations"]:
    champs = ", ".join(f"{c['vector']}={c['detection_rate']}{'(LLM)' if c['llm_generated'] else ''}"
                       for c in g["champions"])
    llm_dets = [c["detection_rate"] for c in g["candidates"] if c["llm"]]
    print(f"gen{g['gen']}: {g['n_llm_plans']}/{g['n_candidates']} LLM plans | "
          f"held-out det {g['held_out_detection_rate']} | FP {g['benign_fp_rate']}")
    print(f"        LLM candidate dets: {llm_dets}")
    print(f"        champions: {champs}")
    print(f"        SHAP: {g['shap_why'][:120]}")

(Path(__file__).resolve().parent / "_tourn_live_out.json").write_text(
    json.dumps({k: v for k, v in s.items() if not k.startswith("_")}, indent=2),
    encoding="utf-8")
print("\n[live tournament complete — full summary in tests/_tourn_live_out.json]")
