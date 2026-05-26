"""bago.api.models.schemas — Pydantic request/response schemas para BAGO API."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    role: str = "user"
    content: str
    images: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    model: str = ""
    messages: list[ChatMessage]
    system: str = ""
    template: str = ""
    stream: bool = False
    options: dict = Field(default_factory=dict)
    provider: str = ""
    quality_guard: Optional[bool] = None
    context_escalation: Optional[bool] = None
    max_switches: Optional[int] = None


class ChatResponse(BaseModel):
    model: str
    provider: str
    message: ChatMessage
    done: bool = True
    total_duration: int = 0
    eval_count: int = 0
    eval_duration: int = 0
    load_duration: int = 0
    prompt_eval_count: int = 0
    prompt_eval_duration: int = 0
    switches: int = 0
    original_model: str = ""
    original_provider: str = ""
    route_reason: str = ""


class GenerateRequest(BaseModel):
    model: str = ""
    prompt: str
    system: str = ""
    template: str = ""
    context: list[int] = Field(default_factory=list)
    stream: bool = False
    raw: bool = False
    options: dict = Field(default_factory=dict)
    provider: str = ""
    quality_guard: Optional[bool] = None


class GenerateResponse(BaseModel):
    model: str
    provider: str
    response: str
    done: bool = True
    total_duration: int = 0
    eval_count: int = 0
    switches: int = 0
    original_model: str = ""
    route_reason: str = ""


class EmbedRequest(BaseModel):
    model: str = ""
    input: str | list[str]
    options: dict = Field(default_factory=dict)


class EmbedResponse(BaseModel):
    model: str
    embeddings: list[list[float]]
    total_duration: int = 0
    load_duration: int = 0
    prompt_eval_count: int = 0


class ModelInfo(BaseModel):
    name: str
    model: str = ""
    modified_at: str = ""
    size: int = 0
    digest: str = ""
    details: dict = Field(default_factory=dict)
    provider: str = ""
    best_for: str = ""
    installed: bool = False
    compat_level: str = ""


class TagsResponse(BaseModel):
    models: list[ModelInfo] = Field(default_factory=list)


class ShowRequest(BaseModel):
    model: str
    verbose: bool = False


class ShowResponse(BaseModel):
    modelfile: str = ""
    parameters: str = ""
    template: str = ""
    system: str = ""
    details: dict = Field(default_factory=dict)
    provider: str = ""
    routing: dict = Field(default_factory=dict)
    fallback: str = ""
    quality_guard: bool = True
    compat_level: str = ""
    catalog_entry: dict = Field(default_factory=dict)


class RunningModel(BaseModel):
    name: str
    model: str = ""
    provider: str = ""
    size: int = 0
    digest: str = ""
    expires_at: str = ""
    size_vram: int = 0


class PsResponse(BaseModel):
    models: list[RunningModel] = Field(default_factory=list)


class CreateRequest(BaseModel):
    name: str
    modelfile: str = ""
    path: str = ""


class CreateResponse(BaseModel):
    status: str = "success"
    name: str = ""


class CopyRequest(BaseModel):
    source: str
    destination: str


class CopyResponse(BaseModel):
    status: str = "success"


class PullRequest(BaseModel):
    model: str
    insecure: bool = False
    stream: bool = True


class PushRequest(BaseModel):
    model: str
    insecure: bool = False
    stream: bool = True


class ProgressResponse(BaseModel):
    status: str
    digest: str = ""
    total: int = 0
    completed: int = 0


class DeleteRequest(BaseModel):
    model: str


class RouteRequest(BaseModel):
    prompt: str
    model: str = ""
    provider: str = ""


class RouteResponse(BaseModel):
    provider: str
    model: str
    wire_name: str
    reason: str
    rule_id: str = ""
    fallback_available: list[dict] = Field(default_factory=list)
    quality_guard: bool = True
    context_escalation: bool = True


class ProviderHealth(BaseModel):
    name: str
    available: bool
    models: int = 0
    latency_ms: float = 0
    error: str = ""


class HealthResponse(BaseModel):
    score: int = 0
    providers: list[ProviderHealth] = Field(default_factory=list)
    version: str = ""


class EscalateRequest(BaseModel):
    session_id: str = ""
    target_provider: str = ""
    target_model: str = ""


class EscalateResponse(BaseModel):
    provider: str
    model: str
    reason: str = ""


class SessionCreateRequest(BaseModel):
    model: str = ""
    provider: str = ""
    system: str = ""


class SessionInfo(BaseModel):
    id: str
    provider: str
    model: str
    switches: int = 0
    messages: int = 0
    created_at: str = ""


class SessionResponse(BaseModel):
    session: SessionInfo


class VersionResponse(BaseModel):
    bago_version: str
    api_version: str = "1.0.0"
    ollama_version: str = ""
