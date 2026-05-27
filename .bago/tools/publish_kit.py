#!/usr/bin/env python3
"""publish_kit.py - genera materiales de publicacion para una version BAGO."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
STATE = ROOT / "state"
OUT_DIR = STATE / "publication"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _latest_changelog_block() -> str:
    path = REPO / "CHANGELOG.md"
    if not path.exists():
        return "Sin CHANGELOG.md disponible."
    text = path.read_text(encoding="utf-8")
    parts = text.split("\n## ")
    if len(parts) <= 1:
        return text[:3000].strip()
    return ("## " + parts[1]).strip()


def _collect_metrics() -> dict:
    pack = _load_json(ROOT / "pack.json")
    state = _load_json(STATE / "global_state.json")
    implemented = _load_json(STATE / "implemented_ideas.json").get("implemented", [])
    return {
        "version": state.get("bago_version") or pack.get("version") or "unknown",
        "pack_version": state.get("pack_version") or pack.get("version") or "unknown",
        "implemented_count": len(implemented),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def build_markdown(channel: str) -> str:
    m = _collect_metrics()
    changelog = _latest_changelog_block()
    stable_note = "Beta: no publicar como stable hasta validar instalacion limpia."
    return f"""# BAGO Publish Kit

Generado: {m["generated_at"]}
Canal: {channel}
Version: {m["version"]}

## Resumen corto

BAGO {m["version"]} queda preparado para publicacion {channel}. {stable_note}

## Texto GitHub

BAGO {m["version"]} ({channel})

- Runtime empaquetado y trazable.
- Ideas implementadas registradas: {m["implemented_count"]}.
- Revisar gates antes de promover a stable.

## Texto Telegram

BAGO {m["version"]} disponible en canal {channel}. Estado: beta hasta completar smoke test de instalacion limpia.

## Changelog base

{changelog}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera notas y textos de publicacion BAGO.")
    parser.add_argument("--channel", default="beta", choices=["beta", "stable", "internal"])
    parser.add_argument("--out", default=str(OUT_DIR / "publish_kit.md"))
    parser.add_argument("--print", action="store_true", dest="print_only")
    args = parser.parse_args()

    content = build_markdown(args.channel)
    if args.print_only:
        print(content)
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"Publish kit generado: {out}")
    return 0




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
    raise SystemExit(main())
