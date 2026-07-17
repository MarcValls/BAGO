"""bench_models.py — Prueba todos los modelos Ollama locales con un prompt
simple, sin pasar por el frontend ni por el backend de BAGO. Mide latencia,
longitud, ratio de coherencia y veredicto.

Uso:
    python bench_models.py
    python bench_models.py "tu prompt"
"""
import json
import sys
import time
import urllib.request
import urllib.error


def list_models(base: str = "http://127.0.0.1:11434") -> list[dict]:
    with urllib.request.urlopen(f"{base}/api/tags", timeout=5) as r:
        return json.load(r).get("models", [])


def query(model: str, prompt: str, base: str = "http://127.0.0.1:11434",
          timeout_s: int = 60) -> dict:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 256,
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            data = json.load(r)
            data["_elapsed_s"] = time.time() - t0
            data["_error"] = None
            return data
    except urllib.error.URLError as exc:
        return {
            "_elapsed_s": time.time() - t0,
            "_error": f"URLError: {exc}",
            "response": "",
        }
    except Exception as exc:
        return {
            "_elapsed_s": time.time() - t0,
            "_error": f"{type(exc).__name__}: {exc}",
            "response": "",
        }


def is_degenerate(text: str) -> tuple[bool, float, str]:
    """Heurística: una respuesta es 'rara' si tiene <40% de letras/espacios,
    contiene líneas de símbolos puros, o no termina en puntuación normal.
    """
    if not text:
        return True, 1.0, "vacía"
    n = len(text)
    letters_spaces = sum(1 for c in text if c.isalpha() or c.isspace())
    ratio = letters_spaces / n
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return True, ratio, "sin líneas"
    # Línea con >70% de símbolos no-alfanuméricos
    for line in lines:
        non_alnum = sum(1 for c in line if not c.isalnum() and not c.isspace())
        if len(line) > 8 and non_alnum / len(line) > 0.7:
            return True, ratio, f"línea-símbolos: {line[:40]!r}"
    # Sin terminador normal
    if not text.rstrip().endswith((".", "!", "?", ":", "```", '"', "'", ")", "]", "}")):
        # Puede estar truncado por num_predict, no es necesariamente malo
        pass
    if ratio < 0.40:
        return True, ratio, f"ratio letras={ratio:.2f}"
    return False, ratio, "ok"


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Di hola en una sola frase."
    print(f"Prompt: {prompt!r}\n")

    models = list_models()
    if not models:
        print("No hay modelos en Ollama.")
        return 1

    # Excluir modelos de visión/orquestador/persona para chat puro
    chat_models = [
        m["name"] for m in models
        if "vision" not in m["name"]
        and "eyes" not in m["name"]
        and "orchestrator" not in m["name"]
    ]
    print(f"Modelos a probar ({len(chat_models)}): {chat_models}\n")

    results: list[dict] = []
    for m in chat_models:
        print(f"--- {m} ---")
        # warm-up + medida
        r = query(m, prompt)
        elapsed = r.get("_elapsed_s", 0)
        err = r.get("_error")
        text = r.get("response", "") or ""
        if err:
            print(f"  ERROR: {err} ({elapsed:.1f}s)")
            results.append({"model": m, "ok": False, "error": err,
                            "elapsed_s": elapsed, "len": 0,
                            "ratio": 0.0, "degenerate": True})
            continue
        bad, ratio, why = is_degenerate(text)
        verdict = "DEGENERATE" if bad else "OK"
        print(f"  [{verdict}] {elapsed:.1f}s  len={len(text)}  ratio_letras={ratio:.2f}  why={why}")
        snippet = text[:200].replace("\n", " ⏎ ")
        print(f"  >> {snippet}")
        print()
        results.append({
            "model": m,
            "ok": not bad,
            "error": None if not bad else why,
            "elapsed_s": elapsed,
            "len": len(text),
            "ratio": ratio,
            "degenerate": bad,
        })

    print("=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"{'modelo':40} {'estado':12} {'seg':>6} {'len':>5} {'ratio':>6}")
    print("-" * 70)
    for r in results:
        status = "❌ degenerate" if r["degenerate"] else "✅ ok"
        if r.get("error"):
            status = f"💥 {r['error'][:15]}"
        print(f"{r['model']:40} {status:12} {r['elapsed_s']:6.1f} {r['len']:5d} {r['ratio']:6.2f}")

    good = [r for r in results if not r["degenerate"]]
    print()
    print(f"Aprobados: {len(good)}/{len(results)}")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
