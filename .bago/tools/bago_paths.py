#!/usr/bin/env python3
from __future__ import annotations
r"""bago_paths.py

Resuelve rutas del motor BAGO y del knowledge repository.
Lee install_config.json para saber donde esta cada cosa.
"""
""

import json
import os
from pathlib import Path

_CONFIG_FILE = Path(__file__).resolve().parents[1] / "install_config.json"

def _find_motor_root():
    here = Path(__file__).resolve().parent
    parents = list(here.parents)
    for parent in parents:
        if (parent / '.git').exists():
            return parent
    for parent in parents:
        if (parent / '.bago').exists() or (parent / 'pack.json').exists():
            return parent
    return parents[1] if len(parents) > 1 else here.parent

def get_install_config():
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding='utf-8-sig'))
        except Exception:
            pass
    return {
        "motor": {'repo_url': "", 'local_path': "."},
        "knowledge": {'repo_url': "", 'local_path': './knowledge'},
        "paths_relative_to": "motor_root",
    }

def get_motor_root():
    env = os.environ.get('BAGO_MOTOR_ROOT')
    if env:
        return Path(env).resolve()
    return _find_motor_root()

def get_knowledge_root():
    env = os.environ.get('BAGO_KNOWLEDGE_ROOT')
    if env:
        p = Path(env).resolve()
        if p.exists():
            return p
    cfg = get_install_config()
    motor = get_motor_root()
    rel = cfg.get('knowledge', {}).get('local_path', './knowledge')
    if cfg.get('paths_relative_to') == 'motor_root':
        candidate = (motor / rel).resolve()
    else:
        candidate = Path(rel).expanduser().resolve()
    if candidate.exists():
        return candidate
    for name in ('bago-knowledge', 'knowledge'):
        sibling = motor.parent / name
        if sibling.exists():
            return sibling.resolve()
    fallback = motor.parent / 'bago-knowledge'
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback.resolve()

def get_state_root():
    env = os.environ.get('BAGO_STATE_ROOT') or os.environ.get('BAGO_USER_HOME')
    if env:
        p = Path(env).resolve()
        try:
            p.mkdir(parents=True, exist_ok=True)
            test = p / '.write_test'
            test.write_text('ok')
            test.unlink()
            return p
        except Exception:
            pass
    return Path.home() / '.bago'

if __name__ == '__main__':
    print('motor:     ' + str(get_motor_root()))
    print('knowledge: ' + str(get_knowledge_root()))
    print('state:     ' + str(get_state_root()))