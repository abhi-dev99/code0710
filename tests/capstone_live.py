"""Capstone: live ox-alpha arena round + multi-rail ledger run."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from env_bootstrap import load_env  # noqa: E402

load_env()
for p in ("attacks", "config", "defense", "arena"):
    sp = str(ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from loop import run_multi_rail, run_round
from redagent.core.llm_client import LLMClient
from redagent.core.strategy_memory import StrategyMemory

m = StrategyMemory(ROOT / "arena_ledger.db")
llm = LLMClient.from_env()

print("=== LIVE ox-alpha round (card_intl) ===")
s = run_round(profile_key="card_intl", vector_ids=["A1", "C2", "B1", "D1"],
              n_benign=2000, use_llm=True, memory=m, llm=llm)
print(json.dumps({k: s[k] for k in ("held_out_vector", "held_out_detection_rate",
                                    "benign_fp_rate", "shap_why")}, indent=1))
print("planners:", [(v["id"], "llm" if v["llm_generated"] else "tpl") for v in s["vectors"]])

print("=== MULTI-RAIL (templates) ===")
mr = run_multi_rail(vector_ids=["A1", "B1", "C1", "D1"], n_benign=1000, use_llm=False)
for rail, r in mr.items():
    if r.get("error"):
        print(rail, "-> ERR", str(r["error"])[:80])
    else:
        print(f"{rail} -> det={r['held_out_detection_rate']} fp={r['benign_fp_rate']} f1={r['overall']['f1']}")
