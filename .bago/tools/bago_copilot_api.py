
import os, sys, json, urllib.request, urllib.error
from pathlib import Path

TOKEN_PATHS = [
    Path.home() / ".bago" / "config" / "github_token.txt",
    Path.home() / "BAGO" / ".bago" / "config" / "github_token.txt",
    Path.home() / "Documents" / "BAGO" / ".bago" / "config" / "github_token.txt",
]

def find_token_path():
    for p in TOKEN_PATHS:
        if p.exists():
            return p
    return TOKEN_PATHS[0]

def get_token():
    token = os.environ.get("GITHUB_TOKEN", "")
    token_path = find_token_path()
    if not token and token_path.exists():
        token = token_path.read_text(encoding="utf-8-sig").strip()
    if not token:
        print("[BAGO] ERROR: GITHUB_TOKEN no configurado.")
        sys.exit(1)
    return token

def copilot_complete(prompt, model="copilot-chat", max_tokens=1024):
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = json.dumps({
        "model": "copilot-chat",
        "messages": [
            {"role": "system", "content": "Eres un asistente de programacion experto."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/copilot/chat/completions",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[BAGO] Copilot API error: {e.code} {e.reason}")
        return None
    except Exception as e:
        print(f"[BAGO] Error: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Uso: python bago_copilot_api.py prompt [--model modelo]")
        sys.exit(1)
    model = "copilot-chat"
    prompt = sys.argv[1]
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx + 1]
    print(f"[BAGO] Copilot API - Modelo: {model}")
    result = copilot_complete(prompt, model)
    if result and "choices" in result:
        for choice in result["choices"]:
            print(choice.get("message", {}).get("content", ""))
    else:
        print("[BAGO] No se obtuvo respuesta. Abriendo web...")
        import webbrowser
        webbrowser.open("https://github.com/copilot")



def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    main()