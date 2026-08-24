# FINAL SPRINT PLAN — End-to-End Product (branch: sprint/final-e2e)

Deadline: Aug 31. Tonight: build the complete closed-loop product.

## Decision framework (applied to every choice)
Right for purpose? Innovative? Global-production scale? Relevant? Failure modes accounted for? **Will it win?**

## Architecture delivered by this sprint

```
┌─────────────────────────── ARENA (closed loop) ───────────────────────────┐
│                                                                           │
│  RED (ox-alpha @ max effort)          BLUE (heterogeneous ensemble)       │
│  ├─ taxonomy (14 vectors)             ├─ backbone: XGBoost + LR (SHAP)    │
│  ├─ strategy planner → plan JSON      ├─ graph tier: networkx entity      │
│  ├─ transaction_weaver (plan→txns)    │   graph features → GBDT           │
│  ├─ constraint_engine (rail profiles) ├─ rules tier: deterministic checks │
│  ├─ strategy_memory (SQLite)          ├─ meta: disagreement→novelty flag  │
│  └─ SHAP-feedback mutation loop       └─ honest dual evaluation (below)   │
│                                                                           │
│  ROBUSTNESS LEDGER: every round logged — attack, detection, why           │
└───────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   FastAPI + web UI (competition requires working web prototype)
```

## Data honesty (non-negotiable, per docs/AUDIT.md)
- Benign traffic anchored to REAL corpora (ULB EU-card, IEEE-CIS global). Synthetic ONLY for attacks.
- Dual evaluation, explicitly reported:
  1. **Real-data metrics**: backbone trained/tested on native ULB splits (AUC/PR on honest holdout).
  2. **Arena metrics**: detection of synthetic attacks vs real benign traffic on the 34-feature schema.
  - The ledger states plainly that arena metrics measure attack-detection, not real-world fraud AUC (avoids ARGUS's fatal training/serving skew).

## Rail profiles (global expansion, judge-aligned)
- `card_intl` (Mastercard-flavored default), `upi_in`, `eu_psd2` (SCA step-up mechanic), `us_cnp` (no SCA).
- Constraint engine parameterized; same arena runs per profile; ledger compares attack survival per rail.

## Milestones (commit after each)
1. [x] Branch + sprint plan
2. [ ] Rail profiles + constraint engine parameterization
3. [ ] transaction_weaver (plan JSON → constraint-checked txns, seeded, provenance-tagged)
4. [ ] strategy_memory (SQLite: campaigns, rounds, outcomes)
5. [ ] Red agent orchestrator (plan → weaver → campaign; SHAP mutation loop)
6. [ ] Blue backbone (XGBoost+LR) + honest ULB training script + metrics
7. [ ] Graph tier (networkx entity-graph features) + rules tier + disagreement meta
8. [ ] SHAP explainer → mutation feedback
9. [ ] Arena loop + Robustness Ledger
10. [ ] FastAPI + web UI (dashboard, live round runner, ledger view)
11. [ ] E2E test + full docs (README, ARCHITECTURE, FEATURES)
12. [ ] Merge-ready: green tests, clean docs

## Stretch (only if core is green)
- GNN tier via torch/PyG; multi-rail ledger comparison UI
