"""test_stream.py — Cliente SSE paciente para verificar el fix del payload
canónico de error. Lee hasta 'done' o hasta timeout.
"""
import json
import sys
import time
import urllib.request


def post_chat_stream(message: str, timeout_s: int = 120) -> None:
    url = "http://127.0.0.1:8080/chat/stream"
    body = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    chunks: list[str] = []
    diagnostics: list[dict] = []
    done_payload = None
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        print(f"[HTTP {resp.status}] stream abierto, leyendo...")
        for raw in resp:
            elapsed = time.time() - started
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if not line.startswith("data: "):
                continue
            payload_str = line[len("data: "):]
            try:
                payload = json.loads(payload_str)
            except Exception:
                print(f"  [{elapsed:.1f}s] non-json: {payload_str[:120]}")
                continue

            if "chunk" in payload:
                chunks.append(payload["chunk"])
                print(f"  [{elapsed:.1f}s] chunk: {payload['chunk'][:140]}")
            elif "diagnostic" in payload:
                diagnostics.append(payload)
                print(f"  [{elapsed:.1f}s] DIAGNOSTIC: {json.dumps(payload, ensure_ascii=False)[:200]}")
            elif "error" in payload:
                print(f"  [{elapsed:.1f}s] ERROR: {payload['error']}")
            elif payload.get("done"):
                done_payload = payload
                print(f"  [{elapsed:.1f}s] DONE: {payload}")
                break

    print()
    print("=" * 60)
    print(f"Resumen: {len(chunks)} chunks visibles al usuario, "
          f"{len(diagnostics)} diagnostics, done={done_payload}")
    full = "".join(chunks)
    if full.strip().startswith("{"):
        # Verificar que NO es el payload canónico de error
        try:
            parsed = json.loads(full)
            actions = parsed.get("validation_actions") if isinstance(parsed, dict) else None
            ev = parsed.get("evidence") if isinstance(parsed, dict) else None
            if actions and "repair_response" in actions:
                print("❌ FALLO: el payload canónico de error se filtró al usuario")
            elif ev and isinstance(ev, list) and ev and ev[0].get("type") == "validation_error":
                print("❌ FALLO: evidence[0].type=validation_error llegó al usuario")
            else:
                print("✅ OK: usuario recibió JSON pero no es el payload canónico de error")
        except Exception as exc:
            print(f"  (json parse fail: {exc})")
    else:
        if full.startswith("⚠️"):
            print("✅ OK: usuario recibió mensaje legible de error (no JSON crudo)")
        else:
            print("✅ OK: usuario recibió texto normal")


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "genera un texto hablando sobre bago con diagramas mermaid"
    post_chat_stream(msg)
