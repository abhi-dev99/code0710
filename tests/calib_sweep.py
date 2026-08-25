import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for p in ("attacks", "config", "defense", "arena"):
    sp = str(ROOT / p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from redagent.core.strategy_memory import StrategyMemory
from loop import run_round
import tempfile

import shutil

td = Path(tempfile.mkdtemp())
try:
    for calib in (375, 1000, 2500, 5000):
        m = StrategyMemory(td / f"t{calib}.db")
        s = run_round(profile_key="card_intl", vector_ids=["A1", "B1", "C1", "D1"],
                      n_benign=1500, n_calib_benign=calib, use_llm=False, memory=m)
        print(f"calib={calib:5d}  det={s['held_out_detection_rate']:.3f}  "
              f"fp={s['benign_fp_rate']:.4f}  f1={s['overall']['f1']:.3f}  "
              f"recall={s['overall']['recall']:.3f}  prec={s['overall']['precision']:.3f}", flush=True)
finally:
    shutil.rmtree(td, ignore_errors=True)

