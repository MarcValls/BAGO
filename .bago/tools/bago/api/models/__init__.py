"""bago.api.models — Schemas and BAGOMODEL spec."""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .bagomodel import (
    BagoModel, VALID_PARAMS,
    parse_bagomodel, load_bagomodel, save_bagomodel,
)
from .schemas import (
    ChatMessage, ChatRequest, ChatResponse,
    GenerateRequest, GenerateResponse,
    EmbedRequest, EmbedResponse,
    ModelInfo, TagsResponse,
    ShowRequest, ShowResponse,
    RunningModel, PsResponse,
    CreateRequest, CreateResponse,
    CopyRequest, CopyResponse,
    PullRequest, PushRequest, ProgressResponse,
    DeleteRequest,
    RouteRequest, RouteResponse,
    ProviderHealth, HealthResponse,
    EscalateRequest, EscalateResponse,
    SessionCreateRequest, SessionInfo, SessionResponse,
    VersionResponse,
)
