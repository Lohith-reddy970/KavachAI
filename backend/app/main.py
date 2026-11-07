"""KAVACH AI - FastAPI application entrypoint.

Run:
    python -m uvicorn app.main:app --reload --port 8000   (from the backend/ dir)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .api.routes import router
from .database import db
from .security.middleware import AuditAndAirgapMiddleware, write_audit
from .services.model_catalog import refresh_models
from .models.providers import InferenceUnavailable
from .services import analysis_jobs, batch_jobs
from .services.document_store import DocumentNotFound, DocumentBusy, DocumentAccessError
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: prepare directories, schema, and configured model assignments.
    config.ensure_dirs()
    db.init_db()
    analysis_jobs.recover_interrupted()
    batch_jobs.start()
    refresh_models()
    write_audit("system.startup",
                detail=f"{config.APP_NAME} {config.VERSION} started in "
                       f"{config.KAVACH_MODE} mode.")
    yield
    batch_jobs.shutdown()
    analysis_jobs.shutdown()
    write_audit("system.shutdown", detail="Application shutting down.")


app = FastAPI(
    title=f"{config.APP_NAME} - {config.APP_TAGLINE}",
    version=config.VERSION,
    description="Private local document analysis and evidence review.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    # Local-only appliance: accept the frontend on any localhost port so the UI
    # works regardless of which dev port Next.js picks.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Kavach-Mode", "X-Kavach-Network"],
)
app.add_middleware(AuditAndAirgapMiddleware)

app.include_router(router)


@app.get("/")
def root():
    return {
        "app": config.APP_NAME,
        "tagline": config.APP_TAGLINE,
        "version": config.VERSION,
        "mode": config.KAVACH_MODE,
        "docs": "/docs",
        "health": "/api/health",
    }


@app.exception_handler(InferenceUnavailable)
async def inference_unavailable(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(DocumentNotFound)
async def document_not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DocumentBusy)
@app.exception_handler(DocumentAccessError)
async def document_unavailable(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})
