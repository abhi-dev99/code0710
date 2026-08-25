# LiveFire — Adversarial Co-Evolution Arena
# Clone -> one command -> arena:
#   docker compose up --build
# then open http://127.0.0.1:8000
FROM python:3.12-slim

WORKDIR /app

# system deps: none beyond slim; XGBoost/scikit wheels cover linux x86_64
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# data splits are gitignored — build them if present, else the arena still
# runs (benign generator falls back to uniform pools with a warning)
RUN python data/build_splits.py || echo "[docker] splits not available - run data/download_datasets.py for real-corpus anchoring"

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
