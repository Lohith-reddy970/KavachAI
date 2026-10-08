"""KAVACH AI - Central configuration.

All settings are environment-driven with safe offline defaults. This module is
import-safe (no heavy deps) so the app can start with only the core packages.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Version / identity --------------------------------------------------------
VERSION = "1.0.0-prototype"
APP_NAME = "KAVACH AI"
APP_TAGLINE = "Sovereign On-Premise Agentic AI Workbench"

# --- Paths --------------------------------------------------------------------
# backend/app/config.py -> backend/app -> backend -> repository root
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

DEMO_DATA_DIR = Path(os.getenv("KAVACH_DEMO_DATA", str(REPO_ROOT / "demo-data")))
UPLOADS_DIR = Path(os.getenv("KAVACH_UPLOADS", str(DEMO_DATA_DIR / "uploads")))
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
# Ollama uses the locally installed models for each role. The mock provider is
# still available for deterministic demos and tests. OLLAMA_MODEL is retained as
# a compatibility override for the non-reasoning/non-vision text role.
_PROVIDER_ALIASES = {"mock": "mock-local", "mock-local": "mock-local", "ollama": "ollama"}
INFERENCE_PROVIDER = _PROVIDER_ALIASES.get(
    os.getenv("KAVACH_INFERENCE_PROVIDER", "ollama").strip().lower(), "mock-local")
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

# --- Agentic planner ----------------------------------------------------------
PLANNER_MAX_STEPS = int(os.getenv("KAVACH_PLANNER_MAX_STEPS", "10"))
PLANNER_HARD_STEP_CAP = 20
# Findings below this confidence always require human approval.
REVIEW_MIN_CONFIDENCE = float(os.getenv("KAVACH_REVIEW_MIN_CONFIDENCE", "75"))
HIGH_RISK_SEVERITIES = {"high", "critical"}


def ensure_dirs() -> None:
    """Create all runtime directories (idempotent)."""
    for d in (DEMO_DATA_DIR, UPLOADS_DIR, GENERATED_DIR):
        d.mkdir(parents=True, exist_ok=True)
