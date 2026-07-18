"""bench_translate.py — Test de traducción ES↔EN para todos los modelos Ollama.

Mide: coherencia de la traducción, fidelidad (preserva el sentido), idioma
correcto de salida, y latencia. No es un benchmark lingüístico formal,
sirve para detectar qué modelos sirven como translator razonables.
"""
import json
import time
import urllib.request
import urllib.error

OLLAMA = "http://127.0.0.1:11434"
TIMEOUT = 180

# Pares (source_text, source_lang, target_lang, must_contain_any)
# must_contain_any: al menos una de estas sub-strings debe aparecer en la salida
PAIRS = [
    (
        "The quick brown fox jumps over the lazy dog.",
        "inglés",
        "español",
        ["rápido", "zorro", "perezoso"],  # cualquiera de estas
    ),
    (
        "El desarrollo de inteligencia artificial está transformando "
        "la forma en que trabajamos y vivimos.",
        "español",
        "inglés",
        ["artificial intelligence", "AI", "development"],
    ),
]

# Lista negra local
import os
_blacklist = set()
try:
    bl_path = os.path.expandvars(r"%USERPROFILE%\.bago\state\model_blacklist.json")
    if os.path.exists(bl_path):
        with open(bl_path, encoding="utf-8") as f:
            _blacklist = set(json.load(f).get("models", []))
except Exception:
    pass


def list_models():
    with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=5) as r:
        return json.load(r).get("models", [])


def query(model, prompt, timeout_s=TIMEOUT):
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1, "num_predict": 200},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            d = json.load(r)
            return d.get("response", ""), time.time() - t0, None
    except Exception as exc:
        return "", time.time() - t0, f"{type(exc).__name__}: {exc}"


def score(text, must_contain_any, target_lang):
    if not text:
        return 0.0, "vacío"
    text_low = text.lower()
    # Tiene al menos una keyword esperada
    if not any(k.lower() in text_low for k in must_contain_any):
        return 0.2, f"sin keywords {must_contain_any}"
    # Idioma de salida: heurística muy cruda
    if target_lang == "español":
        # debe tener ñ, á, é, í, ó, ú, o palabras comunes
        es_signals = sum(1 for c in text if c in "áéíóúñü¿¡")
        en_signals = sum(1 for c in text_low if c in "abcdefghijklmnopqrstuvwxyz")
        # proporción muy burda
        if es_signals == 0 and len(text) > 30:
            return 0.5, f"sin tildes/ñ (es_signals=0, len={len(text)})"
        return 1.0, f"ok (es_signals={es_signals})"
    else:  # inglés
        en_words = ["the", "and", "is", "of", "for", "with", "that", "to", "a", "in"]
        es_signals = sum(1 for c in text if c in "áéíóúñü¿¡")
        has_en = any(w in text_low.split() for w in en_words)
        if es_signals > 3 and not has_en:
            return 0.5, f"salida parece español (es_signals={es_signals})"
        if not has_en:
            return 0.6, f"sin palabras EN comunes"
        return 1.0, "ok"


def main():
    models = list_models()
    chat_models = [
        m["name"] for m in models
        if "vision" not in m["name"]
        and "eyes" not in m["name"]
        and "orchestrator" not in m["name"]
        and m["name"] not in _blacklist
    ]
    print(f"Modelos a probar: {len(chat_models)}\n")

    results = []
    for m in chat_models:
        print(f"=== {m} ===")
        for src, src_lang, tgt_lang, must in PAIRS:
            prompt = f"Traduce del {src_lang} al {tgt_lang}. Responde SOLO con la traducción, sin explicaciones.\n\n{src}"
            text, dt, err = query(m, prompt)
            if err:
                print(f"  [{src_lang}→{tgt_lang}] ERROR: {err} ({dt:.0f}s)")
                results.append({"model": m, "pair": f"{src_lang}→{tgt_lang}",
                                "ok": False, "err": err, "elapsed": dt})
                continue
            sc, why = score(text, must, tgt_lang)
            verdict = "✅" if sc >= 0.9 else "⚠️" if sc >= 0.5 else "❌"
            print(f"  {verdict} [{src_lang}→{tgt_lang}] {dt:.1f}s  score={sc:.1f}  {why}")
            print(f"    >> {text[:140]!r}")
            results.append({"model": m, "pair": f"{src_lang}→{tgt_lang}",
                            "ok": sc >= 0.9, "elapsed": dt, "score": sc})

    print()
    print("=" * 78)
    print("RESUMEN — modelos buenos para traducir")
    print("=" * 78)
    by_model = {}
    for r in results:
        by_model.setdefault(r["model"], []).append(r)
    for m, runs in by_model.items():
        oks = sum(1 for r in runs if r.get("ok"))
        avg = sum(r.get("elapsed", 999) for r in runs) / len(runs)
        avg_sc = sum(r.get("score", 0) for r in runs) / len(runs)
        status = "✅ APTO" if oks == len(runs) else f"⚠️ {oks}/{len(runs)}"
        print(f"  {m:45} {status:15} avg_time={avg:5.0f}s  avg_score={avg_sc:.2f}")


if __name__ == "__main__":
    main()
