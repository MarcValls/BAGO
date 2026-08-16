#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import get_scan_root, load_json, print_test_results, save_json, timestamp_iso
from harmony_gate import HarmonyGate, SpiralState
import skill_engine
from skill_engine import SkillResult, _load_registry as _load_skill_registry, run_skill

TOOLS_DIR = Path(__file__).resolve().parent
SCAN_ROOT = Path.cwd()
BAGO_ROOT = SCAN_ROOT / '.bago'
STATE_DIR = BAGO_ROOT / 'state'
AGENTS_REGISTRY = STATE_DIR / 'agents_registry.json'
AGENTS_STATE_DIR = STATE_DIR / 'agents'
SKILL_REGISTRY = STATE_DIR / 'skill_registry.json'

STEP_NAMES = [
    'OBSERVE', 'DETECT', 'PROPOSE', 'SELECT', 'ACT', 'VALIDATE',
    'RECORD', 'REFLECT', 'EVOLVE', 'REMEMBER', 'DISTILL', 'EMIT',
]


def _resolve_bago_root(scan_root: Path) -> Path:
    scan_root = Path(scan_root).resolve()
    if scan_root.name == '.bago':
        return scan_root
    return scan_root / '.bago'


def configure_paths(root_override: str | None = None) -> Path:
    global SCAN_ROOT, BAGO_ROOT, STATE_DIR, AGENTS_REGISTRY, AGENTS_STATE_DIR, SKILL_REGISTRY
    SCAN_ROOT = get_scan_root(root_override)
    BAGO_ROOT = _resolve_bago_root(SCAN_ROOT)
    STATE_DIR = BAGO_ROOT / 'state'
    AGENTS_REGISTRY = STATE_DIR / 'agents_registry.json'
    AGENTS_STATE_DIR = STATE_DIR / 'agents'
    SKILL_REGISTRY = STATE_DIR / 'skill_registry.json'
    skill_engine.configure_paths(root_override)
    return SCAN_ROOT


configure_paths()


@dataclass
class AgentResult:
    agent_id: str
    phase: int
    cycles_run: int
    radius_gained: float
    validate: str
    fingerprint: list[str] = field(default_factory=list)
    skill_results: list[SkillResult] = field(default_factory=list)
    state_vector: dict = field(default_factory=dict)
    harmony_scores: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=timestamp_iso)

    def to_dict(self) -> dict:
        return {
            'agent_id': self.agent_id,
            'phase': self.phase,
            'cycles_run': self.cycles_run,
            'radius_gained': self.radius_gained,
            'validate': self.validate,
            'fingerprint': list(self.fingerprint),
            'skill_results': [item.to_dict() for item in self.skill_results],
            'state_vector': dict(self.state_vector),
            'harmony_scores': dict(self.harmony_scores),
            'timestamp': self.timestamp,
        }


class BagoAgent:
    def __init__(
        self,
        agent_id: str,
        phase: int = 0,
        skills: list[str] | None = None,
        category: str = 'generic',
        description: str = '',
        harmony_threshold: float = 0.6,
    ):
        self.agent_id = agent_id
        self.phase = int(phase) % 12
        self.skill_ids = list(skills or [])
        self.category = category
        self.description = description
        self._gate = HarmonyGate(threshold=harmony_threshold)
        self._state_dir = AGENTS_STATE_DIR / agent_id
        self._state_file = self._state_dir / 'state.json'
        self._gradient_file = self._state_dir / 'gradient.json'
        self._episodic_file = self._state_dir / 'episodic.json'
        self._state_dir.mkdir(parents=True, exist_ok=True)
        state = load_json(self._state_file, {})
        self._cycles = int(state.get('cycles', 0))
        self._total_radius = float(state.get('total_radius', 0.0))

    def _current_state(self) -> dict:
        return load_json(self._state_file, {'agent_id': self.agent_id, 'phase': self.phase, 'cycles': self._cycles, 'total_radius': self._total_radius})

    def _save_state(self, validate: str, radius_gained: float) -> None:
        self._cycles += 1
        self._total_radius = round(self._total_radius + radius_gained, 4)
        save_json(self._state_file, {
            'agent_id': self.agent_id,
            'phase': self.phase,
            'cycles': self._cycles,
            'total_radius': self._total_radius,
            'last_validate': validate,
            'updated_at': timestamp_iso(),
        })

    def _save_gradient(self, skill_results: list[SkillResult], validate: str) -> None:
        harmony = 1.0 if not skill_results else round(sum(1.0 if item.validate == 'GO' else 0.5 if item.validate == 'WARN' else 0.0 for item in skill_results) / len(skill_results), 4)
        save_json(self._gradient_file, {
            'agent_id': self.agent_id,
            'phase': self.phase,
            'last_validate': validate,
            'last_harmony': harmony,
            'updated_at': timestamp_iso(),
        })

    def _save_episodic(self, result: AgentResult) -> None:
        episodes = load_json(self._episodic_file, {})
        if not isinstance(episodes, list):
            episodes = []
        episodes.append({
            'cycle': result.cycles_run,
            'validate': result.validate,
            'radius_gained': result.radius_gained,
            'fingerprint': list(result.fingerprint),
            'timestamp': result.timestamp,
        })
        save_json(self._episodic_file, episodes[-50:])

    def _step_observe(self, ctx: dict) -> None:
        registry = _load_skill_registry()
        ctx['available_skills'] = {skill_id: registry[skill_id] for skill_id in self.skill_ids if skill_id in registry}
        ctx['agent_state'] = self._current_state()

    def _step_detect(self, ctx: dict) -> None:
        ctx['skills_to_run'] = list(ctx.get('available_skills', {}).keys())
        ctx['issues'] = [] if ctx['skills_to_run'] else ['no-skills']

    def _step_propose(self, ctx: dict) -> None:
        ctx['proposals'] = [{'action': 'run_skill', 'skill_id': skill_id} for skill_id in ctx.get('skills_to_run', [])]

    def _step_select(self, ctx: dict) -> None:
        ctx['selected'] = list(ctx.get('proposals', []))

    def _step_act(self, ctx: dict) -> None:
        results: list[SkillResult] = []
        gate_log: list[str] = []
        harmony_scores: dict[str, float] = {}
        previous_state: SpiralState | None = None
        for proposal in ctx.get('selected', []):
            skill_id = proposal.get('skill_id', '')
            if not skill_id:
                continue
            if previous_state is not None:
                current_state = SpiralState(entity_id=skill_id, phase=self.phase, validate='WARN', fingerprint=[f'skill:{skill_id}'])
                gate_result = self._gate.check_before(previous_state, current_state)
                gate_log.append(f'{previous_state.entity_id}->{skill_id}:{gate_result.score:.3f}:{"open" if gate_result.open else "closed"}')
            result = run_skill(skill_id)
            results.append(result)
            current_skill_state = SpiralState.from_skill_result(result)
            if previous_state is not None:
                harmony_scores[f'{previous_state.entity_id}<->{skill_id}'] = self._gate.score(previous_state, current_skill_state)
            previous_state = current_skill_state
        ctx['skill_results'] = results
        ctx['gate_log'] = gate_log
        ctx['harmony_scores'] = harmony_scores

    def _step_validate(self, ctx: dict) -> None:
        results = ctx.get('skill_results', [])
        if not results:
            ctx['validate'] = 'WARN'
            return
        if all(item.validate == 'GO' for item in results):
            ctx['validate'] = 'GO'
        elif all(item.validate == 'FAIL' for item in results):
            ctx['validate'] = 'FAIL'
        else:
            ctx['validate'] = 'WARN'

    def _step_record(self, ctx: dict) -> None:
        radius_gained = round(sum(float(item.radius_gained) for item in ctx.get('skill_results', [])), 4)
        ctx['radius_gained'] = radius_gained
        self._save_state(ctx.get('validate', 'WARN'), radius_gained)

    def _step_reflect(self, ctx: dict) -> None:
        fingerprint = [f'agent:{self.agent_id}', f'phase:{self.phase}', f'validate:{ctx.get("validate", "WARN")}']
        for item in ctx.get('skill_results', []):
            fingerprint.extend(item.fingerprint)
        ctx['fingerprint'] = fingerprint
        self._save_gradient(ctx.get('skill_results', []), ctx.get('validate', 'WARN'))

    def _step_evolve(self, ctx: dict) -> None:
        ctx['next_phase'] = (self.phase + 1) % 12

    def _step_remember(self, ctx: dict) -> None:
        ctx['memory_entry'] = {'timestamp': timestamp_iso(), 'validate': ctx.get('validate', 'WARN'), 'radius_gained': ctx.get('radius_gained', 0.0)}

    def _step_distill(self, ctx: dict) -> None:
        ctx['summary'] = {
            'skills_run': [item.skill_id for item in ctx.get('skill_results', [])],
            'gate_log': ctx.get('gate_log', []),
            'last_step': 'DISTILL',
        }

    def _step_emit(self, ctx: dict) -> None:
        ctx['emitted'] = True
        # ── Orchestrator Handoff (opt-in: BAGO_ORCHESTRATE=1) ──────────────────
        import os as _os
        if _os.environ.get('BAGO_ORCHESTRATE') == '1':
            try:
                import importlib.util as _ilu
                _orc_path = Path(__file__).parent / 'orchestrator_v4.py'
                _spec = _ilu.spec_from_file_location('orchestrator_v4', _orc_path)
                _orc = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
                _spec.loader.exec_module(_orc)  # type: ignore[union-attr]
                _orc.configure_paths(str(SCAN_ROOT))
                summary = (
                    f"SpiralAgent {self.agent_id} completó ciclo. "
                    f"validate={ctx.get('validate','?')} "
                    f"radius={ctx.get('radius_gained',0)} "
                    f"skills={[r.skill_id for r in ctx.get('skill_results',[])]}"
                )
                brief_id = ctx.get('brief_id', '')
                if not brief_id:
                    # Crear brief para este ciclo si no viene de router
                    _brief = _orc.create_brief(
                        task_description=f"SpiralAgent {self.agent_id} cycle",
                        domain="Backend",
                        priority="P2",
                    )
                    brief_id = _brief.get('id', '')
                _orc.create_handoff(
                    brief_id=brief_id,
                    from_domain="Backend",
                    to_domain="Backend",
                    summary=summary,
                )
                ctx['handoff_brief_id'] = brief_id
            except Exception:
                pass  # Orchestrator no disponible — continúa sin él
        # ─────────────────────────────────────────────────────────────────────

    def run(self, parent_ctx: dict | None = None) -> AgentResult:
        ctx: dict[str, Any] = {
            'agent_id': self.agent_id,
            'phase': self.phase,
            'parent_sv': (parent_ctx or {}).get('state_vector', {}),
            'parent_tags': (parent_ctx or {}).get('fingerprint', []),
            'last_step': '',
        }
        steps = [
            ('OBSERVE', self._step_observe),
            ('DETECT', self._step_detect),
            ('PROPOSE', self._step_propose),
            ('SELECT', self._step_select),
            ('ACT', self._step_act),
            ('VALIDATE', self._step_validate),
            ('RECORD', self._step_record),
            ('REFLECT', self._step_reflect),
            ('EVOLVE', self._step_evolve),
            ('REMEMBER', self._step_remember),
            ('DISTILL', self._step_distill),
            ('EMIT', self._step_emit),
        ]
        rotated = steps[self.phase:] + steps[:self.phase]
        for name, fn in rotated:
            ctx['last_step'] = name
            fn(ctx)

        result = AgentResult(
            agent_id=self.agent_id,
            phase=self.phase,
            cycles_run=self._cycles,
            radius_gained=ctx.get('radius_gained', 0.0),
            validate=ctx.get('validate', 'WARN'),
            fingerprint=list(ctx.get('fingerprint', [])),
            skill_results=list(ctx.get('skill_results', [])),
            state_vector={
                'phase': self.phase,
                'cycles': self._cycles,
                'total_radius': self._total_radius,
                'skills_active': len(self.skill_ids),
                'last_step': ctx.get('last_step', ''),
                'next_phase': ctx.get('next_phase', self.phase),
            },
            harmony_scores=dict(ctx.get('harmony_scores', {})),
        )
        self._save_episodic(result)
        return result

    @property
    def spiral_state(self) -> SpiralState:
        state = self._current_state()
        episodes = load_json(self._episodic_file, {})
        if not isinstance(episodes, list):
            episodes = []
        fingerprint = episodes[-1].get('fingerprint', []) if episodes else []
        return SpiralState(
            entity_id=self.agent_id,
            phase=self.phase,
            validate=state.get('last_validate', 'WARN'),
            fingerprint=fingerprint,
            radius_gained=state.get('total_radius', 0.0),
        )


def load_agents_registry() -> dict:
    return load_json(AGENTS_REGISTRY, {})


def _save_agents_registry(data: dict) -> None:
    registry = load_agents_registry()
    registry.update(data)
    save_json(AGENTS_REGISTRY, registry)


def agent_from_registry(agent_id: str) -> BagoAgent | None:
    registry = load_agents_registry()
    entry = registry.get(agent_id)
    if not isinstance(entry, dict) or not entry.get('active', True):
        return None
    return BagoAgent(
        agent_id=agent_id,
        phase=entry.get('phase', 0),
        skills=entry.get('skills', []),
        category=entry.get('category', 'generic'),
        description=entry.get('description', ''),
    )


def list_agents() -> list[dict]:
    registry = load_agents_registry()
    items: list[dict] = []
    for agent_id, entry in sorted(registry.items()):
        state = load_json(AGENTS_STATE_DIR / agent_id / 'state.json', {})
        items.append({
            'id': agent_id,
            'phase': entry.get('phase', 0),
            'skills': entry.get('skills', []),
            'category': entry.get('category', 'generic'),
            'description': entry.get('description', ''),
            'active': entry.get('active', True),
            'cycles': state.get('cycles', 0),
            'total_radius': state.get('total_radius', 0.0),
            'last_validate': state.get('last_validate', '-'),
        })
    return items


def _cmd_spawn(args: list[str]) -> int:
    if not args:
        print('agent spawn requires an id', file=sys.stderr)
        return 1
    agent_id = args[0]
    phase = 0
    skills: list[str] = []
    i = 1
    while i < len(args):
        if args[i] == '--phase' and i + 1 < len(args):
            phase = int(args[i + 1]); i += 2
        elif args[i] == '--skills' and i + 1 < len(args):
            skills = [item.strip() for item in args[i + 1].split(',') if item.strip()]; i += 2
        else:
            i += 1
    _save_agents_registry({agent_id: {'phase': phase % 12, 'skills': skills, 'category': 'custom', 'description': 'spawned via CLI', 'active': True}})
    print(f'spawned {agent_id} phase={phase % 12} skills={",".join(skills) if skills else "none"}')
    return 0


def _cmd_list(_args: list[str]) -> int:
    agents = list_agents()
    if not agents:
        print('no agents registered')
        return 0
    for agent in agents:
        skills = ','.join(agent['skills']) if agent['skills'] else 'none'
        print(f"{agent['id']} phase={agent['phase']} active={agent['active']} validate={agent['last_validate']} cycles={agent['cycles']} skills={skills}")
    return 0


def _cmd_run(args: list[str]) -> int:
    if not args:
        print('agent run requires an id', file=sys.stderr)
        return 1
    agent = agent_from_registry(args[0])
    if agent is None:
        print(f'agent not found: {args[0]}', file=sys.stderr)
        return 1
    result = agent.run()
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.validate != 'FAIL' else 1


def _cmd_kill(args: list[str]) -> int:
    if not args:
        print('agent kill requires an id', file=sys.stderr)
        return 1
    registry = load_agents_registry()
    if args[0] not in registry:
        print(f'agent not found: {args[0]}', file=sys.stderr)
        return 1
    entry = dict(registry[args[0]])
    entry['active'] = False
    _save_agents_registry({args[0]: entry})
    print(f'killed {args[0]}')
    return 0


def _cmd_status(_args: list[str]) -> int:
    agents = [agent_from_registry(item['id']) for item in list_agents() if item.get('active')]
    agents = [agent for agent in agents if agent is not None]
    if not agents:
        print('no active agents')
        return 0
    gate = HarmonyGate(threshold=0.6)
    states = [agent.spiral_state for agent in agents]
    for state in states:
        print(f'{state.entity_id} phase={state.phase} validate={state.validate} radius={state.radius_gained}')
    for index, left in enumerate(states):
        for right in states[index + 1:]:
            score = gate.score(left, right)
            status = 'open' if score >= 0.6 else 'closed'
            print(f'{left.entity_id}<->{right.entity_id} score={score:.3f} {status}')
    return 0


_SUBCOMMANDS = {
    'spawn': _cmd_spawn,
    'list': _cmd_list,
    'run': _cmd_run,
    'kill': _cmd_kill,
    'status': _cmd_status,
}


def _scratch_dir(label: str) -> Path:
    root = Path.cwd() / '.bago' / 'state' / '_selftests' / label
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_tests() -> int:
    scratch = _scratch_dir('spiral_agent')
    try:
        configure_paths(str(scratch))
        save_json(SKILL_REGISTRY, {
            'probe': {'phase': 1, 'steps': [0, 3, 4, 5, 8, 9, 10, 11], 'category': 'test'}
        })
        spawn_rc = _cmd_spawn(['alpha', '--phase', '3', '--skills', 'probe'])
        agent = agent_from_registry('alpha')
        result = agent.run() if agent else None
        registry = load_agents_registry()
        state = load_json(AGENTS_STATE_DIR / 'alpha' / 'state.json', {})
        listing = list_agents()
        capture = io.StringIO()
        with redirect_stdout(capture):
            list_rc = _cmd_list([])
        results = [
            ('agent_spawn', spawn_rc == 0 and 'alpha' in registry, 'spawn registers agent'),
            ('agent_state_persists', state.get('cycles', 0) >= 1, 'run persists state to disk'),
            ('skill_registration', 'probe' in _load_skill_registry(), 'skill registry available to agents'),
            ('spiral_step', isinstance(result, AgentResult) and result.state_vector.get('last_step') in STEP_NAMES, 'agent completes spiral cycle'),
            ('agent_list', any(item['id'] == 'alpha' for item in listing) and list_rc == 0, 'list returns registered agent'),
            ('agent_output', 'alpha' in capture.getvalue(), 'list command prints agent id'),
        ]
        return print_test_results(results)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)
        configure_paths()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='BAGO spiral agents')
    parser.add_argument('--root', default='', help='Scan root override')
    parser.add_argument('--test', action='store_true', help='Run self-tests')
    parser.add_argument('command', nargs='?', choices=sorted(_SUBCOMMANDS))
    parser.add_argument('rest', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    configure_paths(args.root or None)

    if args.test:
        return _run_tests()
    if not args.command:
        parser.print_help()
        return 0
    return _SUBCOMMANDS[args.command](args.rest)


if __name__ == '__main__':
    raise SystemExit(main())
