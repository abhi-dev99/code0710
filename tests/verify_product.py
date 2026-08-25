"""
Live verification of the product-completeness fixes (run against a live server):
  1. /api/health reports ensemble_ready + artifact
  2. POST /api/round persists the ensemble artifact to disk
  3. GET /api/ledger/export returns a CSV with the right columns
  4. POST /api/detect works off the persisted ensemble (no in-memory fit needed)
Run: .venv\\Scripts\\python.exe tests\\verify_product.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
ARTIFACT = ROOT / "defense" / "models" / "artifacts" / "arena_ensemble.joblib"

fails: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        fails.append(name)


def get(path: str) -> tuple[int, object]:
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return r.status, json.loads(r.read())


def post(path: str, body: dict) -> tuple[int, object]:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.status, json.loads(r.read())


print("PRODUCT VERIFICATION — LiveFire")

st, h = get("/api/health")
check("health ensemble_ready", st == 200 and h.get("ensemble_ready") is True, json.dumps(h.get("ensemble_artifact")))

st, s = post("/api/round", {"rail_profile": "card_intl", "n_benign": 600, "seed": 710, "use_llm": False})
check("round runs", st == 200 and "held_out_detection_rate" in s, f"held-out det {s.get('held_out_detection_rate')}")

check("ensemble artifact persisted", ARTIFACT.exists(), str(ARTIFACT.name))

req = urllib.request.urlopen(BASE + "/api/ledger/export", timeout=60)
csv_text = req.read().decode("utf-8-sig")
header = csv_text.splitlines()[0].split(",")
check("ledger CSV export", req.status == 200 and header[0] == "ts" and "detection_rate" in header,
      f"{len(csv_text.splitlines())-1} data rows")

txns = [
    {"txn_id": "v-benign", "user_id": "u_v1", "device_id": "dev_v1",
     "merchant_id": "m_v1", "channel": "card_present", "amount": 55.0,
     "timestamp": datetime.now(timezone.utc).isoformat(), "location_distance_km": 2},
    {"txn_id": "v-attack", "user_id": "u_v2", "device_id": "dev_v2",
     "merchant_id": "m_v2", "channel": "card_not_present", "amount": 4900.0,
     "timestamp": datetime.now(timezone.utc).isoformat(), "location_distance_km": 1500},
]
st, d = post("/api/detect", {"transactions": txns})
ok = st == 200 and len(d.get("results", [])) == 2 and d["results"][1]["flagged"]
check("detect on persisted ensemble", ok,
      f"attack flagged={d['results'][1]['flagged'] if st == 200 else '?'} fused={d['results'][1]['fused_score'] if st == 200 else '?'}")

st, r = get("/api/rounds")
check("round history endpoint", st == 200 and len(r.get("rounds", [])) > 0, f"{len(r.get('rounds', []))} rounds")

print(f"\nVERIFICATION: {6 - len(fails)} passed, {len(fails)} failed")
sys.exit(1 if fails else 0)
