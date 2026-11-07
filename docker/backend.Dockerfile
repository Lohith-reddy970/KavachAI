# KAVACH AI — backend image. Build context is the repo root.
FROM python:3.11-slim

WORKDIR /app

# Tesseract runs entirely inside the backend container for uploaded scans.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Core + offline-friendly optional deps. RAG falls back to pure-python if the
# heavy vector-store libs are absent, so we keep the image lean.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/

WORKDIR /app/backend

ENV KAVACH_MODE=airgapped \
    KAVACH_DATA=/app/data \
    KAVACH_UPLOADS=/app/data/uploads \
    KAVACH_GENERATED=/app/generated \
    KAVACH_DB=/app/data/kavach.db \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
