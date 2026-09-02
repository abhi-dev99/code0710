# LiveFire — Adversarial Co-Evolution Arena
# Clone -> one command -> arena:
#   docker compose up --build
# then open http://127.0.0.1:8000 — the LiveFire Terminal, the one frontend
# (the plain dashboard is deprecated and no longer part of the image)

# ---- stage 1: build the terminal (the only frontend now) ----
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci
COPY app/frontend/ ./
RUN npm run build

# ---- stage 2: python runtime ----
FROM python:3.12-slim

WORKDIR /app

# system deps: none beyond slim; XGBoost/scikit wheels cover linux x86_64
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# overwrite the source frontend dir with the built one so app/api.py's
# app/frontend/dist lookup finds real assets, not source .jsx
COPY --from=frontend-build /frontend/dist ./app/frontend/dist

# data splits are gitignored — build them if present, else the arena still
# runs (benign generator falls back to uniform pools with a warning)
RUN python data/build_splits.py || echo "[docker] splits not available - run data/download_datasets.py for real-corpus anchoring"

# ensure ledger directory exists on the mounted volume
RUN mkdir -p /app/data/ledger

ENV PORT=8000
EXPOSE 8000 8080
CMD ["sh", "-c", "python -m uvicorn app.api:app --host 0.0.0.0 --port ${PORT}"]
