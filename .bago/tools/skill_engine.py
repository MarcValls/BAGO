#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import get_scan_root, load_json, print_test_results, save_json, timestamp_iso

TOOLS_DIR = Path(__file__).resolve().parent
SCAN_ROOT = Path.cwd()
BAGO_ROOT = SCAN_ROOT / '.bago'
STATE = BAGO_ROOT / 'state'
SKILLS_DIR = STATE / 'skills'
REGISTRY_FILE = STATE / 'skill_registry.json'
GS_FILE = STATE / 'global_state.json'

STEP_NAMES = [
    ('C', 'OBSERVE'), ('C#', 'DESCRIBE'), ('D', 'COMPARE'), ('D#', 'DETECT'),
    ('E', 'PROPOSE'), ('F', 'SELECT'), ('F#', 'PLAN'), ('G', 'ACT'),
    ('G#', 'VALIDATE'), ('A', 'RECORD'), ('A#', 'REFLECT'), ('B', 'REST'),
]


def _resolve_bago_root(scan_root: Path) -> Path:
    scan_root = Path(scan_root).resolve()
    if scan_root.name == '.bago':
        return scan_root
    return scan_root / '.bago'


def configure_paths(root_override: str | None = None) -> Path:
    global SCAN_ROOT, BAGO_ROOT, STATE, SKILLS_DIR, REGISTRY_FILE, GS_FILE
    SCAN_ROOT = get_scan_root(root_override)
    BAGO_ROOT = _resolve_bago_root(SCAN_ROOT)
    STATE = BAGO_ROOT / 'state'
    SKILLS_DIR = STATE / 'skills'
    REGISTRY_FILE = STATE / 'skill_registry.json'
    GS_FILE = STATE / 'global_state.json'
    return SCAN_ROOT


configure_paths()


@dataclass
class SkillResult:
    skill_id: str
    radius_gained: float = 0.0
    validate: str = 'WARN'
    fingerprint: list[str] = field(default_factory=list)
    state_vector: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=timestamp_iso)

    def to_dict(self) -> dict:
        return {
            'skill_id': self.skill_id,
            'radius_gained': self.radius_gained,
            'validate': self.validate,
            'fingerprint': list(self.fingerprint),
            'state_vector': dict(self.state_vector),
            'timestamp': self.timestamp,
        }


def _load_registry() -> dict:
    return load_json(REGISTRY_FILE, {})


def _skill_file(skill_id: str, suffix: str = '') -> Path:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    return SKILLS_DIR / f'{skill_id}{suffix}.json'


def _load_skill_state(skill_id: str) -> dict:
    return load_json(_skill_file(skill_id), {'cycles': [], 'total_radius': 0.0})


def _save_skill_state(skill_id: str, data: dict) -> None:
    save_json(_skill_file(skill_id), data)


def _load_skill_gradient(skill_id: str) -> dict:
    default = {'step_weights': {name: 1.0 for _, name in STEP_NAMES}, 'last_delta': 0.0, 'last_validate': 'WARN'}
    return load_json(_skill_file(skill_id, '_gradient'), default)


def _save_skill_gradient(skill_id: str, data: dict) -> None:
    save_json(_skill_file(skill_id, '_gradient'), data)


def _load_skill_episodic(skill_id: str) -> dict:
    return load_json(_skill_file(skill_id, '_episodic'), {'episodes': []})


def _save_skill_episodic(skill_id: str, data: dict) -> None:
    save_json(_skill_file(skill_id, '_episodic'), data)


def _load_gs() -> dict:
    return load_json(GS_FILE, {})


def run_skill(skill_id: str, registry: dict | None = None) -> SkillResult:
    registry = registry or _load_registry()
    entry = registry.get(skill_id)
    if not entry:
        return SkillResult(skill_id=skill_id, validate='FAIL', fingerprint=['unknown-skill'])

    step_indices = list(entry.get('steps', [0, 3, 4, 5, 8, 9, 10, 11]))
    phase = int(entry.get('phase', step_indices[0] if step_indices else 0)) % 12
    state = _load_skill_state(skill_id)
    gradient = _load_skill_gradient(skill_id)
    episodic = _load_skill_episodic(skill_id)
    gs = _load_gs()
    now = timestamp_iso()
    issues: list[str] = []

    health = gs.get('health_score', {}).get('score', 100)
    if isinstance(health, (int, float)) and health < 80:
        issues.append(f'health={health}')
    if gs.get('guardian_findings', {}).get('errors'):
        issues.append('guardian-errors')

    rotated = [(phase + i) % 12 for i in range(12)]
    executed = [idx for idx in rotated if idx in step_indices]
    proposals: list[dict] = []
    if issues:
        proposals = [{'title': f'Address {item}', 'radius_gain': 0.25} for item in issues]
    else:
        proposals = [{'title': 'Consolidate stable state', 'radius_gain': 0.1}]
    selected = proposals[: max(1, min(2, len(proposals)))]
    radius = round(sum(float(item.get('radius_gain', 0.0)) for item in selected), 4)
    validate = 'WARN' if issues else 'GO'

    record = {
        'at': now,
        'phase': phase,
        'executed_steps': executed,
        'issues': list(issues),
        'selected': list(selected),
        'validate': validate,
        'radius': radius,
    }
    state.setdefault('cycles', []).append(record)
    state['total_radius'] = round(float(state.get('total_radius', 0.0)) + radius, 4)
    _save_skill_state(skill_id, state)

    gradient['last_delta'] = radius
    gradient['last_validate'] = validate
    _save_skill_gradient(skill_id, gradient)

    episodic.setdefault('episodes', []).append({'at': now, 'validate': validate, 'radius': radius, 'issues': issues})
    _save_skill_episodic(skill_id, episodic)

    fingerprint = [f'skill:{skill_id}', f'validate:{validate}', f'phase:{phase}']
    if issues:
        fingerprint.extend(f'issue:{item}' for item in issues)

    return SkillResult(
        skill_id=skill_id,
        radius_gained=radius,
        validate=validate,
        fingerprint=fingerprint,
        state_vector={
            'phase': phase,
            'executed_steps': executed,
            'cycles': len(state.get('cycles', [])),
            'total_radius': state.get('total_radius', 0.0),
        },
    )


def _cmd_list() -> int:
    registry = _load_registry()
    for skill_id, entry in sorted(registry.items()):
        steps = ','.join(str(s) for s in entry.get('steps', []))
        print(f'{skill_id}: phase={entry.get("phase", 0)} steps={steps}')
    return 0


def _cmd_run(skill_id: str) -> int:
    result = run_skill(skill_id)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.validate != 'FAIL' else 1


def _cmd_status() -> int:
    registry = _load_registry()
    payload = {skill_id: _load_skill_state(skill_id) for skill_id in registry}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _scratch_dir(label: str) -> Path:
    root = Path.cwd() / '.bago' / 'state' / '_selftests' / label
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_tests() -> int:
    scratch = _scratch_dir('skill_engine')
    try:
        configure_paths(str(scratch))
        save_json(REGISTRY_FILE, {
            'probe': {'phase': 2, 'steps': [0, 3, 4, 5, 8, 9, 10, 11], 'category': 'test'}
        })
        result = run_skill('probe')
        state = _load_skill_state('probe')
        results = [
            ('registry_load', 'probe' in _load_registry(), 'skill registry loads from scan root'),
            ('result_type', isinstance(result.to_dict(), dict), 'run_skill returns serializable result'),
            ('state_saved', len(state.get('cycles', [])) == 1, 'skill state persists'),
            ('radius_positive', result.radius_gained >= 0.0, 'radius computed'),
            ('phase_persisted', result.state_vector.get('phase') == 2, 'phase stored in state vector'),
        ]
        return print_test_results(results)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)
        configure_paths()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='BAGO skill engine')
    parser.add_argument('--root', default='', help='Scan root override')
    parser.add_argument('--test', action='store_true', help='Run self-tests')
    parser.add_argument('command', nargs='?', choices=['list', 'run', 'status'])
    parser.add_argument('skill_id', nargs='?')
    args = parser.parse_args(argv)
    configure_paths(args.root or None)

    if args.test:
        return _run_tests()
    if args.command == 'list':
        return _cmd_list()
    if args.command == 'run':
        if not args.skill_id:
            print('skill_engine run requires a skill id', file=sys.stderr)
            return 1
        return _cmd_run(args.skill_id)
    if args.command == 'status':
        return _cmd_status()
    parser.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
