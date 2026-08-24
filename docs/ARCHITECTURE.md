# Architecture — LiveFire

## Component graph

```
                    ┌──────────────────────────────┐
                    │   attacks/taxonomy.json      │  14 vectors, 5 categories
                    │   (incl. agentic D1–D3)      │
                    └──────────────┬───────────────┘
                                   ▼
┌──────────── RED (ox-alpha, reasoning=max) ────────────────────────────────┐
│ llm_client.py     tiered routing, failover chains, 429 circuit breaker    │
│ arena/loop.py     mutation-aware planner prompt ← strategy_memory (SQLite)│
│   → plan JSON: {channel, structuring ladder, inter-arrival dist,          │
│     entity cardinality, jitter, window}  ← statistical parameters only    │
└──────────────────────────────┬────────────────────────────────────────────┘
                               ▼
┌──────────── WEAVER (CPU, seeded, no LLM) ─────────────────────────────────┐
│ transaction_weaver.py                                                     │
│   plan validation → entity pools → amount ladder + jitter →               │
│   inter-arrival sampling → tz-aware timestamps → home-city geo →          │
│   per-txn CONSTRAINT ENGINE gate (6 checks × rail profile)                │
│ rail_profiles.py  card_intl | eu_psd2 | us_cnp | upi_in                   │
└──────────────────────────────┬────────────────────────────────────────────┘
                               ▼
┌──────────── BLUE (heterogeneous ensemble) ────────────────────────────────┐
│ arena_features.py behavioral + causal velocity windows + entity-graph     │
│                   fan-out (15 dims, stationary by design)                 │
│ models/backbone.py XGB (55%) + LR (25%) + rules (20%) fusion              │
│   threshold calibrated on a HELD-OUT benign slice → ≤2% benign FP         │
│   disagreement → novelty flag (suspicious-but-under-threshold)            │
└──────────────────────────────┬────────────────────────────────────────────┘
                               ▼
┌──────────── EXPLAIN + REMEMBER ───────────────────────────────────────────┐
│ SHAP TreeExplainer → top-k feature reasons per caught campaign            │
│ strategy_memory.py campaigns + rounds tables (SQLite)                     │
│   → vector report card (attempts, avg detection)                          │
│   → next round's planner prompt includes mutation context                 │
└──────────────────────────────┬────────────────────────────────────────────┘
                               ▼
┌──────────── SURFACES ─────────────────────────────────────────────────────┐
│ app/api.py   FastAPI: /api/round /api/multi-rail /api/detect /api/ledger  │
│ app/static   dark dashboard: run rounds, live results, ledger, why        │
└───────────────────────────────────────────────────────────────────────────┘
```

## Evaluation protocol (the honesty core)

1. **Real-data credibility** — `defense/train_real_backbone.py`: XGBoost on the
   real ULB corpus, native features, committed split. Result: ROC-AUC 0.9852,
   AP 0.8738. This is the number that says "the ML works on real fraud."
2. **Arena detection** — `arena/loop.py` cross-vector protocol: ensemble trains
   on attacks from k−1 vectors, evaluated on a **held-out vector it has never
   seen**. Result: 92–98% detection at ≤1.3% benign FP, F1 0.92.
3. The two are reported separately, always. Arena metrics measure synthetic-
   attack detection against real-anchored benign traffic — never presented as
   real-fraud performance. (This avoids the fatal training/serving skew that
   invalidated the vendored ARGUS metrics — see docs/AUDIT.md.)

## Key invariants

- No transaction reaches the blue team without passing the constraint engine.
- Every weave is seeded → byte-reproducible campaigns.
- Benign traffic is bootstrapped from real corpora (amounts + hour-of-day from
  ULB); users are home-city anchored; travel is rare and time-coherent.
- Threshold calibration uses a dedicated benign slice — never the training set.
- Graph/velocity features are causal windows (stationary), not cumulative counts.

## Failure modes considered

| Failure | Mitigation |
|---|---|
| LLM quota exhaustion / upstream 429 | deterministic template plans; failover model chains |
| LLM emits unweaveable plan | schema validation → template fallback, logged |
| LLM refuses "attack plan" framing | generator-parameters interface (sanctioned-benchmark framing) |
| Label/row misalignment in features | build_features returns original stream order (tested) |
| Feature drift across slices | causal windowed features; drift checked in dev |
| FP explosion | held-out benign calibration slice, target ≤2% |
| In-sample detection inflation | cross-vector holdout protocol; in-sample rates labeled |
