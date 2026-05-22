"""npath — Neural Path System entry point.

Sistema local de grafos versionados donde las ramas funcionan como
trayectorias cognitivas activables, fusionables y reversibles.

Uso:
  bago npath init
  bago npath branch <nombre> [descripción]
  bago npath branches
  bago npath commit <contenido> [--branch <rama>] [--type <tipo>] [--weight <0-1>]
  bago npath log [<rama>|all] [--limit N]
  bago npath map [<rama>]
  bago npath merge <rama1> <rama2> [--content <desc>] [--strategy manual|weighted]
  bago npath unmerge <merge-id>
  bago npath reactivate-merge <merge-id>
  bago npath split <node-id> --remove <rama> [--content <desc>]
  bago npath activate <rama> [--weight <0-1>]
  bago npath deactivate <rama>
  bago npath recall <query> [--limit N] [--no-semantic]
  bago npath status
  bago npath node <node-id>
  bago npath delete-node <node-id>
  bago npath --test

Integración Ollama (red de pensamiento local):
  bago npath ollama-status
  bago npath think <pregunta> [--branch <rama>] [--model <m>] [--commit]
  bago npath reflect [<rama>] [--model <m>] [--commit]
  bago npath suggest [<rama>] [--model <m>]
  bago npath evolve  [--branch <rama>] [--nodes N] [--model <m>] [--no-commit]

Búsqueda semántica (embeddings vía Ollama):
  bago npath embed   [<rama>|all] [--model <m>] [--batch N]
  bago npath similar <node-id>   [--limit N] [--threshold 0.5]

DB: .bago/state/npath.db
"""
from __future__ import annotations

import sys

from npath._db import (
    _connect, _get_current_branch,
    CYAN, RED, cmd_init,
)
from npath._graph import (
    cmd_branch, cmd_branches, cmd_commit,
    cmd_merge, cmd_unmerge, cmd_reactivate_merge,
    cmd_split, cmd_activate, cmd_deactivate,
)
from npath._view import cmd_log, cmd_map, cmd_status, cmd_node, cmd_delete_node, cmd_recall
from npath._ollama import (
    cmd_think, cmd_reflect, cmd_suggest, cmd_evolve, cmd_ollama_status,
)
from npath._embeddings import cmd_embed, cmd_similar
from npath._tests import _run_tests


def _usage() -> None:
    print(__doc__)


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        _usage()
        return

    cmd  = args[0].lower()
    rest = args[1:]

    # ── init ──────────────────────────────────────────────────────────────────
    if cmd == "init":
        cmd_init()

    # ── branch ────────────────────────────────────────────────────────────────
    elif cmd == "branch":
        if not rest:
            conn = _connect()
            cur  = _get_current_branch(conn)
            conn.close()
            print(f"  Rama activa: {CYAN(cur)}")
            print("  Para listar: bago npath branches")
        else:
            name = rest[0]
            desc = rest[1] if len(rest) > 1 else ""
            cmd_branch(name, desc)

    elif cmd == "branches":
        cmd_branches()

    # ── commit ────────────────────────────────────────────────────────────────
    elif cmd == "commit":
        if not rest:
            print(RED("❌ Uso: bago npath commit <contenido> [--branch <rama>] [--type <tipo>] [--weight <0-1>]"))
            sys.exit(1)
        content = rest[0]
        branch  = None
        ntype   = "concept"
        weight  = 0.5
        i = 1
        while i < len(rest):
            if rest[i] == "--branch" and i + 1 < len(rest):
                branch = rest[i + 1]; i += 2
            elif rest[i] == "--type" and i + 1 < len(rest):
                ntype = rest[i + 1]; i += 2
            elif rest[i] == "--weight" and i + 1 < len(rest):
                try:
                    weight = float(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1
        cmd_commit(content, branch=branch, ntype=ntype, weight=weight)

    # ── log ───────────────────────────────────────────────────────────────────
    elif cmd == "log":
        branch = None
        limit  = 20
        i = 0
        while i < len(rest):
            if rest[i] == "--branch" and i + 1 < len(rest):
                branch = rest[i + 1]; i += 2
            elif rest[i] == "--limit" and i + 1 < len(rest):
                try:
                    limit = int(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                branch = rest[i]; i += 1
        cmd_log(branch=branch, limit=limit)

    # ── map ───────────────────────────────────────────────────────────────────
    elif cmd == "map":
        branch = rest[0] if rest and not rest[0].startswith("--") else None
        cmd_map(branch=branch)

    # ── merge ─────────────────────────────────────────────────────────────────
    elif cmd == "merge":
        if len(rest) < 2:
            print(RED("❌ Uso: bago npath merge <rama1> <rama2> [--content <desc>] [--strategy manual|weighted]"))
            sys.exit(1)
        b1, b2   = rest[0], rest[1]
        content  = None
        strategy = "manual"
        i = 2
        while i < len(rest):
            if rest[i] == "--content" and i + 1 < len(rest):
                content = rest[i + 1]; i += 2
            elif rest[i] == "--strategy" and i + 1 < len(rest):
                strategy = rest[i + 1]; i += 2
            else:
                i += 1
        cmd_merge(b1, b2, content=content, strategy=strategy)

    elif cmd == "unmerge":
        if not rest:
            print(RED("❌ Uso: bago npath unmerge <merge-id>")); sys.exit(1)
        cmd_unmerge(rest[0])

    elif cmd == "reactivate-merge":
        if not rest:
            print(RED("❌ Uso: bago npath reactivate-merge <merge-id>")); sys.exit(1)
        cmd_reactivate_merge(rest[0])

    # ── split ─────────────────────────────────────────────────────────────────
    elif cmd == "split":
        if not rest:
            print(RED("❌ Uso: bago npath split <node-id> --remove <rama>")); sys.exit(1)
        node_id       = rest[0]
        remove_branch = None
        content       = None
        i = 1
        while i < len(rest):
            if rest[i] == "--remove" and i + 1 < len(rest):
                remove_branch = rest[i + 1]; i += 2
            elif rest[i] == "--content" and i + 1 < len(rest):
                content = rest[i + 1]; i += 2
            else:
                i += 1
        if not remove_branch:
            print(RED("❌ Usa --remove <rama> para indicar qué influencia eliminar")); sys.exit(1)
        cmd_split(node_id, remove_branch, content=content)

    # ── activate / deactivate ─────────────────────────────────────────────────
    elif cmd == "activate":
        if not rest:
            print(RED("❌ Uso: bago npath activate <rama> [--weight <0-1>]")); sys.exit(1)
        branch = rest[0]
        weight = None
        if "--weight" in rest:
            idx = rest.index("--weight")
            if idx + 1 < len(rest):
                try:
                    weight = float(rest[idx + 1])
                except ValueError:
                    pass
        cmd_activate(branch, weight=weight)

    elif cmd == "deactivate":
        if not rest:
            print(RED("❌ Uso: bago npath deactivate <rama>")); sys.exit(1)
        cmd_deactivate(rest[0])

    # ── recall ────────────────────────────────────────────────────────────────
    elif cmd == "recall":
        if not rest:
            print(RED("❌ Uso: bago npath recall <query> [--limit N] [--no-semantic]")); sys.exit(1)
        query    = rest[0]
        limit    = 10
        semantic = True
        i = 1
        while i < len(rest):
            if rest[i] == "--limit" and i + 1 < len(rest):
                try:
                    limit = int(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            elif rest[i] == "--no-semantic":
                semantic = False; i += 1
            else:
                i += 1
        cmd_recall(query, limit=limit, semantic=semantic)

    # ── status ────────────────────────────────────────────────────────────────
    elif cmd == "status":
        cmd_status()

    elif cmd == "node":
        if not rest:
            print(RED("❌ Uso: bago npath node <node-id>")); sys.exit(1)
        cmd_node(rest[0])

    elif cmd in ("delete-node", "rm"):
        if not rest:
            print(RED("❌ Uso: bago npath delete-node <node-id>")); sys.exit(1)
        cmd_delete_node(rest[0])

    # ── Ollama ────────────────────────────────────────────────────────────────
    elif cmd in ("ollama", "ollama-status"):
        cmd_ollama_status()

    elif cmd == "think":
        if not rest:
            print(RED("❌ Uso: bago npath think <pregunta> [--branch <rama>] [--model <m>] [--commit]"))
            sys.exit(1)
        query     = rest[0]
        branch    = None
        model     = None
        do_commit = False
        i = 1
        while i < len(rest):
            if rest[i] == "--branch" and i + 1 < len(rest):
                branch = rest[i + 1]; i += 2
            elif rest[i] == "--model" and i + 1 < len(rest):
                model = rest[i + 1]; i += 2
            elif rest[i] == "--commit":
                do_commit = True; i += 1
            else:
                i += 1
        cmd_think(query, branch=branch, model=model, do_commit=do_commit)

    elif cmd == "reflect":
        branch    = None
        model     = None
        do_commit = False
        i = 0
        while i < len(rest):
            if rest[i] == "--branch" and i + 1 < len(rest):
                branch = rest[i + 1]; i += 2
            elif rest[i] == "--model" and i + 1 < len(rest):
                model = rest[i + 1]; i += 2
            elif rest[i] == "--commit":
                do_commit = True; i += 1
            else:
                branch = rest[i]; i += 1
        cmd_reflect(branch=branch, model=model, do_commit=do_commit)

    elif cmd == "suggest":
        branch = None
        model  = None
        i = 0
        while i < len(rest):
            if rest[i] == "--branch" and i + 1 < len(rest):
                branch = rest[i + 1]; i += 2
            elif rest[i] == "--model" and i + 1 < len(rest):
                model = rest[i + 1]; i += 2
            else:
                branch = rest[i]; i += 1
        cmd_suggest(branch=branch, model=model)

    elif cmd == "evolve":
        branch    = None
        model     = None
        n_nodes   = 3
        do_commit = True
        i = 0
        while i < len(rest):
            if rest[i] == "--branch" and i + 1 < len(rest):
                branch = rest[i + 1]; i += 2
            elif rest[i] == "--model" and i + 1 < len(rest):
                model = rest[i + 1]; i += 2
            elif rest[i] == "--nodes" and i + 1 < len(rest):
                try:
                    n_nodes = int(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            elif rest[i] == "--no-commit":
                do_commit = False; i += 1
            else:
                i += 1
        cmd_evolve(branch=branch, model=model, n_nodes=n_nodes, do_commit=do_commit)

    # ── Embeddings ────────────────────────────────────────────────────────────
    elif cmd == "embed":
        branch = None
        model  = None
        batch  = 50
        i = 0
        while i < len(rest):
            if rest[i] == "--model" and i + 1 < len(rest):
                model = rest[i + 1]; i += 2
            elif rest[i] == "--batch" and i + 1 < len(rest):
                try:
                    batch = int(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            elif not rest[i].startswith("--"):
                branch = rest[i]; i += 1
            else:
                i += 1
        cmd_embed(branch=branch, model=model, batch=batch)

    elif cmd == "similar":
        if not rest:
            print(RED("❌ Uso: bago npath similar <node-id> [--limit N] [--threshold 0.5]"))
            sys.exit(1)
        node_id   = rest[0]
        limit     = 8
        threshold = 0.5
        i = 1
        while i < len(rest):
            if rest[i] == "--limit" and i + 1 < len(rest):
                try:
                    limit = int(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            elif rest[i] == "--threshold" and i + 1 < len(rest):
                try:
                    threshold = float(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1
        cmd_similar(node_id, limit=limit, threshold=threshold)

    # ── test ──────────────────────────────────────────────────────────────────
    elif cmd == "--test":
        _run_tests()

    else:
        print(RED(f"❌ Subcomando desconocido: '{cmd}'"))
        print("   Usa: bago npath --help")
        sys.exit(1)


if __name__ == "__main__":
    main()
