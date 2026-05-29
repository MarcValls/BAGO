#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
git_context.py - Integracion de contexto git en BAGO.

Captura el estado git del repositorio activo:
  - Branch actual y upstream
  - Archivos sin commitear (staged, modified, untracked)
  - Commits recientes (log corto)
  - Contribuidores activos del periodo
  - Diferencias con rama base

Modos:
  python3 git_context.py              # estado completo
  python3 git_context.py --brief      # resumen de una linea
  python3 git_context.py --since 7d   # actividad de los ultimos 7 dias
  python3 git_context.py --log 10     # ultimos N commits
  python3 git_context.py --diff       # diff estadistico de archivos no staged
  python3 git_context.py --json       # output JSON (para integracion)
  python3 git_context.py --inject     # inyecta en context_map del repo activo
  python3 git_context.py --test

Integracion con bago analyze:
  Cuando se llama con --inject, escribe .git_bago_context.json
  en el repo activo para que context_map.py lo incluya.
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso
import argparse, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd, cwd=None, timeout=10):
    """Ejecuta git y retorna stdout. Retorna '' en caso de error."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, check=False
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _find_git_root(start=None):
    """Busca el directorio raiz del repo git desde start o cwd."""
    if start:
        cwd = Path(start)
    else:
        from _cwd import get_user_cwd
        cwd = get_user_cwd()
    current = cwd
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _git_branch(git_root):
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=git_root)
    upstream = _run(["git", "rev-parse", "--abbrev-ref", "@{u}"], cwd=git_root)
    return branch or "HEAD", upstream or None


def _git_status(git_root):
    """Retorna dict con staged, modified, untracked counts y listas."""
    out = _run(["git", "status", "--porcelain"], cwd=git_root)
    staged, modified, untracked = [], [], []
    for line in out.splitlines():
        if not line.strip():
            continue
        x, y = line[0], line[1]
        fname = line[3:].strip()
        if x != " " and x != "?":
            staged.append(fname)
        if y == "M":
            modified.append(fname)
        if x == "?" and y == "?":
            untracked.append(fname)
    return {
        "staged": staged, "modified": modified, "untracked": untracked,
        "clean": not (staged or modified or untracked)
    }


def _git_log(git_root, n=10, since=None):
    """Retorna lista de commits recientes."""
    fmt = "%H|%h|%s|%an|%ad"
    cmd = ["git", "log", "--format={}".format(fmt), "--date=short", "-{}".format(n)]
    if since:
        cmd.append("--since={}".format(since))
    out = _run(cmd, cwd=git_root)
    commits = []
    for line in out.splitlines():
        if "|" not in line:
            continue
        parts = line.split("|", 4)
        if len(parts) >= 5:
            commits.append({
                "sha": parts[0], "short": parts[1],
                "subject": parts[2], "author": parts[3], "date": parts[4]
            })
    return commits


def _git_authors(git_root, since="4.weeks.ago"):
    """Retorna los autores con mas commits en el periodo."""
    out = _run(["git", "shortlog", "-sn", "--no-merges",
                "--since={}".format(since)], cwd=git_root)
    authors = []
    for line in out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            authors.append({"commits": int(parts[0]), "name": parts[1]})
    return authors[:5]


def _git_diff_stat(git_root):
    """Retorna estadisticas de diff de archivos no staged."""
    out = _run(["git", "diff", "--stat"], cwd=git_root)
    return out.splitlines() if out else []


def _git_stash(git_root):
    """Retorna el numero de stashes."""
    out = _run(["git", "stash", "list"], cwd=git_root)
    return len([l for l in out.splitlines() if l.strip()])


def _since_str(days_str):
    """Convierte '7d', '2w', '1m' a string para git --since."""
    if days_str.endswith("d"):
        return "{}.days.ago".format(days_str[:-1])
    elif days_str.endswith("w"):
        return "{}.weeks.ago".format(days_str[:-1])
    elif days_str.endswith("m"):
        weeks = int(days_str[:-1]) * 4
        return "{}.weeks.ago".format(weeks)
    return days_str


def collect_context(git_root, n_log=10, since=None):
    """Recopila el contexto git completo del repo."""
    branch, upstream = _git_branch(git_root)
    status = _git_status(git_root)
    log = _git_log(git_root, n=n_log, since=since)
    authors = _git_authors(git_root, since=since or "4.weeks.ago")
    stashes = _git_stash(git_root)

    # Estadisticas del repo
    total_commits = _run(["git", "rev-list", "--count", "HEAD"], cwd=git_root)
    try:
        total_commits = int(total_commits)
    except ValueError:
        total_commits = 0

    return {
        "repo": str(git_root.name),
        "repo_path": str(git_root),
        "branch": branch,
        "upstream": upstream,
        "total_commits": total_commits,
        "stashes": stashes,
        "status": status,
        "recent_commits": log,
        "top_authors": authors,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def render_brief(ctx):
    """Imprime una linea de resumen."""
    st = ctx["status"]
    dirty = "" if st["clean"] else " [dirty: +{} ~{}]".format(
        len(st["staged"]) + len(st["untracked"]), len(st["modified"]))
    last = ctx["recent_commits"][0]["subject"][:50] if ctx["recent_commits"] else "—"
    print("  {}  {}{}  commits:{} | last: {}".format(
        ctx["repo"], ctx["branch"], dirty, ctx["total_commits"], last))


def render_full(ctx, diff_stat=None):
    """Render completo en terminal."""
    print()
    print("  GIT Context — {}".format(ctx["repo"]))
    print()
    print("  Branch   : {} {}".format(
        ctx["branch"],
        "-> {}".format(ctx["upstream"]) if ctx["upstream"] else "(sin upstream)"))
    print("  Commits  : {} total".format(ctx["total_commits"]))
    print("  Stashes  : {}".format(ctx["stashes"]))
    print()

    st = ctx["status"]
    if st["clean"]:
        print("  Worktree : LIMPIO (sin cambios)")
    else:
        print("  Worktree : MODIFICADO")
        if st["staged"]:
            print("    Staged    ({}) :".format(len(st["staged"])))
            for f in st["staged"][:8]:
                print("      + {}".format(f))
            if len(st["staged"]) > 8:
                print("      ... y {} mas".format(len(st["staged"]) - 8))
        if st["modified"]:
            print("    Modified  ({}) :".format(len(st["modified"])))
            for f in st["modified"][:8]:
                print("      ~ {}".format(f))
        if st["untracked"]:
            print("    Untracked ({}) :".format(len(st["untracked"])))
            for f in st["untracked"][:6]:
                print("      ? {}".format(f))
    print()

    if ctx["recent_commits"]:
        print("  Commits recientes:")
        for c in ctx["recent_commits"][:8]:
            print("    {} {} {} ({})".format(
                c["short"], c["date"],
                c["subject"][:55] + ("..." if len(c["subject"]) > 55 else ""),
                c["author"]))
        print()

    if ctx["top_authors"]:
        print("  Top autores (4 semanas):")
        for a in ctx["top_authors"]:
            print("    {:>4} commits  {}".format(a["commits"], a["name"]))
        print()

    if diff_stat:
        print("  Diff stat:")
        for line in diff_stat[:10]:
            print("    {}".format(line))
        print()


def inject_context(git_root, ctx):
    """Escribe .git_bago_context.json en el repo para que context_map lo lea."""
    out_path = git_root / ".git_bago_context.json"
    # Excluir datos grandes para el inyectable
    injectable = {k: v for k, v in ctx.items()
                  if k not in ("recent_commits",)}
    injectable["recent_commits"] = ctx["recent_commits"][:5]
    out_path.write_text(json.dumps(injectable, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print("  Contexto inyectado en: {}".format(out_path))
    return out_path


def _run_tests():
    print("  Ejecutando tests de git_context.py...")

    import tempfile

    # Crear un mini repo git de prueba
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Detect what default branch name this git installation uses
        _default_branch_result = subprocess.run(
            ["git", "config", "--global", "init.defaultBranch"],
            capture_output=True, text=True
        )
        _default_branch = _default_branch_result.stdout.strip() or None

        # Init repo — try with explicit branch first (git >= 2.28)
        if _default_branch:
            _run(["git", "init", f"--initial-branch={_default_branch}"], cwd=tmppath)
        else:
            _run(["git", "init", "--initial-branch=main"], cwd=tmppath)
            _run(["git", "init"], cwd=tmppath)
        _run(["git", "config", "user.email", "test@test.com"], cwd=tmppath)
        _run(["git", "config", "user.name", "Tester"], cwd=tmppath)

        # Crear commit
        (tmppath / "README.md").write_text("# Test\n")
        _run(["git", "add", "."], cwd=tmppath)
        _run(["git", "commit", "-m", "Initial commit"], cwd=tmppath)

        # Agregar archivo no trackeado
        (tmppath / "new_file.py").write_text("x = 1\n")

        # Test _find_git_root
        subdir = tmppath / "subdir"
        subdir.mkdir()
        found = _find_git_root(subdir)
        assert found == tmppath, "git root no encontrado: {}".format(found)

        # Test _git_branch — accept whatever branch name git chose (main, master, trunk, etc.)
        branch, _ = _git_branch(tmppath)
        assert branch, "branch vacía: {}".format(branch)

        # Test _git_status
        st = _git_status(tmppath)
        assert not st["staged"], "staged inesperado"
        assert "new_file.py" in st["untracked"], "untracked no detectado"

        # Test _git_log
        log = _git_log(tmppath, n=5)
        assert len(log) == 1, "log inesperado: {}".format(log)
        assert "Initial commit" in log[0]["subject"]

        # Test collect_context
        ctx = collect_context(tmppath, n_log=5)
        assert ctx["repo"] == tmppath.name
        assert ctx["branch"], "branch vacía en ctx: {}".format(ctx.get("branch"))
        assert ctx["total_commits"] == 1
        assert "new_file.py" in ctx["status"]["untracked"]

        # Test inject_context
        out = inject_context(tmppath, ctx)
        assert out.exists(), "archivo inyectado no creado"
        data = json.loads(out.read_text())
        assert data["branch"], "branch vacía en datos inyectados: {}".format(data.get("branch"))

    print("  OK: todos los tests pasaron (5/5)")


def main():
    p = argparse.ArgumentParser(description="Contexto git para BAGO")
    p.add_argument("--brief", "-b", action="store_true", help="Resumen de una linea")
    p.add_argument("--since", default=None, help="Periodo (7d, 2w, 1m)")
    p.add_argument("--log", type=int, default=10, dest="n_log", metavar="N",
                   help="Numero de commits a mostrar (default: 10)")
    p.add_argument("--diff", action="store_true", help="Mostrar diff estadistico")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="Output JSON (para integracion)")
    p.add_argument("--inject", action="store_true",
                   help="Inyectar contexto en .git_bago_context.json del repo")
    p.add_argument("--repo", default=None, help="Ruta al repo (default: cwd)")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()

    if args.test:
        _run_tests()
        return

    # Encontrar el repo git
    start = args.repo or os.getcwd()
    git_root = _find_git_root(start)

    if not git_root:
        print("  ERROR: no se encontro repositorio git en {}".format(start))
        raise SystemExit(1)

    since_str = _since_str(args.since) if args.since else None
    ctx = collect_context(git_root, n_log=args.n_log, since=since_str)

    if args.as_json:
        print(json.dumps(ctx, indent=2, ensure_ascii=False))
        return

    if args.inject:
        inject_context(git_root, ctx)
        return

    diff_stat = _git_diff_stat(git_root) if args.diff else None

    if args.brief:
        render_brief(ctx)
    else:
        render_full(ctx, diff_stat=diff_stat)


if __name__ == "__main__":
    main()
