#!/usr/bin/env python3
r"""bago_sync_bidirectional.py

Sincroniza BAGO motor + knowledge entre instalaciones locales y GitHub.

Fuentes de verdad:
- Motor:  https://github.com/MarcValls/BAGO
- Knowledge: https://github.com/MarcValls/bago-knowledge

Instalaciones locales:
- USB/Pendrive: E:\\bago_fw
- Disco local:  C:\\bago_true

Uso:
    python bago_sync_bidirectional.py [--dry-run] [--no-push]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# ── Configuración ───────────────────────────────────────────────────────────

REPO_CONFIG = {
    "motor": {
        "github": "https://github.com/MarcValls/BAGO.git",
        "locals": {
            "usb": Path("E:\\\\bago_fw"),
            "disk": Path("C:\\\\bago_true"),
        },
    },
    "knowledge": {
        "github": "https://github.com/MarcValls/bago-knowledge.git",
        "locals": {
            "usb": Path("E:\\\\bago_fw\\\\.bago\\\\knowledge"),
            "disk": Path("C:\\\\bago_true\\\\bago-knowledge"),
        },
    },
}

def _run(cmd, cwd, timeout=30):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace')

def _git_has_changes(cwd):
    r = _run(["git", "status", "--porcelain"], cwd)
    return bool(r.stdout.strip())

def _git_current_branch(cwd):
    r = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return r.stdout.strip() or "main"

def _git_commit_all(cwd, message):
    _run(["git", "add", "-A"], cwd)
    r = _run(["git", "commit", "-m", message, "--no-verify"], cwd)
    return r.returncode == 0

def _git_fetch(cwd, remote):
    r = _run(["git", "fetch", remote], cwd, timeout=45)
    return r.returncode == 0

def _git_ahead(cwd, local_branch, remote_branch):
    r = _run(["git", "rev-list", "--count", f"{remote_branch}..{local_branch}"], cwd)
    try:
        return int(r.stdout.strip())
    except Exception:
        return 0

def _git_pull(cwd, remote, branch):
    r = _run(["git", "pull", "--no-rebase", remote, branch], cwd, timeout=60)
    return r.returncode == 0

def _git_push(cwd, remote, branch):
    r = _run(["git", "push", remote, branch], cwd, timeout=60)
    return r.returncode == 0

def _commit_auto(cwd, label):
    if not _git_has_changes(cwd):
        print(f"  [{label}] Sin cambios locales")
        return False
    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
    msg = f"sync-auto {label} @ {ts}"
    ok = _git_commit_all(cwd, msg)
    print(f"  [{label}] Auto-commit: {msg}")
    return ok

def _sync_repo(name, cfg, dry_run, no_push):
    print(f"\
=== Sync {name} ===")
    locals_ = cfg["locals"]
    ok = True

    for label, path in locals_.items():
        if not path.exists():
            print(f"  [{label}] NO EXISTE: {path}")
            ok = False
            continue
        if not (path / ".git").exists():
            print(f"  [{label}] No es repo git: {path}")
            ok = False
            continue
        if not dry_run:
            _commit_auto(path, label)
        else:
            if _git_has_changes(path):
                print(f"  [DRY][{label}] Tiene cambios locales")

    usb_path = locals_.get("usb")
    disk_path = locals_.get("disk")
    if usb_path and usb_path.exists() and disk_path and disk_path.exists():
        usb_branch = _git_current_branch(usb_path)
        disk_branch = _git_current_branch(disk_path)

        if not dry_run:
            _git_fetch(disk_path, "usb")
            ahead_usb = _git_ahead(disk_path, f"usb/{usb_branch}", f"origin/{disk_branch}")
            if ahead_usb > 0:
                print(f"  [disk] Pull desde usb ({ahead_usb} commits)")
                if not _git_pull(disk_path, "usb", usb_branch):
                    print(f"  [disk] WARN: pull desde usb tuvo conflictos")
                    ok = False
        else:
            print(f"  [DRY] Sync usb -> disk no ejecutado")

        if not dry_run:
            _git_fetch(usb_path, "disk")
            ahead_disk = _git_ahead(usb_path, f"disk/{disk_branch}", f"origin/{usb_branch}")
            if ahead_disk > 0:
                print(f"  [usb] Pull desde disk ({ahead_disk} commits)")
                if not _git_pull(usb_path, "disk", disk_branch):
                    print(f"  [usb] WARN: pull desde disk tuvo conflictos")
                    ok = False
        else:
            print(f"  [DRY] Sync disk -> usb no ejecutado")

    if not no_push:
        for label, path in locals_.items():
            if not path.exists():
                continue
            branch = _git_current_branch(path)
            if not dry_run:
                print(f"  [{label}] Push a origin/{branch}...")
                if not _git_push(path, "origin", branch):
                    print(f"  [{label}] WARN: push falló")
                    ok = False
            else:
                print(f"  [DRY][{label}] Push a origin/{branch} no ejecutado")

    return ok

def main():
    p = argparse.ArgumentParser(description="Sincroniza BAGO motor + knowledge")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-push", action="store_true")
    args = p.parse_args()

    print("BAGO Sync Bidireccional")
    print("Motor:    MarcValls/BAGO")
    print("Knowledge: MarcValls/bago-knowledge")
    print(f"USB:  E:\\\\bago_fw")
    print(f"Disk: C:\\\\bago_true")
    if args.dry_run:
        print("\
*** MODO DRY-RUN ***\
")

    ok = True
    for name, cfg in REPO_CONFIG.items():
        if not _sync_repo(name, cfg, args.dry_run, args.no_push):
            ok = False

    print("\
" + "="*50)
    print("  SYNC: " + ("OK" if ok else "CON PROBLEMAS"))
    print("="*50)
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
