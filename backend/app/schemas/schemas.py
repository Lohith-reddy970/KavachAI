"""Pydantic request/response schemas for the KAVACH AI API."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str
    version: str
    app: str


class TaskCreate(BaseModel):
    document_id: Optional[int] = Field(default=None, ge=1)
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = Field(default="", max_length=5000)
    task_type: Optional[str] = None


class DocumentAnalysisRequest(TaskCreate):
    profile: str = Field(default="general", min_length=1, max_length=40)
    analysis_mode: Literal["risk_review", "summary", "extract_fields"] = "risk_review"


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
    document_id: int | None = None
    char_start: int | None = None
    char_end: int | None = None


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: list[KnowledgeSearchResult]
    total_chunks: int
    embedding_backend: str


class AgentRunRequest(BaseModel):
    document_id: int = Field(..., ge=1)
    profile: str = Field(default="general", min_length=1, max_length=40)
    analysis_mode: Literal["risk_review", "summary", "extract_fields"] = "risk_review"
    task: str = Field(..., min_length=1, max_length=2000)
    max_steps: Optional[int] = Field(default=None, ge=1, le=20)


class GenericResponse(BaseModel):
    ok: bool = True
    detail: Optional[str] = None
    data: Optional[Any] = None


class SandboxExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(..., min_length=1, max_length=65536)
    stdin: str = Field(default="", max_length=16384)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=30, strict=True)


class AnalysisJobRequest(DocumentAnalysisRequest):
    document_id: int = Field(..., ge=1)
    workflow: Literal["pipeline", "planner"] = "pipeline"
    max_steps: Optional[int] = Field(default=None, ge=1, le=20)


class BatchAnalysisRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1, max_length=50)
    profile: str = Field(default="general", min_length=1, max_length=40)
    analysis_mode: Literal["risk_review", "summary", "extract_fields"] = "risk_review"
    description: str = Field(default="Analyze this document and cite the source.", min_length=1, max_length=2000)
    request_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{8,80}$")


class PassageRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    excerpt: str = Field(..., min_length=1, max_length=3000)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=6000)


class DocumentChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    document_ids: list[int] = Field(..., min_length=1, max_length=20)
    history: list[ChatMessage] = Field(default_factory=list, max_length=8)
