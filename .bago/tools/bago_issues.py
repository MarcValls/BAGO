#!/usr/bin/env python3
"""bago issues — Gestiona issues asignados a BAGO via label 'bago' en GitHub."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = os.environ.get("BAGO_ISSUES_REPO", "MarcValls/BAGO")
LABEL = os.environ.get("BAGO_ISSUES_LABEL", "bago")


def _gh(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, encoding="utf-8"
    )
    return proc.returncode, proc.stdout


def cmd_list(state: str = "open", limit: int = 20) -> None:
    rc, out = _gh([
        "issue", "list",
        "--repo", REPO,
        "--label", LABEL,
        "--state", state,
        "--limit", str(limit),
        "--json", "number,title,labels,url,createdAt,author",
    ])
    if rc != 0:
        print("  ✖ Error al listar issues. ¿gh autenticado?", file=sys.stderr)
        sys.exit(1)
    items = json.loads(out)
    if not items:
        print(f"  (sin issues con label '{LABEL}' en {REPO})")
        return
    print(f"\n  Issues con label '{LABEL}' en {REPO} ({len(items)}):\n")
    for it in items:
        labels = ", ".join(l["name"] for l in it.get("labels", []))
        print(f"    #{it['number']:>4}  {it['title'][:55]}")
        print(f"         {labels}  {it['url']}")
        print()


def cmd_show(number: int) -> None:
    rc, out = _gh([
        "issue", "view", str(number),
        "--repo", REPO,
        "--json", "number,title,body,url,labels,state,createdAt,author",
    ])
    if rc != 0:
        print(f"  ✖ Issue #{number} no encontrado", file=sys.stderr)
        sys.exit(1)
    it = json.loads(out)
    labels = ", ".join(l["name"] for l in it.get("labels", []))
    print(f"\n  #{it['number']}  [{it['state'].upper()}]  {it['title']}")
    print(f"  Labels: {labels}")
    print(f"  URL:    {it['url']}")
    print(f"  Autor:  {it['author'].get('login', '?')}")
    print(f"\n  {it.get('body', '(sin descripcion)')[:500]}")
    if len(it.get('body', '')) > 500:
        print("  ...")
    print()


def cmd_take(number: int, agent: str = "codex") -> None:
    rc, out = _gh([
        "issue", "view", str(number),
        "--repo", REPO,
        "--json", "number,title,labels",
    ])
    if rc != 0:
        print(f"  ✖ Issue #{number} no encontrado", file=sys.stderr)
        sys.exit(1)
    it = json.loads(out)
    labels = [l["name"] for l in it.get("labels", [])]
    if "bago-in-progress" not in labels:
        labels.append("bago-in-progress")
    _gh(["issue", "edit", str(number), "--repo", REPO, "--add-label", "bago-in-progress"])
    _gh(["issue", "edit", str(number), "--repo", REPO, "--remove-label", "bago"])
    # Comentar asignación automática
    comment = f"Asignado a BAGO agente {agent}. Branch sugerida: fix/bago-{number}"
    _gh(["issue", "comment", str(number), "--repo", REPO, "--body", comment])
    print(f"  ✓ Issue #{number} en progreso: {it['title'][:50]}")
    print(f"    Agente: {agent}")
    print(f"    Branch sugerida: fix/bago-{number}")


def cmd_close(number: int, comment: str | None = None) -> None:
    if comment:
        _gh(["issue", "comment", str(number), "--repo", REPO, "--body", comment])
    rc, _ = _gh(["issue", "close", str(number), "--repo", REPO])
    if rc == 0:
        print(f"  ✓ Issue #{number} cerrado")
    else:
        print(f"  ✖ No se pudo cerrar issue #{number}", file=sys.stderr)


def cmd_create(title: str, body: str | None = None) -> None:
    args = ["issue", "create", "--repo", REPO, "--title", title, "--label", LABEL]
    if body:
        args += ["--body", body]
    rc, out = _gh(args)
    if rc == 0:
        print(f"  ✓ Issue creado: {out.strip()}")
    else:
        print(f"  ✖ Error creando issue", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description="BAGO issues — Gestiona issues asignados a BAGO")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Listar issues con label bago")

    p_show = sub.add_parser("show", help="Ver detalle de un issue")
    p_show.add_argument("number", type=int)

    p_take = sub.add_parser("take", help="Marcar issue como en progreso")
    p_take.add_argument("number", type=int)
    p_take.add_argument("--agent", "-a", default="codex", help="Agente BAGO asignado (default: codex)")

    p_close = sub.add_parser("close", help="Cerrar issue con comentario opcional")
    p_close.add_argument("number", type=int)
    p_close.add_argument("--comment", "-c", default=None)

    p_create = sub.add_parser("create", help="Crear issue con label bago")
    p_create.add_argument("title")
    p_create.add_argument("--body", "-b", default=None)

    args = p.parse_args()

    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "show":
        cmd_show(args.number)
    elif args.cmd == "take":
        cmd_take(args.number, args.agent)
    elif args.cmd == "close":
        cmd_close(args.number, args.comment)
    elif args.cmd == "create":
        cmd_create(args.title, args.body)


if __name__ == "__main__":
    main()
