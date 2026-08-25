"""LIVE 3-generation ox-alpha tournament (54 LLM plans incl. agentic D1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from env_bootstrap import load_env  # noqa: E402

load_env()

from arena.loop import run_tournament  # noqa: E402
from attacks.redagent.core.llm_client import LLMClient  # noqa: E402
from redagent.core.strategy_memory import StrategyMemory  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
s = run_tournament(
    profile_key="card_intl",
    vector_ids=["A1", "B1", "D1"],
    n_benign=1200,
    seed=909,
    use_llm=True,
    squad_size=6,
    generations=3,
    memory=StrategyMemory(ROOT / "arena_ledger.db"),
    llm=LLMClient.from_env(),
)
out = {k: v for k, v in s.items() if not k.startswith("_")}
(ROOT / "tests" / "_live3.json").write_text(json.dumps(out, indent=2, default=str),
                                            encoding="utf-8")
print("ESCALATION:", s["escalation"])
for g in s["generations"]:
    print(f"gen{g['gen']}: {g['n_llm_plans']}/{g['n_candidates']} llm | "
          f"det {g['held_out_detection_rate']} | fp {g['benign_fp_rate']} | "
          f"champs: {[(c['vector'], c['detection_rate'], c['llm_generated']) for c in g['champions']]}")
