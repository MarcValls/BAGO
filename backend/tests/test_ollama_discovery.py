from __future__ import annotations

from pathlib import Path

from ollama_discovery import discover_ollama_model_names  # noqa: E402
from ollama_local import OllamaLocalAdapter  # noqa: E402
import ollama_discovery  # noqa: E402
import repl_model_router  # noqa: E402


def test_discovers_ollama_models_from_disk(tmp_path, monkeypatch):
    models_root = tmp_path / ".ollama" / "models"
    manifest = models_root / "manifests" / "registry.ollama.ai" / "library" / "llama3.2" / "3b"
    manifest.mkdir(parents=True)
    (manifest / "manifest").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OLLAMA_MODELS", str(models_root))
    monkeypatch.setattr(ollama_discovery, "_discover_models_from_api", lambda base_url: [])

    names = discover_ollama_model_names("http://127.0.0.1:11434")

    assert "llama3.2:3b" in names


def test_adapter_list_models_uses_disk_catalog(tmp_path, monkeypatch):
    models_root = tmp_path / ".ollama" / "models"
    manifest = models_root / "manifests" / "registry.ollama.ai" / "library" / "qwen2.5" / "1.5b"
    manifest.mkdir(parents=True)
    (manifest / "manifest").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OLLAMA_MODELS", str(models_root))
    monkeypatch.setattr(ollama_discovery, "_discover_models_from_api", lambda base_url: [])

    adapter = OllamaLocalAdapter(config={"base_url": "http://127.0.0.1:65535"})
    names = [item.model_id for item in adapter.list_models()]

    assert "qwen2.5:1.5b" in names


def test_ollama_chat_sends_system_as_first_message(monkeypatch):
    payloads = []

    def fake_post(self, url, payload, timeout=60.0):
        payloads.append(payload)
        return {
            "message": {"content": "ok"},
            "done": True,
            "prompt_eval_count": 1,
            "eval_count": 1,
        }

    monkeypatch.setattr(OllamaLocalAdapter, "_post", fake_post)
    adapter = OllamaLocalAdapter(config={"base_url": "http://127.0.0.1:65535"})

    adapter.chat([{"role": "user", "content": "hola"}], "llama3.2:3b", system="SYSTEM PROMPT")

    assert payloads[0]["messages"][0] == {"role": "system", "content": "SYSTEM PROMPT"}
    assert "system" not in payloads[0]


def test_router_discovers_disk_models(tmp_path, monkeypatch):
    models_root = tmp_path / ".ollama" / "models"
    manifest = models_root / "manifests" / "registry.ollama.ai" / "library" / "granite3.2" / "8b"
    manifest.mkdir(parents=True)
    (manifest / "manifest").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OLLAMA_MODELS", str(models_root))
    monkeypatch.setattr(ollama_discovery, "_discover_models_from_api", lambda base_url: [])

    entries = repl_model_router._discover_ollama_local()
    names = [entry.model_id for entry in entries]

    assert "granite3.2:8b" in names
