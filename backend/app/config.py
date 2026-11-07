"""KAVACH AI - Central configuration.

All settings are environment-driven with safe offline defaults. This module is
import-safe (no heavy deps) so the app can start with only the core packages.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Version / identity --------------------------------------------------------
VERSION = "1.0.0"
APP_NAME = "KAVACH AI"
APP_TAGLINE = "Sovereign On-Premise Agentic AI Workbench"

# --- Paths --------------------------------------------------------------------
# backend/app/config.py -> backend/app -> backend -> repository root
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

DATA_DIR = Path(os.getenv("KAVACH_DATA", str(REPO_ROOT / "data")))
UPLOADS_DIR = Path(os.getenv("KAVACH_UPLOADS", str(DATA_DIR / "uploads")))
GENERATED_DIR = Path(os.getenv("KAVACH_GENERATED", str(REPO_ROOT / "generated")))
DB_PATH = Path(os.getenv("KAVACH_DB", str(BACKEND_DIR / "kavach.db")))

# --- Security / mode ----------------------------------------------------------
KAVACH_MODE = os.getenv("KAVACH_MODE", "airgapped").strip().lower()
IS_AIRGAPPED = KAVACH_MODE == "airgapped"

# File-upload policy
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "docx", "csv", "py"}
MAX_UPLOAD_BYTES = int(os.getenv("KAVACH_MAX_UPLOAD_MB", "25")) * 1024 * 1024

# CORS
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

# Providers that are considered "external" and thus blocked in airgapped mode.
EXTERNAL_PROVIDERS = {"openai", "anthropic", "gemini", "google", "azure", "cohere", "bedrock"}


# --- Local inference ----------------------------------------------------------
# Reject invalid settings rather than substituting fabricated inference.
INFERENCE_PROVIDER = os.getenv("KAVACH_INFERENCE_PROVIDER", "ollama").strip().lower()
if INFERENCE_PROVIDER not in {"ollama", "transformers"}:
    raise ValueError("KAVACH_INFERENCE_PROVIDER must be ollama or transformers")
# Hash embeddings perform real local lexical retrieval without a model server.
# Select provider explicitly to use learned embeddings; failures are surfaced.
EMBEDDING_BACKEND = os.getenv("KAVACH_EMBEDDING_BACKEND", "hash").strip().lower()
if EMBEDDING_BACKEND not in {"hash", "provider"}:
    raise ValueError("KAVACH_EMBEDDING_BACKEND must be hash or provider")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "qwen3:8b").strip()
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b").strip()
OLLAMA_OTHER_MODEL = os.getenv(
    "OLLAMA_OTHER_MODEL", os.getenv("OLLAMA_MODEL", "llama3.2:3b")
).strip()
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest").strip()
# Legacy alias used by older integrations.
OLLAMA_MODEL = OLLAMA_OTHER_MODEL
OLLAMA_MODEL_BY_ROLE = {
    "reasoning": OLLAMA_REASONING_MODEL,
    "vision": OLLAMA_VISION_MODEL,
    "other": OLLAMA_OTHER_MODEL,
}
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_S", "120"))

# --- Hugging Face Transformers (strictly local paths; no Hub downloads) --------
TRANSFORMERS_MODEL_PATH = os.getenv("KAVACH_TRANSFORMERS_MODEL_PATH", "").strip()
TRANSFORMERS_EMBED_MODEL_PATH = os.getenv(
    "KAVACH_TRANSFORMERS_EMBED_MODEL_PATH", "").strip()
TRANSFORMERS_DEVICE = os.getenv("KAVACH_TRANSFORMERS_DEVICE", "auto").strip().lower()
TRANSFORMERS_MAX_NEW_TOKENS = max(
    1, min(2048, int(os.getenv("KAVACH_TRANSFORMERS_MAX_NEW_TOKENS", "256"))))
TRANSFORMERS_MAX_INPUT_TOKENS = max(
    128, min(32768, int(os.getenv("KAVACH_TRANSFORMERS_MAX_INPUT_TOKENS", "4096"))))

# --- Local OCR ----------------------------------------------------------------
# pytesseract is a Python wrapper; the Tesseract executable and trained language
# data remain local system dependencies. PyMuPDF is used only to rasterize PDFs.
OCR_TESSERACT_CMD = os.getenv("KAVACH_TESSERACT_CMD", "").strip()
OCR_LANGUAGE = os.getenv("KAVACH_OCR_LANGUAGE", "eng").strip() or "eng"
OCR_TESSERACT_CONFIG = os.getenv("KAVACH_OCR_TESSERACT_CONFIG", "--psm 3").strip()
OCR_DPI = max(72, min(600, int(os.getenv("KAVACH_OCR_DPI", "200"))))
OCR_MIN_PDF_TEXT_CHARS = max(0, int(os.getenv("KAVACH_OCR_MIN_PDF_TEXT_CHARS", "20")))
OCR_REVIEW_MIN_CONFIDENCE = float(os.getenv("KAVACH_OCR_REVIEW_MIN_CONFIDENCE", "70"))

# --- Agentic planner ----------------------------------------------------------
PLANNER_MAX_STEPS = int(os.getenv("KAVACH_PLANNER_MAX_STEPS", "10"))
PLANNER_HARD_STEP_CAP = 20
# Findings below this confidence always require human approval.
REVIEW_MIN_CONFIDENCE = float(os.getenv("KAVACH_REVIEW_MIN_CONFIDENCE", "75"))
HIGH_RISK_SEVERITIES = {"high", "critical"}

# --- Isolated Python execution ------------------------------------------------
SANDBOX_ENABLED = os.getenv("KAVACH_SANDBOX_ENABLED", "true").lower() == "true"
SANDBOX_IMAGE = os.getenv("KAVACH_SANDBOX_IMAGE", "kavach-sandbox:1").strip()
# On Windows, use an installed Linux Docker engine through this WSL distribution.
SANDBOX_WSL_DISTRO = os.getenv("KAVACH_SANDBOX_WSL_DISTRO", "").strip()
SANDBOX_DOCKER = os.getenv("KAVACH_SANDBOX_DOCKER", "docker").strip()
SANDBOX_DOCKER_HOST = os.getenv(
    "KAVACH_SANDBOX_DOCKER_HOST",
    "npipe:////./pipe/docker_engine" if os.name == "nt" and not SANDBOX_WSL_DISTRO
    else "unix:///var/run/docker.sock",
).strip()
SANDBOX_TIMEOUT_S = max(1, min(30, int(os.getenv("KAVACH_SANDBOX_TIMEOUT_S", "10"))))
SANDBOX_MEMORY_MB = max(64, min(512, int(os.getenv("KAVACH_SANDBOX_MEMORY_MB", "128"))))
SANDBOX_MAX_OUTPUT_BYTES = 65536
SANDBOX_MAX_CODE_BYTES = 65536


def ensure_dirs() -> None:
    """Create all runtime directories (idempotent)."""
    for d in (DATA_DIR, UPLOADS_DIR, GENERATED_DIR, DB_PATH.parent):
        d.mkdir(parents=True, exist_ok=True)
