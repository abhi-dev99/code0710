# code0710 — Adversarial Co-Evolution Arena for Payment Security

> Mastercard Innovation Challenge @ GFF 2026 · AI Defense Lab for Payment Security

LLM-driven red-team agents discover and mutate GenAI payment-fraud attacks at scale; a blue-team detection ensemble defends; every round of the arms race is measured in an append-only Robustness Ledger.

## Quick start

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt

# 1. Configure LLM access (any OpenAI-compatible endpoint)
copy config\settings.example.env .env   # then edit values

# 2. Download real anchor datasets (requires free Kaggle account: kaggle.com/settings → API token)
python data\download_datasets.py

# 3. Build + lock evaluation splits from real corpora
python data\build_splits.py

# 4. Smoke-test feature extraction port
python -m defense.features.extractor --selftest
```

## Layout

```
attacks/        Red team: taxonomy, agents, generators, fidelity eval
defense/        Blue team: features, ensemble, experiments, explanations
app/            Web prototype (React + FastAPI/WebSocket arena)
data/           Dataset acquisition + split locking (real-data anchored)
docs/           Walkthrough source, compliance notes, ethics statement
experiments/    Load tests, ablations, headline experiment harness
vendor/argus/   Vendored ARGUS modules (feature extractor, UPI patterns, txn simulator)
```

## Data provenance policy

Benign-traffic statistics are fitted to REAL datasets (ULB creditcardfraud, IEEE-CIS/Vesta) and RBI/NPCI published statistics. Synthetic generation is used ONLY for attack campaigns — that is the assignment — and every artifact carries a `provenance` record. No reported metric is trained AND tested purely on self-generated data.

## Safety & ethics

All simulation runs against synthetic-only identities in a sandboxed ledger. No real PII, no operational phishing targets. This system is authorized security research for defensive purposes: a pre-deployment stress-testing platform for payment fraud models.
