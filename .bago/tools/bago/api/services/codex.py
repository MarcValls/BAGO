"""bago.api.services.codex — Proxy Codex (OpenAI) en puerto 11437.

Traduce la API BAGO al formato OpenAI API.
Puerto: 11437
Auth: OPENAI_API_KEY en entorno
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
from bago.ollama_runtime import DEFAULT_BAGO_CODEX_PORT, env_port

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
    available = bool(os.environ.get("OPENAI_API_KEY", ""))
    return {"provider": PROVIDER_NAME, "available": available,
            "error": "" if available else "OPENAI_API_KEY not set"}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    if req.system:
        messages.insert(0, {"role": "system", "content": req.system})

    model = CODEX_MODELS.get(req.model, ModelInfo(name=req.model, wire_name=req.model)).wire_name
    temp = req.options.get("temperature", req.temperature)
    max_tok = req.options.get("num_predict", req.max_tokens)

    t0 = time.perf_counter()
    result = _call_openai(model, messages, float(temp), int(max_tok))
    elapsed = int((time.perf_counter() - t0) * 1e9)

    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = result.get("usage", {})

    return {
        "model": model, "provider": PROVIDER_NAME,
        "message": {"role": "assistant", "content": content},
        "done": True, "total_duration": elapsed,
        "eval_count": usage.get("completion_tokens", 0),
        "prompt_eval_count": usage.get("prompt_tokens", 0),
    }


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    messages = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.append({"role": "user", "content": req.prompt})

    model = CODEX_MODELS.get(req.model, ModelInfo(name=req.model, wire_name=req.model)).wire_name
    temp = req.options.get("temperature", req.temperature)
    max_tok = req.options.get("num_predict", req.max_tokens)

    t0 = time.perf_counter()
    result = _call_openai(model, messages, float(temp), int(max_tok))
    elapsed = int((time.perf_counter() - t0) * 1e9)

    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = result.get("usage", {})

    return {
        "model": model, "provider": PROVIDER_NAME,
        "response": content, "done": True, "total_duration": elapsed,
        "eval_count": usage.get("completion_tokens", 0),
        "prompt_eval_count": usage.get("prompt_tokens", 0),
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



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
