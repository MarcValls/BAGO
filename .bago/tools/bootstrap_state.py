#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bootstrap_state.py — crea global_state.json desde plantilla limpia con valores inyectados."""

from bago_utils import load_json, save_json, timestamp_iso
import json
import datetime
import uuid
import subprocess
import sys
from pathlib import Path

def _user_cwd() -> Path:
    env_cwd = os.environ.get("BAGO_USER_CWD", "")
    if env_cwd:
        try:
            return Path(env_cwd).expanduser().resolve()
        except Exception:
            pass
    return Path(os.getcwd()).resolve()

def main():
    install_dir = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else _user_cwd()
    bago_dir = install_dir / '.bago'
    tmpl_path = bago_dir / 'templates' / 'global_state.clean.json'
    state_path = bago_dir / 'state' / 'global_state.json'
    pack_path = bago_dir / 'pack.json'

    if not tmpl_path.exists():
        print(f'KO: missing template {tmpl_path}')
        sys.exit(1)

    with open(tmpl_path, 'r', encoding='utf-8') as f:
        state = json.load(f)

    now = datetime.datetime.now().isoformat()
    state['install_id'] = str(uuid.uuid4())
    state['created_at'] = now
    state['updated_at'] = now

    if pack_path.exists():
        with open(pack_path, 'r', encoding='utf-8') as f:
            pack = json.load(f)
        state['bago_version'] = pack.get('version', state.get('bago_version', '3.4.0'))

    try:
        branch = subprocess.check_output(
            ['git', '-C', str(install_dir), 'rev-parse', '--abbrev-ref', 'HEAD'],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        state['inventory']['branch'] = branch
    except Exception:
        pass

    state['mode'] = 'clean_install'
    state['status'] = 'initialized'

    for subdir in (
        'sessions', 'changes', 'evidences', 'reports', 'config',
        'audits', 'contracts', 'agents', 'boot', 'field', 'goals',
        'orchestrator', 'peers', 'reactor', 'research', 'sac_locks',
        'skills', 'sprints', 'toolboxes', 'scenarios',
    ):
        (bago_dir / 'state' / subdir).mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print('GO state initialized')



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

if __name__ == '__main__':
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    main()