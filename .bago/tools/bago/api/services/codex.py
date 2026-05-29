"""bago.api.services.codex — Proxy Codex por codex CLI en puerto 11437.

Chat y generate usan la sesión de `codex login`.
Embeddings siguen usando OpenAI API si hace falta.
"""

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

import json
import os
import time
import urllib.request
import urllib.error

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bago.codex_auth import resolve_openai_credential
from bago.codex_runtime import codex_cli_available, run_codex_exec
from bago.cwd import get_user_cwd
from bago.ollama_runtime import DEFAULT_BAGO_CODEX_PORT, env_port
from bago.providers import resolve_codex_route_candidates

# ─── Config ────────────────────────────────────────────────────────────────────

CODEX_PORT = env_port("BAGO_CODEX_PORT", "BAGO_PORT", default=DEFAULT_BAGO_CODEX_PORT)
OPENAI_URL = "https://api.openai.com"
PROVIDER_NAME = "codex"

# ─── Models ───────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = "user"
    content: str

class ChatRequest(BaseModel):
    model: str = "gpt-5.4"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    system: str = ""
    options: dict = Field(default_factory=dict)

class GenerateRequest(BaseModel):
    model: str = "gpt-5.4"
    prompt: str
    system: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    options: dict = Field(default_factory=dict)

class EmbedRequest(BaseModel):
    model: str = "text-embedding-3-small"
    input: str | list[str]

class ModelInfo(BaseModel):
    name: str
    wire_name: str
    best_for: str = ""
    max_prompt_tokens: int = 128000
    max_output_tokens: int = 8192
    cost: str = "openai_credits"

class TagsResponse(BaseModel):
    models: list[ModelInfo] = Field(default_factory=list)

# ─── Codex models registry ────────────────────────────────────────────────────

CODEX_MODELS = {
    "gpt-5.5": ModelInfo(name="gpt-5.5", wire_name="gpt-5.5", best_for="complex_coding", max_output_tokens=16384, cost="openai_credits"),
    "gpt-5.4": ModelInfo(name="gpt-5.4", wire_name="gpt-5.4", best_for="everyday_coding", max_output_tokens=16384, cost="openai_credits"),
    "gpt-5.4-mini": ModelInfo(name="gpt-5.4-mini", wire_name="gpt-5.4-mini", best_for="fast_coding", max_output_tokens=16384, cost="openai_credits"),
    "gpt-5.3-codex": ModelInfo(name="gpt-5.3-codex", wire_name="gpt-5.3-codex", best_for="coding_optimized", max_output_tokens=16384, cost="openai_credits"),
    "gpt-5.2": ModelInfo(name="gpt-5.2", wire_name="gpt-5.2", best_for="long_running", cost="openai_credits"),
}

# ─── Client ────────────────────────────────────────────────────────────────────

def _get_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise HTTPException(status_code=401, detail="OPENAI_API_KEY not set")
    return key


def _codex_login_ready() -> bool:
    credential, mode = resolve_openai_credential()
    return bool(credential) and mode == "oauth"


def _usage_count(usage: dict, *keys: str) -> int:
    if not usage:
        return 0
    for key in keys:
        value = usage.get(key) if isinstance(usage, dict) else getattr(usage, key, None)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _run_codex_chat(model: str, messages: list[dict]) -> tuple[str, dict, dict]:
    candidates = resolve_codex_route_candidates(model)
    if not candidates:
        credential, mode = resolve_openai_credential()
        if not credential or mode != "oauth":
            raise HTTPException(status_code=401, detail="codex login requerido; ruta API deshabilitada")
        raise HTTPException(status_code=503, detail="codex route unavailable")

    last_exc: Exception | None = None
    for candidate in candidates:
        try:
            backend = candidate.get("backend", "codex-cli")
            if backend == "codex-cli":
                text, usage = run_codex_exec(messages, model, workdir=get_user_cwd())
            else:
                import litellm

                r = litellm.completion(
                    model=model,
                    messages=messages,
                    **(candidate.get("kw", {}) or {}),
                )
                text = r.choices[0].message.content
                usage = getattr(r, "usage", None) or {}
            return text, usage, candidate
        except Exception as exc:
            last_exc = exc

    detail = str(last_exc) if last_exc else "codex route unavailable"
    status = 401 if "auth required" in detail.lower() or "login required" in detail.lower() else 502
    raise HTTPException(status_code=status, detail=detail)

def _call_openai(model: str, messages: list[dict], temperature: float = 0.7,
                 max_tokens: int = 4096) -> dict:
    key = _get_key()
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OPENAI_URL}/v1/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise HTTPException(status_code=e.code, detail=f"OpenAI error: {body}")
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach OpenAI: {e.reason}")

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BAGO Codex Proxy",
    description=f"Proxy Codex (OpenAI) — API BAGO-compatible en puerto {CODEX_PORT}",
    version="1.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return {"name": "BAGO Codex Proxy", "provider": PROVIDER_NAME, "port": CODEX_PORT}


@app.get("/api/version")
async def version():
    return {"provider": PROVIDER_NAME, "api_version": "1.0.0", "base_url": OPENAI_URL}


@app.get("/api/tags", response_model=TagsResponse)
async def tags():
    return TagsResponse(models=list(CODEX_MODELS.values()))


@app.get("/api/ps")
async def ps():
    return {"models": []}


@app.post("/api/health")
async def health():
    credential, mode = resolve_openai_credential()
    candidates = resolve_codex_route_candidates("gpt-5.4-mini")
    available = bool(candidates)
    error = ""
    if available:
        routes = ", ".join(sorted({c.get("service", "") for c in candidates if c.get("service")}))
    elif mode != "oauth" or not credential:
        error = "codex login requerido; ruta API deshabilitada"
        routes = ""
    elif not codex_cli_available():
        error = "codex CLI no disponible"
        routes = ""
    else:
        error = "codex route unavailable"
        routes = ""
    return {"provider": PROVIDER_NAME, "available": available,
            "auth_mode": mode, "error": error, "routes": routes}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    if req.system:
        messages.insert(0, {"role": "system", "content": req.system})

    model = CODEX_MODELS.get(req.model, ModelInfo(name=req.model, wire_name=req.model)).wire_name

    t0 = time.perf_counter()
    try:
        content, usage, route = _run_codex_chat(model, messages)
    except HTTPException:
        raise
    except RuntimeError as exc:
        detail = str(exc)
        status = 401 if "auth required" in detail.lower() or "login required" in detail.lower() else 502
        raise HTTPException(status_code=status, detail=detail)
    elapsed = int((time.perf_counter() - t0) * 1e9)

    return {
        "model": model, "provider": PROVIDER_NAME,
        "message": {"role": "assistant", "content": content},
        "done": True, "total_duration": elapsed,
        "eval_count": _usage_count(usage, "output_tokens", "completion_tokens"),
        "prompt_eval_count": _usage_count(usage, "input_tokens", "prompt_tokens"),
        "service": route.get("service", ""),
        "route": route.get("route", ""),
        "backend": route.get("backend", ""),
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    messages = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.append({"role": "user", "content": req.prompt})

    model = CODEX_MODELS.get(req.model, ModelInfo(name=req.model, wire_name=req.model)).wire_name

    t0 = time.perf_counter()
    try:
        content, usage, route = _run_codex_chat(model, messages)
    except HTTPException:
        raise
    except RuntimeError as exc:
        detail = str(exc)
        status = 401 if "auth required" in detail.lower() or "login required" in detail.lower() else 502
        raise HTTPException(status_code=status, detail=detail)
    elapsed = int((time.perf_counter() - t0) * 1e9)

    return {
        "model": model, "provider": PROVIDER_NAME,
        "response": content, "done": True, "total_duration": elapsed,
        "eval_count": _usage_count(usage, "output_tokens", "completion_tokens"),
        "prompt_eval_count": _usage_count(usage, "input_tokens", "prompt_tokens"),
        "service": route.get("service", ""),
        "route": route.get("route", ""),
        "backend": route.get("backend", ""),
    }


@app.post("/api/embed")
async def embed(req: EmbedRequest):
    key = _get_key()
    model = req.model
    input_data = req.input if isinstance(req.input, list) else [req.input]

    payload = {"model": model, "input": input_data}
    data = json.dumps(payload).encode()
    req_url = urllib.request.Request(
        f"{OPENAI_URL}/v1/embeddings", data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req_url, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=e.code, detail=f"Embedding error: {e.read().decode(errors='replace')}")

    embeddings = [d["embedding"] for d in result.get("data", [])]
    return {"model": model, "embeddings": embeddings}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="BAGO Codex Proxy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=CODEX_PORT)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("bago.api.services.codex:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
