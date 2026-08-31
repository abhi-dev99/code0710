# LiveFire 🔥

**Adversarial co-evolution arena for payment-fraud defense. Red invents attacks, Blue learns to catch them, SHAP explains why — every round committed to a Robustness Ledger.**

> Mastercard Innovation Challenge 2026 — AI Defense Lab for Payment Security · Team code0710

### Thesis in 15 seconds

Static fraud models lose to adaptive attackers. LiveFire closes the loop: an **LLM red team proposes statistical generator parameters** → a **deterministic weaver compiles them into rail-realistic transactions** → a **heterogeneous blue ensemble detects + disagrees → novelty-flags** → **SHAP explains what got caught** → that intelligence **mutates the next attack generation**. Same vectors replayed across four rail profiles for a per-rail survival comparison.

```
IDENTIFY  14-vector taxonomy (5 families incl. agentic D1-D3)
GENERATE  ox-alpha (reasoning=max, failover chains) → generator params (JSON, not free-text)
WEAVE     Transaction Weaver → seeded, constraint-checked txns (CPU, reproducible)
DEFEND    XGB (50%) + LR (20%) + Rules (20%) + IsolationForest (10%) → fused score, calibrated threshold
EXPLAIN   SHAP TreeExplainer → top-k reasons → written to strategy memory (SQLite)
MUTATE    memory + SHAP context fed into next red prompt → co-evolution
LEDGER    every campaign + round persisted; multi-rail replay; CSV export
```

### Run it in 30 seconds

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy config\settings.example.env .env   # fill LLM_API_KEY for ox-alpha; product runs without it

# 1 — real-data anchor (separate from arena, no synthetic)
python defense\train_real_backbone.py        # → defense/models/artifacts/ulb_backbone.joblib

# 2 — full test suite, zero LLM, deterministic
python tests\test_e2e.py                    # 6/6 expected

# 3 — the product
uvicorn app.api:app --port 8000             # http://localhost:8000  (or: docker compose up --build)
```

`POST /api/round` runs one closed loop. `POST /api/tournament` runs population red-teaming. `POST /api/detect` scores your own transactions. `GET /api/ledger/export` downloads the ledger.

### Why LiveFire is not another fraud demo

| Usual failure | What LiveFire does |
|---|---|
| **Metrics trained and tested on own simulator** | **Two numbers, never mixed.** Real credibility = XGB on real ULB holdout (ROC-AUC 0.985 / AP 0.875). Arena = synthetic-attack detection vs real-anchored benign. |
| **Single model, single threshold, inflated rate** | **Heterogeneous blue**: XGB (explainable) + LR + deterministic rules + IF (benign-only). Threshold calibrated on **held-out benign slice** at 0.5% FP target. |
| **"98% detection" at unstated FP** | **Honest operating point.** Every run reports its own *measured* detection + *realized* FP next to the 0.5% target. Ranges across seeds, not points. |
| **LLM writes transactions directly** | **LLM buys the plan, Weaver builds the transactions.** LLM outputs only statistical parameters. Weaver expands CPU-side, seeded, through 6-check constraint engine × rail profile. |
| **One geography, one rail** | **Four rail profiles** — `card_intl` / `eu_psd2` / `us_cnp` / `upi_in` — same vectors, per-rail survival in one ledger. |

### Honest numbers — read before you quote

**Real backbone (no synthetic):** `defense/models/metadata/ulb_backbone_metrics.json` — ULB corpus, native 29 features, committed split `SEED=710`, `n_jobs=1` deterministic:
**ROC-AUC 0.985 / AP 0.875** (n_train 227,845, n_test 56,962)

**Arena (synthetic attacks vs real-anchored benign, cross-vector holdout):**
* Canonical 4-vector round (card_intl, A1/B1/C1/D1): **~70% held-out detection @ ~0.53% realized FP** (target 0.5%)
* Breakthrough grid (48 low-signature plans): template `80.9% → 0.0%` evasion, **recovery 66.7–83.3% across 3 seeds**
* Live ox-alpha tournament (48/54 plans landed): escalation **71.5% → 40.5% → 36.9%** — blue retrains each gen and red still pulls down

We also report `pr_auc` and `recall@FPR≤0.001` with **realized** (not nominal) FPR.

### How it works — deep enough to rebuild

**Red:** `ox-alpha` via `attacks/redagent/core/llm_client.py` — tiered routing, failover chains on `429`, fence-strip, shared `AsyncClient`.

**Weaver:** `weave_attack_plan()` validates → entity pools → amount ladder + jitter → inter-arrivals → tz-aware timestamps → per-txn constraint engine (C1-C6) × rail profile. Seeded → reproducible.

**Blue:** `defense/features/arena_features.py` → 16 dims: behavioral, velocity (causal 1h), graph (causal fan-out), `memo_injection_score` for Category D. `defense/models/backbone.py` fusion `0.50/0.20/0.20/0.10`; disagreement → `novelty_flag`.

**Memory & Ledger:** `strategy_memory.py` (SQLite) — campaigns + rounds, vector report cards, mutation context. `run_tournament()` fields squad_size × vectors × generations.

**Tech stack:** Python 3.12 · XGBoost + sklearn · SHAP · FastAPI · SQLite → Neon · httpx · Docker · GH Actions

### 14 vectors, 4 rails — honestly scoped

`attacks/taxonomy.json` v1.0 — 14 vectors across 5 categories: identity (A1-A3), social (B1-B3), evasion (C1-C3), **agentic (D1-D3 — differentiator)**, poisoning (E1-E2). Shipped detection covers all 14; Category D semantic tier is minimum-viable heuristic stand-in (full LLM tier architected).

Rails: `card_intl` (global), `eu_psd2` (PSD2 SCA), `us_cnp` (no SCA), `upi_in` (NPCI-calibrated).

### Evidence, reproducibility, path to production

**Evidence committed:** `defense/models/metadata/ulb_backbone_metrics.json`, `evidence/breakthrough_report_seed71*.json`, `evidence/live_tournament_3gen_seed909.json`, `CHANGELOG.md`, `docs/AUDIT.md`

**Reproducibility:** every weave seeded, every split `SEED=710`, XGB `n_jobs=1` pinned, `tests/calib_sweep.py` reproduces R14 table.

**Path to production:** `Dockerfile` + `docker-compose.yml`, `BlueEnsemble.save/load`, `/api/health` p50/p99. Real gaps documented honestly.

### Verify it yourself

```bash
python tests/test_e2e.py && python tests/tournament_test.py
python tests/calib_sweep.py
curl http://localhost:8000/api/health
```

LiveFire is not a model. It is a **measurement harness that makes fraud defenses improvable** — by making them fail honestly, explain why, and remember how to fail better next round.

---
**Team code0710** · **LiveFire Terminal** at `http://localhost:3000` (React, amber-on-black, dense) and `http://127.0.0.1:8000` (API)
