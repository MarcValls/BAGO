#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import get_scan_root, load_json, print_test_results, save_json, timestamp_iso


def _default_ollama_url() -> str:
    return os.environ.get('OLLAMA_HOST', 'http://localhost:11434')


def _resolve_ollama_models_dir() -> Path:
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        return base / 'Ollama' / 'models'
    if sys.platform == 'darwin':
        return Path.home() / '.ollama' / 'models'
    return Path(os.environ.get('OLLAMA_MODELS', Path.home() / '.ollama' / 'models'))


OLLAMA_MODELS_DIR = _resolve_ollama_models_dir()
SCAN_ROOT = Path.cwd()
BAGO_ROOT = SCAN_ROOT / '.bago'
STATE_DIR = BAGO_ROOT / 'state'
ROUTER_HISTORY = STATE_DIR / 'route_history.json'
ROUTER_POLICY = STATE_DIR / 'llm_config.json'


def _resolve_bago_root(scan_root: Path) -> Path:
    scan_root = Path(scan_root).resolve()
    if scan_root.name == '.bago':
        return scan_root
    return scan_root / '.bago'


def configure_paths(root_override: str | None = None) -> Path:
    global SCAN_ROOT, BAGO_ROOT, STATE_DIR, ROUTER_HISTORY, ROUTER_POLICY
    SCAN_ROOT = get_scan_root(root_override)
    BAGO_ROOT = _resolve_bago_root(SCAN_ROOT)
    STATE_DIR = BAGO_ROOT / 'state'
    ROUTER_HISTORY = STATE_DIR / 'route_history.json'
    ROUTER_POLICY = STATE_DIR / 'llm_config.json'
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return SCAN_ROOT


configure_paths()


def load_policy() -> dict:
    default = {
        'default_agent': 'copilot',
        'prefer_local': True,
        'model_preferences': {
            'ollama': 'qwen2.5-coder:7b',
            'codex': 'gpt-5',
            'copilot': 'gpt-5',
        },
    }
    if not ROUTER_POLICY.exists():
        return default
    data = load_json(ROUTER_POLICY, default)
    if not isinstance(data, dict):
        return default
    merged = default.copy()
    merged.update(data)
    merged['model_preferences'] = {**default['model_preferences'], **dict(data.get('model_preferences', {}))}
    return merged


def _ollama_server_up(url: str | None = None) -> bool:
    target = f'{(url or _default_ollama_url()).rstrip("/")}/api/tags'
    try:
        with urllib.request.urlopen(target, timeout=1.5) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def detect_agents() -> list[dict]:
    agents = [
        {'id': 'copilot', 'agent': 'copilot', 'available': True, 'reason': 'cloud'},
        {'id': 'codex', 'agent': 'codex', 'available': True, 'reason': 'cloud'},
        {
            'id': 'ollama',
            'agent': 'ollama',
            'available': bool(OLLAMA_MODELS_DIR.exists() or _ollama_server_up()),
            'reason': 'local-runtime',
            'url': _default_ollama_url(),
            'models_dir': str(OLLAMA_MODELS_DIR),
        },
    ]
    return agents


def _available_agents(agents: list[dict] | None = None) -> dict[str, dict]:
    source = agents if agents is not None else detect_agents()
    return {item['id']: item for item in source if item.get('available', True)}


def _classify_with_ollama(task: str) -> dict | None:
    if not _ollama_server_up():
        return None
    prompt = {
        'model': 'qwen2.5-coder:7b',
        'stream': False,
        'prompt': 'Classify this engineering task into one of: ollama, codex, copilot. Return JSON with keys agent and reason. Task: ' + task,
    }
    request = urllib.request.Request(
        f'{_default_ollama_url().rstrip("/")}/api/generate',
        data=json.dumps(prompt).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=3.0) as response:
            payload = json.loads(response.read().decode('utf-8', errors='replace'))
            raw_text = payload.get('response', '{}')
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict) and parsed.get('agent'):
                return parsed
    except Exception:
        return None
    return None


def _signals(task: str) -> dict[str, int | bool]:
    lowered = task.lower()
    code_terms = ('code', 'fix', 'bug', 'test', 'refactor', 'implement', 'build', 'debug', 'python', 'js', 'ts', 'file', 'repo')
    local_terms = ('brainstorm', 'idea', 'summary', 'explain', 'offline', 'quick', 'draft', 'chat')
    gh_terms = ('pr', 'pull request', 'review', 'issue', 'workflow', 'actions', 'github')
    return {
        'code_hits': sum(1 for term in code_terms if term in lowered),
        'local_hits': sum(1 for term in local_terms if term in lowered),
        'gh_hits': sum(1 for term in gh_terms if term in lowered),
        'large_change': any(term in lowered for term in ('multi-file', 'several files', 'many files', 'across modules', 'end-to-end')),
    }


def _hard_route(task: str, available: dict[str, dict]) -> str | None:
    lowered = task.lower()
    if any(term in lowered for term in ('pr review', 'pull request review', 'review pr', 'github review')) and 'copilot' in available:
        return 'copilot'
    if any(term in lowered for term in ('issue triage', 'workflow run', 'github actions', 'repository settings')) and 'copilot' in available:
        return 'copilot'
    if any(term in lowered for term in ('multi-file', 'many files', 'end-to-end', 'execute tests', 'run tests', 'implement')) and 'codex' in available:
        return 'codex'
    return None


def _fallback_route(task: str, available: dict[str, dict], policy: dict) -> str:
    signals = _signals(task)
    scores = {agent_id: 0 for agent_id in available}
    if 'ollama' in available:
        scores['ollama'] += int(signals['local_hits']) * 10
        scores['ollama'] += 5 if policy.get('prefer_local', True) else 0
    if 'codex' in available:
        scores['codex'] += int(signals['code_hits']) * 8
        scores['codex'] += 8 if signals['large_change'] else 0
    if 'copilot' in available:
        scores['copilot'] += int(signals['code_hits']) * 6
        scores['copilot'] += int(signals['gh_hits']) * 12
    best_score = max(scores.values()) if scores else 0
    best = [agent_id for agent_id, score in scores.items() if score == best_score]
    priority = ['copilot', 'codex', 'ollama']
    for agent_id in priority:
        if agent_id in best:
            return agent_id
    return next(iter(available.keys()), policy.get('default_agent', 'copilot'))


def _record_route(route: dict) -> None:
    history = load_json(ROUTER_HISTORY, {})
    if not isinstance(history, list):
        history = []
    history.append(route)
    save_json(ROUTER_HISTORY, history[-200:])


def route_task(task: str, agents: list[dict] | None = None, use_classifier: bool = True, record: bool = False) -> dict:
    policy = load_policy()
    available = _available_agents(agents)

    # ── Orchestrator gate (opt-in: BAGO_ORCHESTRATE=1) ────────────────────────
    brief_id: str = ''
    if os.environ.get('BAGO_ORCHESTRATE') == '1':
        try:
            import importlib.util as _ilu
            _orc_path = Path(__file__).parent / 'orchestrator_v4.py'
            _spec = _ilu.spec_from_file_location('orchestrator_v4', _orc_path)
            _orc = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
            _spec.loader.exec_module(_orc)  # type: ignore[union-attr]
            _orc.configure_paths(str(SCAN_ROOT))
            _brief = _orc.create_brief(task_description=task)
            brief_id = _brief.get('id', '')
        except Exception:
            pass  # Orchestrator no disponible — continúa sin él
    # ─────────────────────────────────────────────────────────────────────────

    if not available:
        agent_id = policy.get('default_agent', 'copilot')
        result = {'agent': agent_id, 'model': policy.get('model_preferences', {}).get(agent_id, ''), 'reason': 'default-no-agents', 'task': task, 'timestamp': timestamp_iso()}
        if brief_id:
            result['brief_id'] = brief_id
        if record:
            _record_route(result)
        return result

    agent_id = _hard_route(task, available)
    reason = 'hard-route' if agent_id else ''

    if not agent_id and use_classifier:
        classified = _classify_with_ollama(task)
        if classified and classified.get('agent') in available:
            agent_id = classified['agent']
            reason = f'classifier:{classified.get("reason", "ollama")}'

    if not agent_id:
        agent_id = _fallback_route(task, available, policy)
        reason = reason or 'fallback'

    result = {
        'agent': agent_id,
        'model': policy.get('model_preferences', {}).get(agent_id, ''),
        'reason': reason,
        'task': task,
        'timestamp': timestamp_iso(),
    }
    if brief_id:
        result['brief_id'] = brief_id
        # Registrar asignación en el brief
        try:
            _orc.assign_brief(brief_id, agent=agent_id)  # type: ignore[name-defined]
        except Exception:
            pass
    if record:
        _record_route(result)
    return result


def _scratch_dir(label: str) -> Path:
    root = Path.cwd() / '.bago' / 'state' / '_selftests' / label
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_tests() -> int:
    scratch = _scratch_dir('agent_router')
    old_host = os.environ.get('OLLAMA_HOST')
    try:
        configure_paths(str(scratch))
        save_json(ROUTER_POLICY, {'default_agent': 'copilot', 'prefer_local': True})
        os.environ['OLLAMA_HOST'] = 'http://localhost:42424'
        agents = [
            {'id': 'ollama', 'available': True},
            {'id': 'codex', 'available': True},
            {'id': 'copilot', 'available': True},
        ]
        route = route_task('implement multi-file auth and run tests', agents=agents, use_classifier=False)
        detected = detect_agents()
        original_up = _ollama_server_up
        try:
            globals()['_ollama_server_up'] = lambda url=None: False
            fallback = route_task('brainstorm offline notes', agents=agents, use_classifier=True)
        finally:
            globals()['_ollama_server_up'] = original_up
        out = io.StringIO()
        with redirect_stdout(out):
            json_rc = main(['--root', str(scratch), '--task', 'brainstorm offline notes', '--json', '--no-classifier'])
        json_payload = json.loads(out.getvalue())
        results = [
            ('default_ollama_url', isinstance(_default_ollama_url(), str) and _default_ollama_url().startswith('http'), 'default ollama url is a string'),
            ('resolve_models_dir', isinstance(_resolve_ollama_models_dir(), Path), 'ollama models dir resolves to Path'),
            ('route_has_agent', isinstance(route, dict) and route.get('agent') == 'codex', 'route_task returns dict with agent key'),
            ('available_agents_list', isinstance(detected, list) and all('id' in item for item in detected), 'detect_agents returns agent list'),
            ('deterministic_fallback', fallback.get('agent') == 'ollama', 'fallback is deterministic when classifier is unavailable'),
            ('json_output_mode', json_rc == 0 and isinstance(json_payload, dict) and 'agent' in json_payload, 'json output mode prints route json'),
        ]
        return print_test_results(results)
    finally:
        if old_host is None:
            os.environ.pop('OLLAMA_HOST', None)
        else:
            os.environ['OLLAMA_HOST'] = old_host
        if scratch.exists():
            shutil.rmtree(scratch)
        configure_paths()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Route tasks to the best available AI agent')
    parser.add_argument('--root', default='', help='Scan root override')
    parser.add_argument('--test', action='store_true', help='Run self-tests')
    parser.add_argument('--task', default='', help='Task text to route')
    parser.add_argument('--json', action='store_true', help='Print route JSON')
    parser.add_argument('--history', action='store_true', help='Show routing history and exit')
    parser.add_argument('--limit', type=int, default=10, help='History entry limit')
    parser.add_argument('--no-classifier', action='store_true', help='Disable ollama classifier')
    parser.add_argument('task_words', nargs='*')
    args = parser.parse_args(argv)
    configure_paths(args.root or None)

    if args.test:
        return _run_tests()
    if args.history:
        history = load_json(ROUTER_HISTORY, {})
        if not isinstance(history, list):
            history = []
        payload = history[-args.limit:]
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            for item in payload:
                print(f"{item.get('timestamp', '-')} {item.get('agent', '-')} {item.get('reason', '-')} {item.get('task', '')}")
        return 0

    task_text = args.task.strip() or ' '.join(args.task_words).strip()
    if not task_text:
        parser.print_help()
        return 0
    route = route_task(task_text, use_classifier=not args.no_classifier, record=True)
    if args.json:
        print(json.dumps(route, indent=2, ensure_ascii=False))
    else:
        print(f"agent={route['agent']} model={route['model']} reason={route['reason']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
