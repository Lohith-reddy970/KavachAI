"""System-status service for KAVACH AI.

Reports real local hardware metrics when they can be detected (GPU through
``nvidia-smi``; CPU and RAM through the import-guarded ``psutil`` package) and
reports unavailable metrics as null. All probing is local
and cached briefly so the endpoint stays fast.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from typing import Any

from .. import config
from ..database import db
from ..rag.pipeline import backend_info
from ..security import sandbox
from . import document_analysis

try:  # import-guarded: the app starts even when psutil is absent
    import psutil  # type: ignore
except Exception:  # noqa: BLE001
    psutil = None

_SMI_TIMEOUT_S = 2.0
_SMI_CACHE_S = 5.0
_smi_cache: dict[str, Any] | None = None
_smi_cache_at = 0.0


def _nvidia_gpu() -> dict[str, Any] | None:
    """Query the local NVIDIA GPU; returns ``None`` when unavailable."""
    global _smi_cache, _smi_cache_at
    now = time.time()
    if _smi_cache is not None and now - _smi_cache_at < _SMI_CACHE_S:
        return _smi_cache
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        result = subprocess.run(
            [exe, "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=_SMI_TIMEOUT_S, check=False,
        )
        first = (result.stdout or "").strip().splitlines()[0]
        name, total_mb, used_mb, util, temp = [part.strip() for part in first.split(",")]
        total_mb_f, used_mb_f = float(total_mb), float(used_mb)
        _smi_cache = {
            "name": name,
            "utilization_pct": round(float(util), 1),
            "temperature_c": round(float(temp), 1),
            "memory_total_gb": round(total_mb_f / 1024, 1),
            "memory_used_gb": round(used_mb_f / 1024, 1),
            "memory_used_pct": round(100 * used_mb_f / total_mb_f, 1) if total_mb_f else 0.0,
        }
        _smi_cache_at = now
        return _smi_cache
    except Exception:  # noqa: BLE001 - a hardware probe must never break status
        return None


def _cpu_ram() -> tuple[float | None, float | None]:
    """Return (cpu_percent, ram_percent) when psutil is available."""
    if psutil is None:
        return None, None
    try:
        return (round(float(psutil.cpu_percent(interval=None)), 1),
                round(float(psutil.virtual_memory().percent), 1))
    except Exception:  # noqa: BLE001
        return None, None


def snapshot() -> dict:
    models = db.fetch_all("SELECT name, status FROM models")
    online = sum(1 for m in models if m["status"] == "online")
    ocr = document_analysis.ocr_status()
    real_gpu = _nvidia_gpu()
    cpu_pct, ram_pct = _cpu_ram()
    if real_gpu:
        gpu: dict[str, Any] = {**real_gpu, "device": real_gpu["name"], "source": "hardware"}
    else:
        gpu = {
            "utilization_pct": None,
            "memory_used_pct": None,
            "temperature_c": None,
            "device": "GPU telemetry unavailable",
            "source": "unavailable",
        }
    return {
        "mode": config.KAVACH_MODE,
        "network": "airgapped (application provider restrictions)" if config.IS_AIRGAPPED else "open",
        "gpu": gpu,
        "cpu": {
            "utilization_pct": cpu_pct,
            "source": "hardware" if cpu_pct is not None else "unavailable",
        },
        "ram": {
            "utilization_pct": ram_pct,
            "source": "hardware" if ram_pct is not None else "unavailable",
        },
        "models": {
            "online": online,
            "total": len(models),
            "list": models,
        },
        "vector_db": {
            "status": "online",
            "backend": backend_info()["vector_backend"],
        },
        "ocr": {
            "status": ocr["status"],
            "engine": ocr["engine"],
            "reason": ocr["reason"],
            "pdf_renderer_available": ocr["pdf_renderer_available"],
        },
        "sandbox": sandbox.status(),
        "documents": db.count("documents"),
        "runs": db.count("agent_runs"),
    }
