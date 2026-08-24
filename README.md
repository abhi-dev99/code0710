# LiveFire 🔥

**Adversarial Co-Evolution Arena for payment fraud defense.**
Red-team agents (ox-alpha LLM) invent GenAI-powered fraud attacks → a compiler turns plans into thousands of rail-realistic transactions → a heterogeneous blue-team ensemble detects them → SHAP explains *why* → the explanations mutate the next generation of attacks. Every round is written to a **Robustness Ledger**.

> Built for the Mastercard Innovation Challenge @ Global Fintech Fest 2026.

## The loop

```
IDENTIFY   14-vector attack taxonomy (incl. agentic-payment vectors)
GENERATE   ox-alpha plans (statistical generator parameters)
           → Transaction Weaver compiles plans → constraint-checked txns (CPU, seeded)
DEFEND     XGBoost+LR ensemble + deterministic rules + entity-graph features
           + disagreement→novelty flag, threshold-calibrated to ≤2% benign FP
EXPLAIN    SHAP: why caught / why evaded → strategy memory (SQLite)
MUTATE     memory feeds the next round's red prompts → co-evolution
LEDGER     every campaign persisted; multi-rail survival comparison
```

## Quick start

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy config\settings.example.env .env   # fill in LLM_API_KEY

# 1. honest real-data anchor (ULB holdout)
python defense\train_real_backbone.py

# 2. full test suite (no LLM needed)
python tests\test_e2e.py

# 3. run the product
uvicorn app.api:app --port 8000         # open http://localhost:8000
```

## What makes it defensible

| Claim | Evidence |
|---|---|
| Real-world credibility | XGBoost on **real** ULB data: ROC-AUC 0.985 / AP 0.87 (committed split, no synthetic) |
| Novel-attack detection | **98% detection of a held-out attack vector the ensemble never saw** (cross-vector protocol), benign FP 1.2%, F1 0.92 |
| Global scale | 4 rail profiles (global card / EU-PSD2 / US-CNP / India-UPI) — same vectors, per-rail survival comparison |
| Honesty | Benign traffic bootstrapped from real corpora; arena metrics labeled as attack-detection, never conflated with real-fraud AUC (docs/AUDIT.md) |
| Literature-grounded | docs/LITERATURE.md — GraphConsis, FRAUD-RLA, ARMS, ACL'26 LLM-on-tabular findings |
| Reproducible | every weave seeded; SHA-256 data manifests; every metric from a committed script |

## Repo map

```
attacks/redagent/    red team: llm_client (failover chains, reasoning=max),
                     constraint_engine (6 realism checks × rail profiles),
                     transaction_weaver (plan→txns compiler), strategy_memory
defense/             blue team: arena_features (behavioral+velocity+graph),
                     models/backbone (ensemble), train_real_backbone.py
arena/loop.py        the closed loop + multi-rail runner
app/                 FastAPI + web dashboard (run rounds from the browser)
config/              rail profiles, settings template
data/                download + split locking (SEED=710, SHA-256 manifests)
docs/                AUDIT, LITERATURE, SPRINT_PLAN, ARCHITECTURE
tests/               stress suite (11) + e2e suite (6)
```

## Honesty protocol

Synthetic data is used **only** for attacks — that is the assignment. Benign traffic is bootstrapped from real corpora. Arena metrics measure *attack detection against real-anchored benign traffic*; real-fraud credibility comes from the ULB-native backbone. The two are never mixed. Full flaw register: `docs/AUDIT.md`.
