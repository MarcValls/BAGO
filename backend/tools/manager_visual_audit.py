from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "manager" / "index.html"
PATCH_JS = ROOT / "manager" / "js" / "patch-manager.js"
OPS_JS = ROOT / "manager" / "js" / "ops-console.js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def has(text: str, needle: str) -> bool:
    return needle in text


def main() -> int:
    html = read(HTML)
    patch_js = read(PATCH_JS)
    ops_js = read(OPS_JS)

    findings: list[str] = []

    required = [
        ("pipelines view", "pm-view-matrix"),
        ("route view", "pm-view-route"),
        ("registry view", "pm-view-patch"),
        ("pipeline rail", "pm-pipeline-rail"),
        ("pipeline contract", "pm-pipeline-contract"),
        ("route board", "pm-route-board"),
        ("patch stage", "pm-stage"),
    ]
    for label, token in required:
        if not has(html, token) and not has(patch_js, token) and not has(ops_js, token):
            findings.append(f"missing:{label}")

    canonical_phrases = [
        "Pipeline para analizar y trabajar un proyecto",
        "Pipeline para actualizar o instalar release",
        "Pipeline para registrar provider",
        "Pipeline para auditar ruta y evidencia",
        "Ruta nodular",
        "Registry nodular",
    ]
    for phrase in canonical_phrases:
        if not has(html, phrase) and not has(ops_js, phrase):
            findings.append(f"vocabulary-gap:{phrase}")

    duplicate_terms = {
        "Patch Bay": html.count("Patch Bay") + patch_js.count("Patch Bay"),
        "Matriz": html.count("Matriz") + patch_js.count("Matriz"),
        "Chain": html.count("Chain") + patch_js.count("Chain") + ops_js.count("Chain"),
    }
    print("Manager visual grammar audit")
    print(f"HTML: {HTML}")
    print(f"Findings: {len(findings)}")
    for item in findings:
      print(f"- {item}")
    print("Term counts:")
    for key, value in duplicate_terms.items():
        print(f"- {key}: {value}")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
