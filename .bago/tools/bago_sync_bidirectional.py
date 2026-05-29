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


# ── Configuración ───────────────────────────────────────────────────────────

# Detectar motor y knowledge dinamicamente via bago_paths
sys.path.insert(0, str(Path(__file__).resolve().parent))

MOTOR_ROOT = get_motor_root()
KNOWLEDGE_ROOT = get_knowledge_root()

# Detectar instalacion secundaria via env o busqueda
_alt_motor = os.environ.get("BAGO_MOTOR_ROOT_ALT")
_alt_knowledge = os.environ.get("BAGO_KNOWLEDGE_ROOT_ALT")
if not _alt_motor:
    # Buscar en todas las unidades disponibles
    for drive_letter in string.ascii_uppercase:
        drive = Path(drive_letter + ":/")
        if not drive.exists():
            continue
        for name in ("bago_true", "bago_fw", "BAGO"):
            candidate = drive / name
            if candidate.exists() and candidate.resolve() != MOTOR_ROOT.resolve():
                if (candidate / ".bago").exists() or (candidate / "pack.json").exists():
                    _alt_motor = str(candidate)
                    break
                if (candidate / ".bago" / "pack.json").exists():
                    _alt_motor = str(candidate / ".bago")
                    break
        if _alt_motor:
            break

# Inferir knowledge alternativo desde motor alternativo
if _alt_motor and not _alt_knowledge:
    alt_path = Path(_alt_motor)
    candidates = []
    if alt_path.name == '.bago':
        candidates = [alt_path / 'knowledge', alt_path.parent / 'bago-knowledge']
    else:
        candidates = [alt_path / '.bago' / 'knowledge', alt_path / 'bago-knowledge']
    for cand in candidates:
        if cand.exists() and (cand / '.git').exists():
            _alt_knowledge = str(cand)
            break
    if not _alt_knowledge:
        for cand in candidates:
            if cand.exists():
                _alt_knowledge = str(cand)
                break

REPO_CONFIG = {
    "motor": {
        "github": "https://github.com/MarcValls/BAGO.git",
        "locals": {
            "primary": MOTOR_ROOT,
            "secondary": Path(_alt_motor) if _alt_motor else MOTOR_ROOT,
        },
    },
    "knowledge": {
        "github": "https://github.com/MarcValls/bago-knowledge.git",
        "locals": {
            "primary": KNOWLEDGE_ROOT,
            "secondary": Path(_alt_knowledge) if _alt_knowledge else KNOWLEDGE_ROOT,
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

    # Sync entre locales (primary <-> secondary)
    paths = list(locals_.values())
    # Eliminar duplicados
    seen = set()
    uniq = []
    for pp in paths:
        rp = str(pp.resolve())
        if rp not in seen:
            seen.add(rp)
            uniq.append(pp)
    paths = uniq
    if len(paths) >= 2 and all(p.exists() for p in paths):
        p1, p2 = paths[0], paths[1]
        b1 = _git_current_branch(p1)
        b2 = _git_current_branch(p2)

        if not dry_run:
            _git_fetch(p2, 'primary' if paths[0] == p1 else 'secondary')
            ahead1 = _git_ahead(p2, f'primary/{b1}', f'origin/{b2}')
            if ahead1 > 0:
                print(f'  [secondary] Pull desde primary ({ahead1} commits)')
                if not _git_pull(p2, 'primary', b1):
                    print('  [secondary] WARN: pull tuvo conflictos')
                    ok = False
        else:
            print('  [DRY] Sync primary -> secondary no ejecutado')

        if not dry_run:
            _git_fetch(p1, 'secondary' if paths[1] == p2 else 'primary')
            ahead2 = _git_ahead(p1, f'secondary/{b2}', f'origin/{b1}')
            if ahead2 > 0:
                print(f'  [primary] Pull desde secondary ({ahead2} commits)')
                if not _git_pull(p1, 'secondary', b2):
                    print('  [primary] WARN: pull tuvo conflictos')
                    ok = False
        else:
            print('  [DRY] Sync secondary -> primary no ejecutado')

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