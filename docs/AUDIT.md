# AUDIT — Vendored ARGUS code & livefire foundations

Date: 2026-08-24. Auditor stance: hostile review. Every finding below is either FIXED,
POLICY-GATED, or ACCEPTED-WITH-DOCUMENTATION.

## A. Inherited flaws from ARGUS (vendored code)

| # | Finding | Severity | Disposition |
|---|---|---|---|
| A1 | **Training/serving skew**: behavioral features (`txn_velocity`, `amount_velocity`, `amount_zscore`, `amount_deviation_ratio`, `daily_cumulative_ratio`, `is_unusual_channel`) silently default to constants when no user profile is passed. ARGUS trained row-wise without profiles → 6 of 34 features were constants in training but real values at inference. Model learned noise; metrics were inflated. | 🔴 CRITICAL | **POLICY**: our training pipeline MUST pass real profiles for every row; runtime scoring path must construct profiles identically. Enforced by assertion in `defense/features` (Phase C). If a profile is unavailable at serve time, the feature vector is flagged `profile_missing=true` and evaluated separately — never mixed into headline metrics. |
| A2 | Dead feature: `balance_delta_ratio` hardcoded to `0.0`. | 🟠 | Kept for now (positional parity with vendored extractor), documented as constant; candidate for removal before final model. |
| A3 | Two divergent sources of truth: `vendor/argus/backend/ml/dataset_config.py::CHANNELS` vs `vendor/argus/backend/simulator/transaction_gen.py::CHANNELS` disagree on valid channel-category pairs and city weight tables. Generator and scorer can contradict each other. | 🟠 | **RULE**: `dataset_config.py` is the ONLY config authority. Our generator (Phase B) imports from it; `transaction_gen.py` is quarantined — reference only, never imported by pipeline code. |
| A4 | Silent timestamp corruption: bare `except Exception` → invalid timestamps become `datetime.now()`, silently distorting temporal features. | 🟠 | Generator validates timestamps at construction (constraint engine, Phase B). Extractor behavior noted; not modified (vendored parity). |
| A5 | "Calibrated to NPCI/RBI/FIU" claims include unverifiable items ("RBI April 2026 proposed cooling period"). | 🟡 | Treat ALL vendor constants as engineering heuristics. Docx may only cite limits we independently verify against NPCI/RBI primary sources. |
| A6 | `is_round_structuring_amount` uses exact float equality against 7 hardcoded amounts — trivially gameable, rule-in-disguise. | 🟡 | Documented; red agents SHOULD exploit such brittle features during co-evolution — that's the point of the arena. |
| A7 | `merchant_risk_score` silently defaults 0.15 when absent. | 🟡 | Same treatment as A1 family: missing-data flags, no silent defaults in our own code paths. |
| A8 | `extract_features_batch` is row-wise Python looping (~1k txn/s). Unusable at our throughput targets. | 🟠 | Superseded: hot-path batch featurization is Phase C work (vectorized numpy); `defense/features/hotpath.py`. |

## B. Flaws found in livefire's own first-pass code (all FIXED)

| # | Finding | Fix |
|---|---|---|
| B1 | `build_splits.py` wrote `.parquet` without `pyarrow` dependency → guaranteed crash. | Added `pyarrow>=15.0` (+`scipy` for later KS-tests) to requirements. |
| B2 | IEEE-CIS split was label-stratified RANDOM → ignores time ordering → leakage-by-time risk. | Replaced with **temporal split** (train = earliest 80% by `TransactionDT`, test = latest 20%), matching deployment reality. ULB keeps stratified-random (its 2-day window has no usable time axis). Split method recorded in manifest. |
| B3 | `download_datasets.py` loaded multi-hundred-MB files fully into RAM (`read_bytes`). | `shutil.copyfile`. |
| B4 | IEEE-CIS download fails unless Kaggle competition rules were accepted in-browser by the token owner. Silent failure mode. | Explicit comment + error-surfacing note in script. |
| B5 | `llm_client.complete_many`: one failed prompt raised through `asyncio.gather`, losing all sibling results — unacceptable for bulk generation. | Per-prompt isolation: failures return `None`, logged, siblings survive. |
| B6 | `llm_client` model fallback used `next()` over possibly-empty filter → `StopIteration`; 429 `Retry-After` header ignored; zero usage observability. | `_fallback_model()` raising clean `LLMError`; Retry-After honored; token usage logged per call. |

## C. Validation status

- Extractor facade selftest: PASS (34 features; new-device/night/cross-state/composite-risk spot-checks).
- All modules AST-parse clean.
- NOT yet validated: dataset download (needs Kaggle token), LLM client live call (needs key), splits build (needs datasets).

## D. Standing rules resulting from this audit

1. No silent defaults in any livefire-original feature path.
2. Profiles mandatory in train AND serve; missing-profile rows reported separately.
3. `dataset_config.py` is sole config authority; `transaction_gen.py` quarantined.
4. Temporal splits wherever a time axis exists.
5. Every metric-generating script committed alongside its manifest/hashes.
