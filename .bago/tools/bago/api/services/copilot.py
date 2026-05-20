"""bago.api.services.copilot — Proxy Copilot (GitHub Models) en puerto 11436.

Traduce la API BAGO al formato de GitHub Models API.
Unifica la interfaz para que n8n y BAGO hablen el mismo protocolo
independientemente del provider.

Puerto: 11436
Auth: GH_TOKEN o GITHUB_TOKEN en entorno
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ─── Config ────────────────────────────────────────────────────────────────────

COPILOT_PORT = 11436
GITHUB_MODELS_URL = "https://models.inference.ai.azure.com"
PROVIDER_NAME = "copilot"

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
    # BAGO compatibility
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
    cost: str = "included"

class TagsResponse(BaseModel):
    models: list[ModelInfo] = Field(default_factory=list)

class VersionResponse(BaseModel):
    provider: str = PROVIDER_NAME
    api_version: str = "1.0.0"
    base_url: str = GITHUB_MODELS_URL

# ─── Copilot models registry ────────────────────────────────────────────────

COPILOT_MODELS = {
    "claude-sonnet-4.6": ModelInfo(name="claude-sonnet-4.6", wire_name="claude-sonnet-4.6", best_for="code_review"),
    "claude-opus-4.7": ModelInfo(name="claude-opus-4.7", wire_name="claude-opus-4.7", best_for="complex_reasoning"),
    "gpt-5.5": ModelInfo(name="gpt-5.5", wire_name="gpt-5.5", best_for="frontier"),
    "gpt-5.4": ModelInfo(name="gpt-5.4", wire_name="gpt-5.4", best_for="everyday"),
    "gpt-5.4-mini": ModelInfo(name="gpt-5.4-mini", wire_name="gpt-5.4-mini", best_for="fast"),
    "gpt-5.3-codex": ModelInfo(name="gpt-5.3-codex", wire_name="gpt-5.3-codex", best_for="coding"),
    "gpt-5.2": ModelInfo(name="gpt-5.2", wire_name="gpt-5.2", best_for="long_agents"),
}

# ─── Client ────────────────────────────────────────────────────────────────

def _get_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise HTTPException(status_code=401, detail="GH_TOKEN not set. Run: gh auth login")
    return token

def _call_github(model: str, messages: list[dict], temperature: float = 0.7,
                 max_tokens: int = 4096) -> dict:
    """Call GitHub Models API (OpenAI-compatible)."""
    token = _get_token()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{GITHUB_MODELS_URL}/v1/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise HTTPException(status_code=e.code, detail=f"GitHub Models error: {body}")
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach GitHub Models: {e.reason}")

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BAGO Copilot Proxy",
    description="Proxy Copilot (GitHub Models) — API BAGO-compatible en puerto 11436",
    version="1.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return {"name": "BAGO Copilot Proxy", "provider": PROVIDER_NAME, "port": COPILOT_PORT}


@app.get("/api/version", response_model=VersionResponse)
async def version():
    return VersionResponse()


@app.get("/api/tags", response_model=TagsResponse)
async def tags():
    return TagsResponse(models=list(COPILOT_MODELS.values()))


@app.get("/api/ps")
async def ps():
    return {"models": []}


@app.post("/api/health")
async def health():
    available = False
    latency = 0
    error = ""
    try:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
        available = bool(token)
        if not token:
            error = "GH_TOKEN not set"
    except Exception as e:
        error = str(e)
    return {"provider": PROVIDER_NAME, "available": available, "error": error}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    if req.system:
        messages.insert(0, {"role": "system", "content": req.system})

    model = req.model
    # Resolve alias
    if model in COPILOT_MODELS:
        model = COPILOT_MODELS[model].wire_name

    temp = req.options.get("temperature", req.temperature)
    max_tok = req.options.get("num_predict", req.max_tokens)

    t0 = time.perf_counter()
    result = _call_github(model, messages, temperature=float(temp), max_tokens=int(max_tok))
    elapsed = int((time.perf_counter() - t0) * 1e9)

    choice = result.get("choices", [{}])[0]
    content = choice.get("message", {}).get("content", "")
    usage = result.get("usage", {})

    return {
        "model": model,
        "provider": PROVIDER_NAME,
        "message": {"role": "assistant", "content": content},
        "done": True,
        "total_duration": elapsed,
        "eval_count": usage.get("completion_tokens", 0),
        "prompt_eval_count": usage.get("prompt_tokens", 0),
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    messages = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.append({"role": "user", "content": req.prompt})

    model = req.model
    if model in COPILOT_MODELS:
        model = COPILOT_MODELS[model].wire_name

    temp = req.options.get("temperature", req.temperature)
    max_tok = req.options.get("num_predict", req.max_tokens)

    t0 = time.perf_counter()
    result = _call_github(model, messages, temperature=float(temp), max_tokens=int(max_tok))
    elapsed = int((time.perf_counter() - t0) * 1e9)

    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = result.get("usage", {})

    return {
        "model": model,
        "provider": PROVIDER_NAME,
        "response": content,
        "done": True,
        "total_duration": elapsed,
        "eval_count": usage.get("completion_tokens", 0),
        "prompt_eval_count": usage.get("prompt_tokens", 0),
    }


@app.post("/api/embed")
async def embed(req: EmbedRequest):
    token = _get_token()
    model = req.model
    input_data = req.input if isinstance(req.input, list) else [req.input]

    payload = {"model": model, "input": input_data}
    data = json.dumps(payload).encode()
    req_url = urllib.request.Request(
        f"{GITHUB_MODELS_URL}/v1/embeddings",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req_url, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=e.code, detail=f"Embedding error: {e.read().decode(errors='replace')}")

    embeddings = [d["embedding"] for d in result.get("data", [])]
    return {"model": model, "embeddings": embeddings}


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="BAGO Copilot Proxy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=COPILOT_PORT)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("bago.api.services.copilot:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
