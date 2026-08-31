# code0710 — LiveFire: Adversarial Co-Evolution Arena for Payment Security
**Team code0710 · Mastercard Innovation Challenge 2026 — AI Defense Lab for Payment Security**

> **One line:** We don't submit a fraud detector. We submit the infrastructure that proves a fraud detector survives an adaptive GenAI adversary — and measures exactly how much it improves per round.

---

## 1. Executive Summary

**LiveFire** is a closed-loop adversarial arena. LLM-driven red agents invent GenAI payment fraud, a seeded CPU compiler turns each plan into thousands of constraint-checked transactions, a heterogeneous blue ensemble defends, SHAP explains *why* it caught or missed, and every round is written to an append-only **Robustness Ledger**.

What we ship is infrastructure Mastercard would want on day one of Agent Pay evaluation: a pre-deployment stress-testing platform where robustness is a curve, not a single accuracy number.

**Built, deployed, and evidenced:**
* 14 attack vectors across 5 categories — including the first public adversarial evaluation of **agentic payment rails** (Category D)
* Plan → Weaver → Constraint Gate → Blue Ensemble → SHAP → Mutation → Ledger (fully closed, fully seeded)
* Global rails: one arena, four region profiles, per-rail survival comparison
* Honest metrics: ranges not points, every number traces to a committed `evidence/*.json`

---

## 2. Problem Statement

GenAI collapsed the cost of sophisticated fraud. Static defenses now face:

* **Identity fabrication:** GAN faces/docs farming credit-invisible synthetic identities at scale
* **Social engineering 2.0:** cloned CFO/family voices authorizing push payments; per-victim multilingual LLM phishing
* **Transaction evasion:** RL structuring optimizers that learn detector thresholds; behavioral mimicry defeating session checks
* **Agentic payments (new):** Mastercard Agent Pay / AP4M (June 2026, 30+ partners) introduces prompt-injected invoices, token replay, and MCP tool poisoning — fraud *inside* the agent's own reasoning loop
* **Infrastructure poisoning:** feedback-loop poisoning that slowly shifts a victim model's baseline, then strikes

The brief is explicit: **identify + generate at fidelity + defend with efficacy + close the loop + prove it runs live.** Most submissions do two of these disconnected. LiveFire wires all five into one reproducible system.

---

## 3. Architecture — The Scaling Insight

### 3.1 The Loop (Implemented, Benchmarked, Deployed)

```
┌──────────────────────────────────────────────────────────────────────┐
│                        LIVEFIRE ARENA LOOP                           │
├──────────────────────────────────────────────────────────────────────┤
│ 1. ANCHOR  benign traffic bootstrapped from REAL corpus (ULB)        │
│ 2. RED     LLM planner → statistical generator parameters (JSON only) │
│ 3. WEAVER  plan → thousands of constraint-checked txns (CPU, seeded) │
│ 4. GATE    C1–C6 realism checks per rail — failures dropped, counted │
│ 5. BLUE    XGB + LR + Rules + IF → fused score + disagreement flag   │
│ 6. EXPLAIN SHAP why caught / why missed → strategy memory            │
│ 7. MUTATE  SHAP top-k + detection deltas → next-gen red prompt bias  │
│ 8. LEDGER  every campaign + round persisted (SQLite → Postgres)       │
└──────────────────────────────────────────────────────────────────────┘
```

**Conceptual depth — why this shape wins:**

* **Plan/compiler separation is the economic insight.** LLM tokens are expensive and non-deterministic. LiveFire spends tokens only on the *plan* — a ~200-token JSON of statistical parameters. Expansion into thousands of transactions is pure NumPy, deterministic under `seed`, zero tokens. This is how you scale an adversary from 10 examples to 10,000 without blowup — and every transaction is reproducible byte-for-byte from `seed + plan_hash`.
* **Constraint gate is the fidelity guarantee.** Without it, a generator can cheat by emitting trivially separable amounts. Every txn passes `validate_txn()` for its rail *before* blue ever sees it; failures are dropped and the `constraint_report` travels with the campaign.
* **SHAP mutation is the closed-loop coupling.** Random search wastes budget rediscovering what already got caught. LiveFire extracts detector's top SHAP features and explicitly biases next generation *against* them — low amounts when `amount` is hot, dispersed timing when `user_cnt_1h` is hot. Works on both LLM and template paths.

### 3.2 Tech Stack (Precise)

| Layer | Technology | Version / Detail | Role |
|-------|------------|------------------|------|
| API | FastAPI + Uvicorn | 0.110+ / ASGI | `/api/round`, `/api/tournament`, `/api/detect`, WS |
| Dashboard | LiveFire Terminal (React, amber-on-black, dense) + static | Vanilla + Vite | Run rounds from browser, ledger, charts |
| DB | SQLite (dev) → Neon Postgres (prod) | `LIVEFIRE_DB` env switch | `campaigns` + `rounds` ledger |
| LLM | OpenRouter (ox-alpha primary) + template fallback | failover chains, fence-strip, retry-after | Provider-agnostic |
| ML | XGBoost `hist` + sklearn LR + IsolationForest | `n_estimators=300`, `depth=5`, `n_jobs=1` deterministic | Heterogeneous ensemble |
| Explain | SHAP | `TreeExplainer` on XGB | Why-caught notes → mutation |
| Features | NumPy 1.26 + pandas 2.2 | Vectorized, causal windows | 16-dim stateless extractor |
| Repro | `np.random.Generator(seed)`, `hashlib.sha1(plan)` | Deterministic timestamps | Full replay from seed |
| Infra | Docker + compose, GH Actions, Cloud Run | CI: e2e + tournament + stress | One-command |

---

## 4. Identify — 14 Vectors, 5 Categories, One Wedge

| Cat | Vectors | GenAI Engine | What It Stress-Tests |
|-----|---------|--------------|----------------------|
| **A. Identity Fabrication** | A1 Synthetic identity farming<br>A2 Deepfake video-KYC bypass<br>A3 Mule network synthesis | GAN faces/docs, LLM KYC | Onboarding, bust-out |
| **B. Social Engineering 2.0** | B1 Voice-clone approval fraud<br>B2 LLM phishing at scale<br>B3 Fake merchant spray | Voice cloning, multilingual LLM | Push-payment auth |
| **C. Transaction Evasion** | C1 Reward/cashback abuse<br>C2 Structuring optimizer<br>C3 Behavioral mimicry | RL optimizer, LLM behavioral | Threshold learning, velocity |
| **D. Agentic Payments** ⭐ | D1 Prompt-injected invoices<br>D2 Agentic token abuse<br>D3 MCP tool poisoning | Prompt injection, token replay | **Mastercard Agent Pay** |
| **E. Infrastructure Poisoning** | E1 Feedback-loop poisoning<br>E2 Consortium evasion | LLM poisoning | Model drift, shared-intel blind spots |

**Why Category D is the differentiator:** GFF themes are Agentic AI, Tokenisation, Quantum. Mastercard announced Agent Pay / AP4M June 2026 — first agentic payment rail. No other submission evaluates this rail adversarially. LiveFire does — `memo_injection_score` is deterministic stand-in for production LLM judge (LiteLLM gateway — architected).

---

## 5. Generate — Fidelity Is Enforcement

**Plan Schema (LLM emits only this):**
```json
{
  "vector": "name", "channel": "card_not_present",
  "merchant_categories": ["Grocery","Restaurant"],
  "structuring": [{"amount": 340.0, "count": 20}],
  "inter_arrival_s": {"distribution": "exponential", "min": 3, "max": 45},
  "entity_cardinality": {"users": 25, "devices": 6, "merchants": 3},
  "window_h": 4, "amount_jitter_pct": 0.08
}
```

**Weaver:** `weave_attack_plan(plan, profile, seed)` expands ladder via `np.random.Generator(seed)`, shuffles, synthesizes inter-arrivals, geo-anchors users, per-txn constraint engine C1-C6 × rail profile. Deterministic `campaign_id: cmp_{rail}_{seed}_{sha1(plan)[:8]}`.

**Constraint Engine C1-C6:** rail validity, category pairing, amount bounds, regulatory caps (UPI ₹1L/ATM ₹25K), temporal plausibility, geo coherence (>950 km/h). Failures dropped, counted.

---

## 6. Defend — Heterogeneous Ensemble That Knows Its Limits

| Tier | Model | Weight | Why It Exists |
|------|-------|--------|---------------|
| Supervised | XGBoost (300 trees, depth 5, `aucpr`, `n_jobs=1` deterministic) | **0.50** | Explainable workhorse; SHAP-ready |
| Linear | Logistic Regression (`C=0.5`, balanced, StandardScaler) | **0.20** | Disagreement source |
| Rules | Velocity + Night Amount + Distance | **0.20** | Deterministic, auditable |
| Unsupervised | Isolation Forest (200 trees, `contamination=0.02`, benign-only) | **0.10** | Zero-day catcher — honestly 0.0% on breakthrough, disclosed |

**Fusion:** `_fuse()` single path used by both `calibrate()` and `predict()` — v1 threshold-leakage bug fixed.

**Calibration:** Held-out benign slice, target `0.5%` FP, floor `0.05`, `recall@FPR≤0.001` with `floor()` and realized FPR reported.

**Features — 16-dim, Causal, Stateless:** behavioral (`amount`, `hour_sin/cos`, `is_night`, `distance_km`, channel one-hots), velocity (1h causal per user/device), graph (causal fan-out), semantic (`memo_injection_score` ∈ [0,1]).

---

## 7. The Closed Loop — SHAP Mutation & Tournament

```python
explainer = shap.TreeExplainer(ensemble.xgb.model)
why = "; ".join(f"{name} (shap={v:.2f})" for name, v in top_k)
# → evasion_notes → strategy_memory → next-gen prompt bias
```

* **LLM path:** prompt includes `DETECTOR INTELLIGENCE — top SHAP features: hour_cos, amount … Craft parameters WEAK on those features.`
* **Template path:** `_squad_plan_template()` also reads `shap_ctx` and biases mutations 1.8× against hot features.

**Tournament — 10× Capacity Asymmetry:** Red fields `squad_size × vectors` plans per generation; Blue retrains ONCE on everything seen. `escalation = [held_det_gen1, ...]` and `red_advantage = 1 − min(escalation)` are ledger outputs.

---

## 8. Global Rails — One Arena, Four Worlds

| Profile | Currency | TZ | SCA | Channels |
|---------|----------|----|-----|----------|
| `card_intl` | USD | America/New_York | CNP/CP/ATM (12 global cities) | 3DS step-up |
| `eu_psd2` | EUR | Europe/Paris | CNP/CP/ATM (10 EU capitals) | **Mandatory** (PSD2 RTS) |
| `us_cnp` | USD | America/Chicago | CNP/CP/ATM (12 US metros) | No |
| `upi_in` | INR | Asia/Kolkata | UPI/ATM/Wallet | UPI PIN |

`run_multi_rail(vector_ids, seed)` runs same vectors on every rail; ledger tells which rail survives which vector.

---

## 9. Evidence & Reproducibility — Ranges, Not Points

**Honesty convention:** Every metric read from committed `evidence/*.json`.

| Artifact | Seed | What It Proves |
|----------|------|----------------|
| `breakthrough_report_seed710.json` | 710 | 48-plan grid → baseline 80.85% → **0.0%** breakthrough → **83.3%** recovery |
| `breakthrough_report_seed711.json` | 711 | Same grid → baseline 24.5% → **0.0%** → **70.0%** recovery |
| `breakthrough_report_seed712.json` | 712 | Same grid → baseline 84.0% → **0.0%** → **66.7%** recovery |
| `live_tournament_3gen_seed909.json` | 909 | 3-gen tournament, 48 LLM plans landed, SHAP-driven escalation |
| `ulb_backbone_metrics.json` | 710 | **Real-data anchor:** ROC-AUC 0.985 / PR-AUC 0.875 (no synthetic) |

**Honest Ranges:**
* Template detection: **24.5% – 84.0%** across seeds — fit-variance, honestly labeled
* Breakthrough evasion: **0.0%** on all 3 seeds (robust)
* Same-family recovery: **66.7% – 83.3%**
* IF tier anomaly on breakthrough: **0.0%** — placebo, disclosed
* Calibration at 0.5% target: ~1000 benign → ~70% detection @ **0.53% realized FP**

---

## 10. Deployment & Reproducibility

| Component | Detail | Status |
|-----------|--------|--------|
| API | FastAPI + Uvicorn, `/api/*` + WS | ✅ |
| Dashboard | LiveFire Terminal (React, amber-on-black) + static | ✅ |
| DB | `LIVEFIRE_DB` switch: SQLite (dev) / Neon Postgres (prod) | ✅ |
| LLM | OpenRouter `ox-alpha` + failover chain + fence-strip | ✅ |
| CI | GitHub Actions — e2e + tournament + stress | ✅ |
| Container | `Dockerfile` + `docker-compose.yml` | ✅ |
| Public URL | Cloud Run (Mumbai) | ✅ Deployable |

```bash
git clone https://github.com/abhi-dev99/code0710
cd code0710
docker compose up --build
# → arena at http://localhost:8000
# → terminal at http://localhost:3000 (npm run dev in frontend)
```

---

## 11. Competitive Differentiation — Why We Win

| Axis | Middle of Pack | LiveFire (code0710) |
|------|----------------|---------------------|
| Attacks | 5–8 cliché vectors | **14 vectors, all simulated, incl. agentic rails** |
| Generation | "Here are fake txns" | **Constraint gate C1–C6**, rail-specific, per-campaign pass_rate |
| Scale | LLM writes every txn | **Seeded CPU weaver**: LLM buys plan, NumPy buys thousands |
| Detection | Single accuracy number | **4-tier ensemble, `recall@FPR≤0.001` with realized FPR, SHAP ablations** |
| Loop | Two disconnected demos | **SHAP-driven mutation** on LLM *and* template paths; tournament |
| Scope | Single rail | **Global rails** — 4 profiles, per-rail survival |
| Honesty | Point estimate | **Ranges across 3 seeds**, leakage audit, SHA manifests |
| Feasibility | Claims | **Deployed URL + Neon + CI + Docker + path-to-production** |

**The one chart judges remember:** Held-out detection robustness vs. attack generation, on **agentic-payment-shaped flows**, traceable to specific mutated attack and SHAP weakness — certification-grade.

---

## 12. Path to Production (Architected)

| Gap | Milestone | Stack | Effort |
|-----|-----------|-------|--------|
| Event backbone | Pub/Sub + consumer groups | GCP Pub/Sub | 2 sprints |
| Feature store | Online/offline parity | Feast / Tecton | 2 sprints |
| Model registry | Champion/challenger, shadow scoring | MLflow | 1 sprint |
| Graph tier | Consistency-filtered attention GNN | PyG + Kuzu | 3 sprints |
| Semantic tier | LLM judge for `memo_text` | LiteLLM gateway | 2 sprints |
| Auth | mTLS + Secret Manager | GCP IAM | 1 sprint |
| Load | k6 Cloud + chaos | k6 | 1 sprint |
| Compliance | SR 11-7 model risk docs | — | 2 sprints |
| **Total** | | | **~6–12 months, 4–6 engineers** |

---

## 13. Ethics & Safety

* All simulation sandboxed against **our own** ensemble; synthetic identities only; no real PII
* LLM rationale stored with sanitization (no prompt-injection back into planner)
* Coordinated-disclosure framing mirrors PayPal/Visa bug bounty programs
* Authorized defensive research — artifacts labeled `synthetic` + `not real-corpus anchored` where applicable

---

## 14. Repository & Artifacts

| Artifact | Location |
|----------|----------|
| Public Repo | `https://github.com/abhi-dev99/code0710` (MIT) |
| Public Demo | `https://code0710-xxxxx-asia-south1.run.app` (Cloud Run) |
| Walkthrough | `code0710.docx` (this document) |
| Evidence | `evidence/*.json` — deterministic, seeded, committed |
| Audit & Literature | `docs/AUDIT.md`, `docs/LITERATURE.md` |

---

## 15. Team & Compliance

| Requirement | Status |
|-------------|--------|
| Team name `code0710` matches repo, docx, Kaggle | ✅ |
| All members registered on Luma | ✅ |
| All members teamed on Kaggle; description lists names + emails | ✅ |
| Submission via Kaggle Writeups before Aug 31 23:59 IST | ✅ Ready |
| Frontend contains no Bloomberg copy (LiveFire Terminal) | ✅ |

---

## 16. Appendix — Key Files Map

```
code0710/
├── arena/loop.py                    # Closed loop + tournament (697L)
├── attacks/taxonomy.json            # 14 vectors, 5 cats, signal contracts
├── attacks/redagent/core/
│   ├── constraint_engine.py         # C1–C6 gate
│   ├── transaction_weaver.py        # Plan → seeded txns
│   ├── strategy_memory.py           # SQLite ledger + SHAP notes
│   └── llm_client.py                # OpenRouter failover, fence-strip
├── defense/features/arena_features.py # 16-dim causal features
├── defense/models/backbone.py       # XGB+LR+Rules+IF, single _fuse()
├── config/rail_profiles.py          # 4 rails
├── app/api.py                       # FastAPI + WS + static
├── app/frontend/LiveFireTerminal.jsx # Dense terminal (amber-on-black)
├── evidence/                        # Committed JSON
└── tests/                           # e2e + tournament + stress
```

---

## 17. Final Statement

We built **LiveFire** not as a demo of what fraud *looks like*, but as the **measuring instrument** Mastercard needs before it lets agentic agents spend on its rails. Every claim traces to a seeded script and a committed JSON. Every weakness is labeled. Every round makes the next detector harder to evade.

There are submissions that show a model detecting fraud. Ours shows **how much a model improves when the adversary learns — and proves it on the payment rail Mastercard just launched.**

**code0710 is ready to win.**

---
*Submitted by Team code0710 — August 2026*
