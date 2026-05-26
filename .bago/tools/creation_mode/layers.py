"""creation_mode.layers — Capas arquitectónicas y filtrado de archivos."""
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

import fnmatch

LAYERS: dict[str, dict] = {
    "frontend": {
        "patterns": [
            "*/frontend/**", "*/src/components/**", "*/src/ui/**", "*/src/hooks/**",
            "*/src/pages/**", "*/public/**", "*/styles/**", "*/assets/**",
            "*.css", "*.scss", "*.less", "*.tsx", "*.jsx", "*.vue", "*.svelte",
            "*.html", "*.htm",
        ],
    },
    "backend": {
        "patterns": [
            "*/backend/**", "*/src/api/**", "*/src/services/**", "*/src/models/**",
            "*/src/workers/**", "*/src/middleware/**", "*/src/core/**",
            "*.py", "*.go", "*.rs", "*.java", "*.kt", "*.rb",
        ],
    },
    "db": {
        "patterns": [
            "*/migrations/**", "*/seeds/**", "*/schema/**", "*/db/**",
            "*.sql", "*.prisma", "*.orm", "*.ddl",
        ],
    },
    "api": {
        "patterns": [
            "*/api/**", "*/openapi/**", "*/swagger/**", "*/proto/**",
            "*.yaml", "*.yml", "*.proto", "*.graphql", "*.gql", "*.wsdl",
        ],
    },
    "infra": {
        "patterns": [
            "Dockerfile*", "docker-compose*", "*/k8s/**", "*/.github/**",
            "*/terraform/**", "*/nginx/**", "*/scripts/**",
            "*.tf", "*.hcl", "*.yml", "*.yaml", ".env*",
        ],
    },
    "all": {"patterns": ["*"]},
}


def matches_layer(path: str, layer: str) -> bool:
    if not layer or layer == "all":
        return True
    cfg = LAYERS.get(layer)
    if not cfg:
        return True
    for pat in cfg.get("patterns", []):
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, "*/" + pat):
            return True
    return False
