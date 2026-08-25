"""
RED TOURNAMENT selftest (template mode — zero LLM tokens).
Verifies: squad generation, 70/30 train/held-out split, per-candidate
champion selection, escalation curve across generations, ledger writes.
Run: .venv\\Scripts\\python.exe tests\\tournament_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.loop import run_tournament  # noqa: E402
from redagent.core.strategy_memory import StrategyMemory  # noqa: E402

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        fails.append(name)


mem = StrategyMemory(Path(__file__).resolve().parents[1] / "arena_ledger.db")
s = run_tournament(
    profile_key="card_intl",
    vector_ids=["A1", "A3", "B1"],
    n_benign=900,
    seed=710,
    use_llm=False,
    squad_size=6,
    generations=2,
    memory=mem,
)

print(f"\nescalation curve: {s['escalation']}")
for g in s["generations"]:
    champs = ", ".join(f"{c['vector']}={c['detection_rate']}" for c in g["champions"])
    print(f"  gen{g['gen']}: {g['n_candidates']} candidates "
          f"({g['n_llm_plans']} llm), held-out det {g['held_out_detection_rate']}, "
          f"FP {g['benign_fp_rate']}, champions: {champs}")

check("structure: two generations", len(s["generations"]) == 2)
check("squad size honored", all(g["n_candidates"] == 18 for g in s["generations"]),
      f"{s['generations'][0]['n_candidates']} candidates/gen")
check("held-out count = 30% of squad", all(g["n_heldout"] == 6 for g in s["generations"]),
      f"{s['generations'][0]['n_heldout']} held-out/gen")
check("champion per vector per gen", all(len(g["champions"]) == 3 for g in s["generations"]))
check("escalation curve populated", len(s["escalation"]) == 2 and all(0 <= e <= 1 for e in s["escalation"]))
check("FP constraint held", all(g["benign_fp_rate"] <= 0.05 for g in s["generations"]),
      f"max FP {max(g['benign_fp_rate'] for g in s['generations'])}")
check("red advantage computed", 0 <= s["red_advantage"] <= 1, f"{s['red_advantage']}")
check("champions are the most evasive", all(
    c["detection_rate"] == min(k["detection_rate"] for k in g["candidates"]
                               if k["vector"] == c["vector"]) + 0.0
    or c["detection_rate"] <= min(k["detection_rate"] for k in g["candidates"]
                                  if k["vector"] == c["vector"]) + 1e-9
    for g in s["generations"] for c in g["champions"]))
check("ledger received tournament campaigns",
      len(mem.round_history(5)) >= 2 and "TOURNAMENT" in (mem.round_history(1)[0]["notes"] or ""))

print(f"\nTOURNAMENT TEST: {9 - len(fails)} passed, {len(fails)} failed")
sys.exit(1 if fails else 0)
