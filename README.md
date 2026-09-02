<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="app/static/logo-dark.svg">
  <img src="app/static/logo.svg" alt="LiveFire" height="110">
</picture>

**An adversarial co-evolution arena for payment-fraud defense.**
Red invents attacks → Blue learns to catch them → SHAP explains why → every round hits a Robustness Ledger.

Mastercard Innovation Challenge 2026 — AI Defense Lab for Payment Security · **Team code0710**

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Tests](https://img.shields.io/badge/e2e%20tests-6%2F6%20passing-brightgreen)](livefire/tests/test_e2e.py)
[![Attack Vectors](https://img.shields.io/badge/attack%20vectors-14-orange)](attacks/taxonomy.json)
[![Rail Profiles](https://img.shields.io/badge/rail%20profiles-4%20global-lightgrey)](config/rail_profiles.py)

[Why LiveFire](#why-livefire-exists) · [Screenshots](#screenshots) · [Quick Start](#quick-start) · [Architecture](#architecture) · [Honest Numbers](#honest-numbers--read-before-you-quote) · [Mastercard Fit](#where-this-sits-in-a-real-mastercard-transaction) · [Reproduce It](#evidence--reproducibility)

</div>

---

## Why LiveFire exists

Static fraud models lose to adaptive attackers. LiveFire closes the loop:

- An **LLM red team** proposes statistical generator parameters
- A **deterministic weaver** compiles them into rail-realistic transactions
- A **heterogeneous blue ensemble** detects, disagrees, and novelty-flags
- **SHAP** explains what got caught
- That intelligence **mutates the next attack generation**
- The same vectors replay across **four global rail profiles** for a per-rail survival comparison — the one axis none of the reference architectures we benchmarked against attempt

| Usual failure | What LiveFire does instead |
|---|---|
| Metrics trained and tested on its own simulator | <ul><li>**Two numbers, never mixed**</li><li>Real credibility = XGB on real ULB holdout (ROC-AUC 0.9852 / AP 0.8750)</li><li>Arena = synthetic-attack detection vs real-anchored benign</li></ul> |
| Single model, single threshold, inflated detection rate | <ul><li>**Heterogeneous blue**: XGB (explainable) + LR + deterministic rules + IF (benign-only)</li><li>Threshold calibrated on a **held-out benign slice** at a 0.5% FP target</li></ul> |
| "98% detection" at an unstated false-positive rate | <ul><li>**Honest operating point** — every run reports its own</li><li>*measured* detection + *realized* FP next to the 0.5% target</li><li>Ranges across seeds, not cherry-picked points</li></ul> |
| LLM writes fraudulent transactions directly | <ul><li>**LLM buys the plan**, the Weaver builds the transactions</li><li>LLM only outputs statistical parameters</li><li>A seeded CPU compiler expands them through a 6-check constraint engine per rail</li></ul> |
| One geography, one rail | <ul><li>**Four rail profiles** — `card_intl` / `eu_psd2` / `us_cnp` / `upi_in`</li><li>Same vectors, per-rail survival in one ledger</li></ul> |
| A "prompt-injection detector" that's a keyword match | <ul><li>**Category D is a structural check**</li><li>`beneficiary_mismatch` compares the mandate's stated payee against where settlement actually lands</li><li>Same account-reference-binding principle real agentic-payment protocols use</li></ul> |

## Screenshots

<table>
<tr><td align="center"><b>LiveFire Terminal</b> — one frontend, React/Vite/Tailwind, amber-on-black</td></tr>
<tr><td><img src="docs/assets/terminal-screenshot.png" alt="LiveFire Terminal: dense keyboard-driven blotter view of the live arena"></td></tr>
</table>

The Terminal is the only frontend — a plain HTML dashboard existed earlier and is now deprecated (removed, not just unlinked) in favor of one real surface with real screens: the blotter, a full taxonomy browser, a rail-profile browser, a multi-rail comparison, and the real-backbone credibility numbers, all keyboard-driven.

## Quick Start

**1. Create the environment and install dependencies**
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure the LLM (optional — the product runs without it, templates fill in; or set it live later via the Terminal's Settings panel)**
```bash
copy config\settings.example.env .env
```

**3. Anchor to real data** — separate from the arena, no synthetic data involved
```bash
python defense\train_real_backbone.py
```
→ writes `defense/models/artifacts/ulb_backbone.joblib`

**4. Run the test suite** — zero LLM calls, fully deterministic
```bash
python tests\test_e2e.py
```
→ 6/6 passing

**5. Build the Terminal** — the API serves this build directly; there is no separate frontend server in production
```bash
cd app\frontend
npm install
npm run build
cd ..\..
```

**6. Start the API** — this is now the one URL: the Terminal *and* every endpoint
```bash
uvicorn app.api:app --port 8000
```
→ http://localhost:8000 (or: `docker compose up --build`, which builds the Terminal for you — see the Dockerfile's frontend build stage)

**Iterating on the UI itself?** Skip step 5 and run `npm run dev` inside `app/frontend` instead — a hot-reloading dev server on `:3000` that talks to the same API on `:8000` via CORS. Switch back to the built version (step 5) when you're done.

**Key endpoints once the API is running:**

| Endpoint | What it does |
|---|---|
| `POST /api/round` | Runs one closed loop (red → weave → blue → explain → ledger) |
| `POST /api/tournament` | Runs population red-teaming (squad vs. blue, multi-generation) |
| `POST /api/detect` | Scores your own transactions with the live ensemble |
| `GET /api/ledger/export` | Downloads the full Robustness Ledger as CSV |

## Architecture

```
IDENTIFY  14-vector taxonomy (5 families incl. agentic D1-D3) — atlas of further-researched
          vectors tracked for the next iteration, not padded into the shipped count
GENERATE  configurable LLM (Gemini by default, reasoning=max, failover chains) → generator params (JSON, not free-text)
WEAVE     Transaction Weaver → seeded, constraint-checked txns (CPU, reproducible)
DEFEND    XGB (50%) + LR (20%) + Rules (20%) + IsolationForest (10%) → fused score, calibrated threshold
EXPLAIN   SHAP TreeExplainer → top-k reasons → written to strategy memory (SQLite)
MUTATE    memory + SHAP context fed into next red prompt → co-evolution
LEDGER    every campaign + round persisted; multi-rail replay; CSV export
```

**Red** — a configurable LLM (Gemini 3 by default) via `attacks/redagent/core/llm_client.py`:
- Provider-agnostic: any OpenAI-compatible endpoint, swappable live via `/api/llm-config` — bring your own key, no restart
- Tiered routing across a model chain
- Failover on `429` (rate limit), `404` (a retired/renamed model slug), and `402` (insufficient credit) — OpenRouter's free/preview tier churns and a $0-credit account can hit any of the three; the whole point of a chain is to survive them
- Fence-strip on raw model output
- Shared `AsyncClient` scoped correctly per event loop

**Weaver** — `weave_attack_plan()`:
- Validates the plan → entity pools → amount ladder + jitter → inter-arrivals → tz-aware timestamps
- Per-txn constraint engine (C1-C6) × rail profile
- Seeded end to end → fully reproducible

**Blue** — `defense/features/arena_features.py` → 17 dims:
- Behavioral, velocity (causal 1h), graph (causal fan-out)
- `memo_injection_score` (text-pattern tier) + `beneficiary_mismatch` (structural tier, Category D)
- `defense/models/backbone.py` fuses XGB/LR/Rules/IF at `0.50/0.20/0.20/0.10`; disagreement → `novelty_flag`
- `beneficiary_mismatch` also fires as a hard, fully-auditable rule — a mandate/settlement mismatch is fraud by construction, not a probabilistic call

**Memory & Ledger** — `strategy_memory.py`:
- SQLite, WAL mode, foreign keys enforced
- Campaigns + rounds, vector report cards, mutation context
- `run_tournament()` fields squad_size × vectors × generations

**Tech stack:**
- Python 3.12 · XGBoost + sklearn · SHAP · FastAPI
- SQLite (env-configurable path; Postgres is a documented path-to-production step, not a present-tense claim)
- React/Vite/Tailwind terminal UI · httpx · Docker

## Honest Numbers — read before you quote

**Real backbone (no synthetic):** `defense/models/metadata/ulb_backbone_metrics.json`
- ULB corpus, committed split `SEED=710`, `n_jobs=1` deterministic
- **ROC-AUC 0.9852 / AP 0.8750** (n_train 227,845, n_test 56,962)
- **Excludes ULB's `Time` column on purpose** — seconds-since-capture-start is a dataset artifact with no live-scoring equivalent
- Checked for this exact training/serving skew (`capture_clock_ablation` in the committed metrics file): with it, 0.9850/0.8752; without it, 0.9852/0.8750
- The headline number was never meaningfully inflated by it — now a committed, reproducible fact, not an assumption

**Arena (synthetic attacks vs real-anchored benign, cross-vector holdout):**
* Canonical 4-vector round (card_intl, A1/B1/C1/D1): **~70% held-out detection @ ~0.53% realized FP** (target 0.5%)
* Breakthrough grid (48 low-signature plans): template `80.9% → 0.0%` evasion, **recovery 66.7–83.3% across 3 seeds**
* Live tournament (48/54 plans landed): escalation **71.5% → 40.5% → 36.9%** — blue retrains each gen and red still pulls down

We also report `pr_auc` and `recall@FPR≤0.001` with **realized** (not nominal) FPR.

**Fidelity — is "real-corpus anchored" actually true?** `evidence/fidelity_report.json` (`python -m defense.fidelity`):
- **Distinguisher AUC 0.5693** — a classifier trained to tell real ULB rows apart from LiveFire's synthetic benign rows (on amount + hour-of-day) barely beats chance. 0.5 = indistinguishable, 1.0 = trivially separable.
- KS statistic on amount: **0.0587** (distributions close); on hour-of-day: **0.1495** (looser — reported as-is, not smoothed over)
- This is a measurement, not an assertion: a generator that only reproduced marginals while destroying joint structure would still show up here, because the distinguisher is free to find whatever actually separates the two distributions rather than a fixed statistic we picked in advance

## Where this sits in a real Mastercard transaction

Named checkpoints, not a vague "we integrate with Mastercard" line:

**Agent Pay for Machines (AP4M)** — Mastercard's June 2026 agentic-payments framework:
- Four sequential functions: *credentialing* a registered agent → *permissioning* what it can spend → *transacting* across card/account rails → *settling*
- LiveFire's rail-profile constraint engine occupies the **permissioning** checkpoint (per-channel caps, category rules, SCA step-up)
- LiveFire's blue ensemble occupies the risk-scoring step inside **transacting**

**The wire format** at that checkpoint is **ISO 8583**:
- Authorization request = MTI `0100` (acquirer → issuer)
- Response = MTI `0110`
- LiveFire's fused score is designed to attach to that `0110` response, not invent a new message format

**Decision Intelligence Pro** — Mastercard's own inline scorer:
- Real-time ML in the authorization path, ~50ms, 500+ data points per transaction
- Network-level intelligence across billions of transactions
- LiveFire's BlueEnsemble occupies the **same architectural slot** — inline, pre-decision scoring — at hackathon scale (17 features, single process)
- Not claiming scale parity — claiming the same slot in the pipeline, honestly sized

**Adjacent real acquisitions** in Mastercard's fraud/identity/AML stack:
- **Ekata** — digital identity verification (maps to Category A)
- **Ethoca** — post-authorization dispute/chargeback collaboration
- **CipherTrace** — crypto/blockchain AML (relevant since AP4M settles partly on-chain)
- LiveFire's rail-profile design is the seam where a real deployment would plug into each

## 14 vectors, 4 rails — honestly scoped

`attacks/taxonomy.json` v1.0:
- 14 vectors across 5 categories: identity (A1-A3), social (B1-B3), evasion (C1-C3), **agentic (D1-D3)**, poisoning (E1-E2)
- Shipped detection covers all 14, including a real structural signal for D1-D3 — not a text-pattern stand-in for a semantic tier
- Rails: `card_intl` (global), `eu_psd2` (PSD2 SCA), `us_cnp` (no SCA), `upi_in` (NPCI-calibrated)

Tracked research, not yet wired into generation/detection (not padded into the taxonomy count):
- Merchant-mandate forgery — a merchant fabricates a signed mandate the user never approved, distinct from D1's poisoned-invoice mechanism
- Indirect prompt injection via product-listing content rather than a tool call
- Both grounded in current (2026) AP2 red-teaming literature, not speculative

## Evidence & Reproducibility

**Evidence committed:**
- `defense/models/metadata/ulb_backbone_metrics.json` (now with the capture-clock ablation)
- `evidence/breakthrough_report_seed71*.json`, `evidence/live_tournament_3gen_seed909.json`, `evidence/fidelity_report.json`
- `CHANGELOG.md`, `docs/AUDIT.md`

**Reproducibility:**
- Every weave seeded, every split `SEED=710`, XGB `n_jobs=1` pinned
- `tests/calib_sweep.py` reproduces the calibration table
- `python -m defense.fidelity` reproduces the fidelity report
- `tests/test_e2e.py` is 6/6 green with zero LLM calls

**Path to production:**
- `Dockerfile` + `docker-compose.yml`, `BlueEnsemble.save/load`, `/api/health` p50/p99
- `LEDGER_DB_URL` as the seam a managed Postgres (e.g. Neon) would attach to for durable multi-instance ledger storage
- Not yet wired — listed here as a next step, not claimed as shipped. Real gaps documented honestly.

Verify it yourself:
```bash
python tests/test_e2e.py && python tests/tournament_test.py
python tests/calib_sweep.py
curl http://localhost:8000/api/health
```

---

<div align="center">

LiveFire is not a model. It is a **measurement harness that makes fraud defenses improvable** — by making them fail honestly, explain why, and remember how to fail better next round.

**Team code0710** · Submitted to the Mastercard Innovation Challenge @ Global Fintech Fest 2026

</div>
