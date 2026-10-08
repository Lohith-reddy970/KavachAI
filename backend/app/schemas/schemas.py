"""Pydantic request/response schemas for the KAVACH AI API."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str
    version: str
    app: str


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = Field(default="", max_length=5000)
    task_type: Optional[str] = None


class DocumentAnalysisRequest(TaskCreate):
    profile: str = Field(default="general", min_length=1, max_length=40)
    analysis_mode: Literal["risk_review", "summary", "extract_fields"] = "risk_review"


class DemoRunRequest(BaseModel):
    scenario: Optional[str] = "refinery_inspection"


class ReviewRequest(BaseModel):
    note: Optional[str] = Field(default="", max_length=2000)
    reviewer: Optional[str] = "reviewer@kavach.local"


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=4, ge=1, le=10)


class KnowledgeSearchResult(BaseModel):
    id: str
    source: str
    page: int
    text: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: list[KnowledgeSearchResult]
    total_chunks: int
    embedding_backend: str


class AgentRunRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=2000)
    max_steps: Optional[int] = Field(default=None, ge=1, le=20)


class GenericResponse(BaseModel):
    ok: bool = True
    detail: Optional[str] = None
    data: Optional[Any] = None
