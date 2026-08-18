"""auto_configurator.py — Genera configuración personalizada por usuario
corriendo tests contra los modelos disponibles.

PROPÓSITO:
  Cada máquina tiene modelos diferentes, hardware diferente, latencias
  diferentes. BAGO puede generar automáticamente la mejor configuración
  para esta máquina corriendo una batería de tests y dejando que un
  "juez" (modelo cloud preferido: copilot/ollama-cloud/openai) evalúe
  las respuestas.

QUÉ HACE:
  1. Descubre todos los modelos locales (Ollama) y cloud (Copilot,
     ollama-cloud, etc.) configurados.
  2. Por cada modelo local corre tests:
     - chat básico ("di hola en una frase")
     - traducción EN→ES y ES→EN
     - razonamiento corto
     - latencia
  3. Un modelo "juez" cloud (configurable, default: copilot si está) puntúa
     cada respuesta de 0-10. Genera un ranking.
  4. Genera un "perfil" con:
     - default_model: el mejor para chat
     - translator_model: el mejor para traducción
     - blacklist: modelos que fallan tests
     - target_models para el middleware de traducción
     - timeouts recomendados según latencia observada
  5. El usuario revisa y confirma con /configure/auto/apply.

RESULTADO:
  Configuración escrita en el state root canónico de BAGO
  (sección "auto_generated_config"), separada del "translation_middleware"
  manual para que sean reversibles independientemente.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

from bago_core.user_state_paths import state_read_candidates, state_root


# ─── Estado global del job ────────────────────────────────────────────

@dataclass
class ModelTestResult:
    model: str
    provider: str
    chat_ok: bool = False
    chat_latency_s: float = 0.0
    chat_score: float = 0.0  # 0-10
    translate_en_to_es_ok: bool = False
    translate_en_to_es_score: float = 0.0
    translate_en_to_es_latency_s: float = 0.0
    translate_es_to_en_ok: bool = False
    translate_es_to_en_score: float = 0.0
    translate_es_to_en_latency_s: float = 0.0
    reasoning_ok: bool = False
    reasoning_score: float = 0.0
    reasoning_latency_s: float = 0.0
    degenerate: bool = False
    error: str | None = None
    notes: list[str] = field(default_factory=list)

    def total_score(self) -> float:
        if self.degenerate or self.error:
            return 0.0
        return (
            self.chat_score
            + self.translate_en_to_es_score
            + self.translate_es_to_en_score
            + self.reasoning_score
        )


@dataclass
class AutoConfigJob:
    status: str = "idle"  # idle | running | done | error | cancelled
    started_at: float = 0.0
    finished_at: float = 0.0
    judge_model: str = ""
    judge_provider: str = ""
    total_models: int = 0
    tested_models: int = 0
    current_model: str = ""
    results: list[ModelTestResult] = field(default_factory=list)
    generated_config: dict = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["results"] = [asdict(r) for r in self.results]
        return d


JOB = AutoConfigJob()
JOB_LOCK = threading.Lock()

# Persistencia del último job terminado, para que sobreviva reinicios.
def _last_job_path() -> Path:
    return state_root() / "last_auto_config.json"


def _read_state_json(relative: str) -> dict | None:
    """Read canonical JSON, then the read-only legacy fallback if enabled."""
    for path in state_read_candidates(relative):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return None


def _persist_last_job() -> None:
    """Guarda el estado actual del job a disco si está done/error."""
    try:
        with JOB_LOCK:
            if JOB.status not in ("done", "error", "cancelled"):
                return
            data = JOB.to_dict()
        target = _last_job_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        fd, tmp = tempfile.mkstemp(prefix="last_auto.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, target)
        except Exception:
            try: os.unlink(tmp)
            except Exception: pass
            raise
    except Exception:
        pass


def _load_last_job() -> dict | None:
    return _read_state_json("last_auto_config.json")


# ─── Helpers HTTP ─────────────────────────────────────────────────────

def _ollama_generate(model: str, prompt: str, *,
                     base_url: str = "http://127.0.0.1:11434",
                     timeout_s: float = 60.0,
                     num_predict: int = 256) -> tuple[str, float, str | None]:
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1, "num_predict": num_predict},
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/api/generate", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            d = json.load(r)
            return (d.get("response") or ""), time.time() - t0, None
    except Exception as exc:
        return "", time.time() - t0, f"{type(exc).__name__}: {exc}"


def _ollama_list_models(base_url: str = "http://127.0.0.1:11434") -> list[str]:
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=5) as r:
            d = json.load(r)
            return [m["name"] for m in d.get("models", [])]
    except Exception:
        return []


# ─── Detección de "degenerate" (heurística barata) ────────────────────

def _is_degenerate(text: str) -> bool:
    if not text or len(text) < 5:
        return True
    sample = text[:1000]
    n = len(sample)
    letters_spaces = sum(1 for c in sample if c.isalpha() or c.isspace())
    if letters_spaces / n < 0.40:
        return True
    # Símbolos no-alfanuméricos > 70% en alguna línea
    for line in sample.splitlines():
        if len(line) > 8:
            non_alnum = sum(1 for c in line if not c.isalnum() and not c.isspace())
            if non_alnum / len(line) > 0.7:
                return True
    return False


# ─── Tests individuales ───────────────────────────────────────────────

CHAT_PROMPT_ES = "Di hola en una sola frase, en español."
TRANSLATE_PROMPT_ES_TO_EN = (
    "Traduce al inglés, SOLO la traducción: "
    "El desarrollo de inteligencia artificial está transformando el mundo."
)
TRANSLATE_PROMPT_EN_TO_ES = (
    "Translate to Spanish, ONLY the translation: "
    "Artificial intelligence development is transforming the world."
)
REASONING_PROMPT = (
    "Si tengo 3 manzanas y me dan el doble de las que tengo, "
    "menos 1 que regalo, ¿cuántas me quedan? Responde solo el número."
)


def _run_test_for_model(model: str, *, judge_score_fn: Callable[[str, str], float] | None = None,
                        timeout_s: float = 90.0) -> ModelTestResult:
    """Corre la batería de tests sobre un modelo local Ollama."""
    r = ModelTestResult(model=model, provider="ollama-local")

    # 1. Chat básico
    text, dt, err = _ollama_generate(model, CHAT_PROMPT_ES, timeout_s=timeout_s, num_predict=80)
    r.chat_latency_s = dt
    if err:
        r.error = err
        r.notes.append(f"chat error: {err[:80]}")
    elif _is_degenerate(text):
        r.degenerate = True
        r.notes.append("chat degenerate")
    else:
        r.chat_ok = True
        if judge_score_fn:
            try:
                r.chat_score = judge_score_fn(CHAT_PROMPT_ES, text)
            except Exception as exc:
                r.notes.append(f"judge chat fail: {str(exc)[:60]}")
                r.chat_score = _heuristic_score_chat(CHAT_PROMPT_ES, text, dt)
        else:
            r.chat_score = _heuristic_score_chat(CHAT_PROMPT_ES, text, dt)

    # 2. Traducción ES→EN
    text, dt, err = _ollama_generate(model, TRANSLATE_PROMPT_ES_TO_EN,
                                     timeout_s=timeout_s, num_predict=80)
    r.translate_es_to_en_latency_s = dt
    if not err and text and not _is_degenerate(text):
        r.translate_es_to_en_ok = True
        if judge_score_fn:
            try:
                r.translate_es_to_en_score = judge_score_fn(TRANSLATE_PROMPT_ES_TO_EN, text)
            except Exception:
                r.translate_es_to_en_score = _heuristic_score_translation(
                    TRANSLATE_PROMPT_ES_TO_EN, text, dt, "en")
        else:
            r.translate_es_to_en_score = _heuristic_score_translation(
                TRANSLATE_PROMPT_ES_TO_EN, text, dt, "en")
    else:
        r.notes.append(f"ES->EN: {err or 'degenerate'}"[:80])

    # 3. Traducción EN→ES
    text, dt, err = _ollama_generate(model, TRANSLATE_PROMPT_EN_TO_ES,
                                     timeout_s=timeout_s, num_predict=80)
    r.translate_en_to_es_latency_s = dt
    if not err and text and not _is_degenerate(text):
        r.translate_en_to_es_ok = True
        if judge_score_fn:
            try:
                r.translate_en_to_es_score = judge_score_fn(TRANSLATE_PROMPT_EN_TO_ES, text)
            except Exception:
                r.translate_en_to_es_score = _heuristic_score_translation(
                    TRANSLATE_PROMPT_EN_TO_ES, text, dt, "es")
        else:
            r.translate_en_to_es_score = _heuristic_score_translation(
                TRANSLATE_PROMPT_EN_TO_ES, text, dt, "es")
    else:
        r.notes.append(f"EN->ES: {err or 'degenerate'}"[:80])

    # 4. Razonamiento
    text, dt, err = _ollama_generate(model, REASONING_PROMPT,
                                     timeout_s=timeout_s, num_predict=40)
    r.reasoning_latency_s = dt
    if not err and text and not _is_degenerate(text):
        # Aceptar "5" o "cinco" en cualquier parte del texto
        t = text.lower()
        if " 5" in t or t.strip().startswith("5") or "cinco" in t or "five" in t:
            r.reasoning_ok = True
        else:
            r.notes.append(f"reasoning: respuesta no contiene 5/cinco ({text[:60]!r})")
        if r.reasoning_ok:
            if judge_score_fn:
                try:
                    r.reasoning_score = judge_score_fn(REASONING_PROMPT, text)
                except Exception:
                    r.reasoning_score = _heuristic_score_reasoning(REASONING_PROMPT, text, dt)
            else:
                r.reasoning_score = _heuristic_score_reasoning(REASONING_PROMPT, text, dt)
        else:
            r.notes.append(f"reasoning: {err or 'wrong answer'}"[:80])

    return r


# ─── Juez: usa un modelo cloud si está disponible ────────────────────

def _heuristic_score_chat(prompt: str, response: str, latency_s: float) -> float:
    """Heurística local de 0-10 para evaluar chat básico. Rápida, sin red."""
    if not response or _is_degenerate(response):
        return 0.0
    score = 5.0
    # Bonus por idioma correcto (es) si el prompt es ES
    if any(c in response for c in "áéíóúñ¿¡"):
        score += 1.5
    # Bonus por longitud razonable (ni muy corto ni excesivamente largo)
    n = len(response.strip())
    if 10 <= n <= 300:
        score += 1.0
    elif n > 300:
        score -= 0.5
    # Penalizar latencia alta
    if latency_s > 30:
        score -= 2.0
    elif latency_s > 10:
        score -= 0.5
    elif latency_s < 5:
        score += 0.5
    return max(0.0, min(10.0, score))


def _heuristic_score_translation(source: str, translation: str, latency_s: float,
                                 target_lang: str) -> float:
    """Heurística para evaluar traducción. Comprueba señales básicas."""
    if not translation or _is_degenerate(translation):
        return 0.0
    score = 5.0
    n = len(translation.strip())
    if 5 <= n <= 500:
        score += 1.0
    elif n > 500:
        score -= 0.5
    # Si el target es ES, debe tener señales de español
    if target_lang == "es" and any(c in translation for c in "áéíóúñ¿¡"):
        score += 1.5
    # Si el target es EN, no debe tener señales fuertes de español
    if target_lang == "en":
        es_chars = sum(1 for c in translation if c in "áéíóúñ¿¡")
        if es_chars > 3:
            score -= 2.0
    if latency_s > 30:
        score -= 2.0
    elif latency_s < 5:
        score += 0.5
    return max(0.0, min(10.0, score))


def _heuristic_score_reasoning(prompt: str, response: str, latency_s: float) -> float:
    """Heurística para razonamiento: verifica que la respuesta correcta esté presente."""
    if not response or _is_degenerate(response):
        return 0.0
    t = response.lower()
    has_answer = (" 5" in t or t.strip().startswith("5") or "cinco" in t or "five" in t)
    if not has_answer:
        return 1.0
    score = 7.0
    if latency_s < 10:
        score += 1.5
    elif latency_s > 30:
        score -= 2.0
    return max(0.0, min(10.0, score))
    """Juez usando ollama-cloud. Si falla, devuelve 5.0."""
    # La key está en credentials.json (no en secret_store)
    api_key = ""
    creds = _read_state_json("credentials.json") or {}
    api_key = (creds.get("ollama-cloud", {}) or {}).get("OLLAMA_CLOUD_KEY", "")
    if not api_key:
        # Intentar también por secret_store y env
        try:
            from secret_store import get_secret_store
            api_key = get_secret_store().get_secret("providers/ollama-cloud/api_key") or ""
        except Exception:
            pass
    if not api_key:
        api_key = os.environ.get("OLLAMA_CLOUD_API_KEY", "")
    if not api_key:
        return 5.0

    judge_prompt = (
        "Evalúa la siguiente respuesta a un prompt. Da una puntuación de 0 a 10 "
        "según corrección, concisión y relevancia. Responde SOLO con un número entero.\n\n"
        f"PROMPT: {prompt}\n\nRESPUESTA: {response}\n\nPUNTUACIÓN:"
    )
    # Modelos "thinking" (gpt-oss, glm-5) usan tokens para razonamiento
    # antes de la respuesta. Damos más num_predict y un prompt más directo.
    body = json.dumps({
        "model": "gpt-oss:20b",
        "prompt": (
            "Just give the number 0-10. No explanation. "
            f"Rate this response:\nQ: {prompt}\nA: {response}\nScore:"
        ),
        "stream": False,
        "options": {"temperature": 0, "num_predict": 80},
    }).encode()
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {api_key}"}
    req = urllib.request.Request(
        "https://ollama.com/api/generate", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
            # Modelos thinking devuelven la respuesta en "response", pero
            # también puede haberla en "thinking". Buscar en ambos.
            text = (d.get("response") or "").strip()
            if not text or not any(c.isdigit() for c in text):
                thinking = (d.get("thinking") or "").strip()
                if thinking and any(c.isdigit() for c in thinking):
                    text = thinking
            import re
            m = re.search(r"\d+(?:\.\d+)?", text)
            if m:
                return max(0.0, min(10.0, float(m.group(0))))
            # Si llegamos aquí, el juez no devolvió un número parseable.
            # Devolvemos 5.0 (neutral) y logueamos.
            import sys
            print(f"[auto_config] juez sin número: response={d.get('response','')[:80]!r} thinking={d.get('thinking','')[:80]!r}", file=sys.stderr)
    except Exception as exc:
        import sys
        print(f"[auto_config] juez excepción: {exc}", file=sys.stderr)
    return 5.0


def _judge_copilot(prompt: str, response: str) -> float:
    """Juez usando GitHub Copilot. Si no hay token, devuelve 5.0."""
    try:
        from secret_store import get_secret_store
        token = get_secret_store().get_secret("providers/copilot/api_key") or ""
    except Exception:
        token = ""
    if not token:
        return 5.0
    judge_prompt = (
        f"Rate this response 0-10 (only number):\nQ: {prompt}\nA: {response}"
    )
    body = json.dumps({
        "messages": [{"role": "user", "content": judge_prompt}],
        "model": "gpt-4o-mini",
    }).encode()
    req = urllib.request.Request(
        "https://api.githubcopilot.com/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
            content = d.get("choices", [{}])[0].get("message", {}).get("content", "")
            import re
            m = re.search(r"\d+", content)
            if m:
                return max(0.0, min(10.0, float(m.group(0))))
    except Exception:
        pass
    return 5.0


def _select_judge() -> tuple[Callable, str, str]:
    """Devuelve (judge_fn, provider_name, model_name). Prioridad: copilot, ollama-cloud, sin juez."""
    # Comprobar ollama-cloud primero (más probable que esté configurado)
    creds = _read_state_json("credentials.json") or {}
    if creds.get("ollama-cloud", {}).get("OLLAMA_CLOUD_KEY"):
        return _judge_ollama_cloud, "ollama-cloud", "gpt-oss:20b"
    # Comprobar copilot
    try:
        from secret_store import get_secret_store
        ss = get_secret_store()
        if ss.has_secret("providers/copilot/api_key"):
            return _judge_copilot, "copilot", "gpt-4o-mini"
    except Exception:
        pass
    # Env vars
    if os.environ.get("OLLAMA_CLOUD_API_KEY"):
        return _judge_ollama_cloud, "ollama-cloud", "gpt-oss:20b"
    if os.environ.get("COPILOT_API_KEY") or os.environ.get("GITHUB_TOKEN"):
        return _judge_copilot, "copilot", "gpt-4o-mini"
    return None, "", ""  # sin juez


# ─── Generación de config a partir de resultados ──────────────────────

def _generate_config_from_results(results: list[ModelTestResult]) -> dict:
    """Genera la config óptima: default, translator, blacklist, timeouts."""
    config = {
        "default_model": "llama3.2:3b",  # fallback
        "translation_middleware": {
            "enabled": False,
            "translator_model": "llama3.2:3b",
            "target_models": [],
            "adapter_timeout_s": 180.0,
            "target_keep_alive_minutes": 30,
        },
        "blacklist": [],
        "model_quality": {},  # model -> score
    }

    # Filtrar modelos válidos (no degenerate, no error)
    valid = [r for r in results if not r.degenerate and not r.error]
    degenerate = [r for r in results if r.degenerate or r.error]

    if not valid:
        return config

    # Mejor modelo para chat: ordenar por score, con latencia <60s
    chat_candidates = sorted(
        [r for r in valid if r.chat_ok and r.chat_latency_s < 60],
        key=lambda r: (-r.chat_score, r.chat_latency_s),  # score desc, latency asc
    )
    if not chat_candidates:
        # Fallback: cualquier modelo válido
        chat_candidates = sorted(valid, key=lambda r: (-r.chat_score, r.chat_latency_s))
    if chat_candidates:
        config["default_model"] = chat_candidates[0].model
        config["model_quality"][chat_candidates[0].model] = {
            "role": "default", "score": chat_candidates[0].chat_score,
            "latency_s": chat_candidates[0].chat_latency_s,
        }

    # Mejor traductor (mayor suma de los 2 scores de traducción, latencia <30s)
    trans_candidates = sorted(
        [r for r in valid if r.translate_es_to_en_ok and r.translate_en_to_es_ok
         and r.translate_es_to_en_latency_s < 30 and r.translate_en_to_es_latency_s < 30],
        key=lambda r: (
            r.translate_es_to_en_score + r.translate_en_to_es_score,
            -max(r.translate_es_to_en_latency_s, r.translate_en_to_es_latency_s)
        ),
    )
    if trans_candidates:
        best_trans = trans_candidates[0]
        config["translation_middleware"]["translator_model"] = best_trans.model
        config["model_quality"][best_trans.model] = {
            "role": "translator",
            "score": (best_trans.translate_es_to_en_score + best_trans.translate_en_to_es_score) / 2,
            "latency_s": max(best_trans.translate_es_to_en_latency_s, best_trans.translate_en_to_es_latency_s),
        }

    # Activar middleware si el default es diferente del translator y hay modelos "lentos en español"
    default_r = next((r for r in valid if r.model == config["default_model"]), None)
    if config["default_model"] != config["translation_middleware"]["translator_model"]:
        # Buscar modelos que NO son buenos para ES pero sí para EN
        for r in valid:
            # Si traduce mejor al inglés que al español, o si el chat en español tiene score bajo
            es_to_en = r.translate_es_to_en_score
            en_to_es = r.translate_en_to_es_score
            chat_es = r.chat_score
            # Criterio: chat_score bajo + traduce bien al/en inglés
            if (chat_es < 6 and es_to_en > 7) or (en_to_es < 5 and es_to_en > 6):
                config["translation_middleware"]["target_models"].append(r.model)
        # Si el default es "lento en español" y hay translator distinto, activar middleware
        if default_r is not None and default_r.chat_score < 7 and config["translation_middleware"]["translator_model"] != config["default_model"]:
            config["translation_middleware"]["enabled"] = True

    # Calcular adapter_timeout según la latencia observada del default
    if default_r is not None:
        # 3x la latencia observada, con mínimo 60s y máximo 300s
        t = max(60.0, min(300.0, default_r.chat_latency_s * 3.0))
        config["translation_middleware"]["adapter_timeout_s"] = t

    # Blacklist: modelos que fallaron
    for r in degenerate:
        config["blacklist"].append({
            "model": r.model,
            "reason": r.error or "degenerate output",
            "notes": r.notes,
        })

    return config


# ─── Job runner ───────────────────────────────────────────────────────

def start_job(judge_override: tuple[str, str] | None = None) -> dict:
    """Lanza el job en background. Devuelve estado inicial."""
    with JOB_LOCK:
        if JOB.status == "running":
            return {"ok": False, "error": "ya hay un job corriendo"}
        JOB.status = "running"
        JOB.started_at = time.time()
        JOB.finished_at = 0.0
        JOB.results = []
        JOB.log = []
        JOB.error = None
        JOB.generated_config = {}
        JOB.tested_models = 0
        JOB.total_models = 0
        JOB.current_model = ""

    def _runner():
        try:
            # 1. Listar modelos locales
            models = _ollama_list_models()
            # Filtrar blacklist existente
            try:
                import blacklist_models as bl
                bl_data = bl.get_blacklist()
                blocked = set(bl_data.get("models", []))
                models = [m for m in models if m not in blocked]
            except Exception:
                pass
            with JOB_LOCK:
                JOB.total_models = len(models)
            JOB.log.append(f"Modelos a probar: {len(models)}")

            # 2. Seleccionar juez
            if judge_override:
                provider, model = judge_override
                if provider == "copilot":
                    judge = _judge_copilot
                else:
                    judge = _judge_ollama_cloud
                JOB.judge_provider = provider
                JOB.judge_model = model
            else:
                judge, prov, mod = _select_judge()
                JOB.judge_provider = prov
                JOB.judge_model = mod
            if judge:
                JOB.log.append(f"Juez: {JOB.judge_provider}/{JOB.judge_model}")
            else:
                JOB.log.append("Sin juez cloud; usando heurística local (menos preciso)")

            # 3. Probar cada modelo
            for m in models:
                with JOB_LOCK:
                    if JOB.status == "cancelled":
                        return
                    JOB.current_model = m
                JOB.log.append(f"Probando {m}...")
                try:
                    r = _run_test_for_model(m, judge_score_fn=judge, timeout_s=90.0)
                except Exception as exc:
                    r = ModelTestResult(model=m, provider="ollama-local", error=str(exc))
                with JOB_LOCK:
                    JOB.results.append(r)
                    JOB.tested_models += 1
                JOB.log.append(
                    f"  {m}: score={r.total_score():.1f}  chat={r.chat_score:.1f}  "
                    f"trans={r.translate_es_to_en_score:.1f}/{r.translate_en_to_es_score:.1f}  "
                    f"reasoning={r.reasoning_score:.1f}  "
                    f"{'⚠️ degenerate' if r.degenerate else ('❌ error' if r.error else '✅')}"
                )

            # 4. Generar config
            with JOB_LOCK:
                JOB.generated_config = _generate_config_from_results(JOB.results)
                JOB.status = "done"
                JOB.finished_at = time.time()
            _persist_last_job()
            JOB.log.append(f"Config generada. Default: {JOB.generated_config.get('default_model')}")
        except Exception as exc:
            with JOB_LOCK:
                JOB.status = "error"
                JOB.error = str(exc)
                JOB.finished_at = time.time()
            _persist_last_job()
            JOB.log.append(f"ERROR: {exc}")

    threading.Thread(target=_runner, daemon=True).start()
    return {"ok": True, "status": JOB.status, "models_to_test": JOB.total_models}


def cancel_job() -> dict:
    with JOB_LOCK:
        if JOB.status != "running":
            return {"ok": False, "error": "no hay job corriendo"}
        JOB.status = "cancelled"
    return {"ok": True, "status": "cancelled"}


def get_status() -> dict:
    """Estado del job en memoria. Si está idle, intenta cargar el último
    job terminado desde disco (sobrevive a reinicios)."""
    with JOB_LOCK:
        if JOB.status == "idle":
            last = _load_last_job()
            if last:
                return {
                    "ok": True,
                    "status": "idle",
                    "last_job": last,
                    "message": "no hay job activo; mostrando el último terminado",
                }
        return {"ok": True, **JOB.to_dict()}


def apply_generated_config(force: bool = False) -> dict:
    """Aplica la config generada al config.json del usuario (LOCALAPPDATA).

    Si el job en memoria está idle, intenta cargar el último job terminado
    de disco. Con force=True aplica aunque venga de disco.
    """
    with JOB_LOCK:
        if JOB.status == "done":
            cfg = JOB.generated_config
        else:
            last = _load_last_job()
            if not last:
                return {"ok": False, "error": "el job no ha terminado y no hay último resultado guardado"}
            if last.get("status") != "done":
                return {"ok": False, "error": f"el último job terminó con estado {last.get('status')}"}
            cfg = last.get("generated_config", {})
    if not cfg:
        return {"ok": False, "error": "no hay config generada"}

    # Escritura siempre canónica; legacy solo participa en la lectura inicial.
    cfg_path = state_root() / "config.json"

    # Leer config existente
    existing = _read_state_json("config.json") or {}

    # Aplicar default_model
    if cfg.get("default_model"):
        existing["default_model"] = cfg["default_model"]
        # También en providers.ollama-local.default_model
        if "providers" not in existing:
            existing["providers"] = {}
        if "ollama-local" not in existing["providers"]:
            existing["providers"]["ollama-local"] = {}
        existing["providers"]["ollama-local"]["default_model"] = cfg["default_model"]

    # Aplicar translation_middleware
    if cfg.get("translation_middleware"):
        existing["translation_middleware"] = cfg["translation_middleware"]

    # Guardar metadata de auto-config
    existing["auto_generated_config"] = {
        "generated_at": time.time(),
        "default_model": cfg.get("default_model"),
        "translator_model": cfg.get("translation_middleware", {}).get("translator_model"),
        "model_quality": cfg.get("model_quality", {}),
        "blacklist_count": len(cfg.get("blacklist", [])),
    }

    # Guardar atómicamente
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    fd, tmp_name = tempfile.mkstemp(prefix="config.", suffix=".tmp", dir=str(cfg_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        os.replace(tmp_name, cfg_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass
        raise

    # Aplicar blacklist por separado (otro archivo)
    blacklist = cfg.get("blacklist", [])
    if blacklist:
        try:
            import blacklist_models as bl
            for entry in blacklist:
                bl.add(entry["model"], entry.get("reason", "auto: failed tests"))
        except Exception as exc:
            return {"ok": True, "config_applied": True,
                    "blacklist_warning": f"no se pudo aplicar blacklist: {exc}"}

    return {
        "ok": True,
        "config_path": str(cfg_path),
        "applied": {
            "default_model": cfg.get("default_model"),
            "translator_model": cfg.get("translation_middleware", {}).get("translator_model"),
            "middleware_enabled": cfg.get("translation_middleware", {}).get("enabled", False),
            "blacklist_size": len(blacklist),
            "model_quality": cfg.get("model_quality", {}),
        },
    }
