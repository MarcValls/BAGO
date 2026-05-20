"""bago.api.services.ollama_cloud — Proxy Ollama Cloud en puerto 11438.

Traduce la API BAGO al formato Ollama Cloud API.
Puerto: 11438
Auth: OLLAMA_API_KEY en entorno
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ─── Config ────────────────────────────────────────────────────────────────────

OLLAMA_CLOUD_PORT = 11438
OLLAMA_CLOUD_URL = "https://api.ollama.com"
PROVIDER_NAME = "ollama-cloud"

# ─── Models ────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = "user"
    content: str

class ChatRequest(BaseModel):
    model: str = "devstral-2:123b"
    messages: list[ChatMessage]
    stream: bool = False
    system: str = ""
    options: dict = Field(default_factory=dict)

class GenerateRequest(BaseModel):
    model: str = "devstral-2:123b"
    prompt: str
    system: str = ""
    stream: bool = False
    options: dict = Field(default_factory=dict)

class EmbedRequest(BaseModel):
    model: str = "nomic-embed-text"
    input: str | list[str]

class ModelInfo(BaseModel):
    name: str
    wire_name: str
    best_for: str = ""
    max_prompt_tokens: int = 128000
    max_output_tokens: int = 8192
    cost: str = "subscription"

class TagsResponse(BaseModel):
    models: list[ModelInfo] = Field(default_factory=list)

# ─── Cloud models ─────────────────────────────────────────────────────────────

CLOUD_MODELS = {
    "devstral-2": ModelInfo(name="devstral-2", wire_name="devstral-2:123b", best_for="code", max_prompt_tokens=128000),
    "qwen3-coder-480b": ModelInfo(name="qwen3-coder-480b", wire_name="qwen3-coder:480b", best_for="code", max_prompt_tokens=256000),
    "deepseek-v3-671b": ModelInfo(name="deepseek-v3-671b", wire_name="deepseek-v3.1:671b", best_for="reasoning", max_prompt_tokens=64000),
    "kimi-k2-1t": ModelInfo(name="kimi-k2-1t", wire_name="kimi-k2:1t", best_for="long_context", max_prompt_tokens=1000000),
}

# ─── Client ───────────────────────────────────────────────────────────────────

def _get_key() -> str:
    key = os.environ.get("OLLAMA_API_KEY", "")
    if not key:
        raise HTTPException(status_code=401, detail="OLLAMA_API_KEY not set")
    return key

def _call_ollama_cloud(endpoint: str, payload: dict) -> dict:
    key = _get_key()
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_CLOUD_URL}{endpoint}",
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise HTTPException(status_code=e.code, detail=f"Ollama Cloud error: {body}")
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach Ollama Cloud: {e.reason}")

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BAGO Ollama Cloud Proxy",
    description="Proxy Ollama Cloud — API BAGO-compatible en puerto 11438",
    version="1.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return {"name": "BAGO Ollama Cloud Proxy", "provider": PROVIDER_NAME, "port": OLLAMA_CLOUD_PORT}


@app.get("/api/version")
async def version():
    return {"provider": PROVIDER_NAME, "api_version": "1.0.0", "base_url": OLLAMA_CLOUD_URL}


@app.get("/api/tags", response_model=TagsResponse)
async def tags():
    return TagsResponse(models=list(CLOUD_MODELS.values()))


@app.get("/api/ps")
async def ps():
    return {"models": []}


@app.post("/api/health")
async def health():
    available = bool(os.environ.get("OLLAMA_API_KEY", ""))
    return {"provider": PROVIDER_NAME, "available": available,
            "error": "" if available else "OLLAMA_API_KEY not set"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    if req.system:
        messages.insert(0, {"role": "system", "content": req.system})

    model = CLOUD_MODELS.get(req.model, ModelInfo(name=req.model, wire_name=req.model)).wire_name

    payload = {"model": model, "messages": messages, "stream": False}
    payload.update(req.options)

    t0 = time.perf_counter()
    result = _call_ollama_cloud("/api/chat", payload)
    elapsed = int((time.perf_counter() - t0) * 1e9)

    content = result.get("message", {}).get("content", "")
    return {
        "model": model, "provider": PROVIDER_NAME,
        "message": {"role": "assistant", "content": content},
        "done": True, "total_duration": elapsed,
        "eval_count": result.get("eval_count", 0),
        "prompt_eval_count": result.get("prompt_eval_count", 0),
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    model = CLOUD_MODELS.get(req.model, ModelInfo(name=req.model, wire_name=req.model)).wire_name

    payload = {"model": model, "prompt": req.prompt, "stream": False}
    if req.system:
        payload["system"] = req.system
    payload.update(req.options)

    t0 = time.perf_counter()
    result = _call_ollama_cloud("/api/generate", payload)
    elapsed = int((time.perf_counter() - t0) * 1e9)

    return {
        "model": model, "provider": PROVIDER_NAME,
        "response": result.get("response", ""),
        "done": True, "total_duration": elapsed,
        "eval_count": result.get("eval_count", 0),
        "prompt_eval_count": result.get("prompt_eval_count", 0),
    }


@app.post("/api/embed")
async def embed(req: EmbedRequest):
    model = req.model
    payload = {"model": model, "input": req.input}

    result = _call_ollama_cloud("/api/embed", payload)
    embeddings = result.get("embeddings", [])
    return {"model": model, "embeddings": embeddings}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="BAGO Ollama Cloud Proxy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=OLLAMA_CLOUD_PORT)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("bago.api.services.ollama_cloud:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
