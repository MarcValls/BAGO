#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys
import textwrap
import urllib.error
import urllib.request
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import get_scan_root, load_json, print_test_results, save_json, timestamp_iso

TOOLS_DIR = Path(__file__).resolve().parent
SCAN_ROOT = Path.cwd()
BAGO_ROOT = SCAN_ROOT / '.bago'
CATALOG_PATH = BAGO_ROOT / 'mcp' / 'toolbox_catalog.json'
TOOLBOXES_DIR = BAGO_ROOT / 'state' / 'toolboxes'
REGISTRY_PATH = TOOLS_DIR / 'tool_registry.py'
NEURAL_URL = 'http://localhost:7331'


def _resolve_bago_root(scan_root: Path) -> Path:
    scan_root = Path(scan_root).resolve()
    if scan_root.name == '.bago':
        return scan_root
    return scan_root / '.bago'


def configure_paths(root_override: str | None = None) -> Path:
    global SCAN_ROOT, BAGO_ROOT, CATALOG_PATH, TOOLBOXES_DIR, REGISTRY_PATH
    SCAN_ROOT = get_scan_root(root_override)
    BAGO_ROOT = _resolve_bago_root(SCAN_ROOT)
    CATALOG_PATH = BAGO_ROOT / 'mcp' / 'toolbox_catalog.json'
    TOOLBOXES_DIR = BAGO_ROOT / 'state' / 'toolboxes'
    REGISTRY_PATH = TOOLS_DIR / 'tool_registry.py'
    TOOLBOXES_DIR.mkdir(parents=True, exist_ok=True)
    return SCAN_ROOT


configure_paths()


@dataclass
class AssignedTool:
    name: str
    purpose: str = ''
    reason: str = ''
    category: str = ''
    confidence: float = 0.0


@dataclass
class Toolbox:
    agent: str
    sprint: str
    task: str
    tools: list[AssignedTool] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=timestamp_iso)

    def to_dict(self) -> dict:
        return {
            'agent': self.agent,
            'sprint': self.sprint,
            'task': self.task,
            'tools': [asdict(item) for item in self.tools],
            'notes': list(self.notes),
            'created_at': self.created_at,
        }


def _catalog_exists() -> bool:
    return CATALOG_PATH.exists()


def _load_catalog() -> dict:
    return load_json(CATALOG_PATH, {}) if CATALOG_PATH.exists() else {}


def _tool_meta(catalog: dict, tool_name: str) -> dict:
    tools = catalog.get('tools', {})
    if isinstance(tools, dict):
        return dict(tools.get(tool_name, {}) or {})
    return {}


def _normalize_group_items(catalog: dict, names: list[str]) -> list[str]:
    groups = catalog.get('groups', {})
    seen: list[str] = []
    for group_name in names:
        entries = groups.get(group_name, []) if isinstance(groups, dict) else []
        for entry in entries:
            if isinstance(entry, str):
                tool_name = entry
            elif isinstance(entry, dict):
                tool_name = entry.get('name') or entry.get('tool') or entry.get('id') or ''
            else:
                tool_name = ''
            if tool_name and tool_name not in seen:
                seen.append(tool_name)
    return seen


def _route_from_catalog(catalog: dict, task: str, agent: str | None = None) -> tuple[str, list[str], list[str]]:
    task_lower = task.lower()
    routing = catalog.get('task_routing', [])
    matched = None
    if isinstance(routing, list):
        for route in routing:
            if not isinstance(route, dict):
                continue
            keywords = [str(item).lower() for item in route.get('keywords', [])]
            if keywords and any(keyword in task_lower for keyword in keywords):
                matched = route
                break
    chosen_agent = agent or (matched or {}).get('agent') or catalog.get('default_agent') or 'copilot'
    composite_name = (matched or {}).get('composite')
    tool_names: list[str] = []
    notes: list[str] = []
    composites = catalog.get('composites', {}) if isinstance(catalog.get('composites', {}), dict) else {}
    if composite_name and composite_name in composites:
        composite = composites.get(composite_name, {}) or {}
        group_names = [str(item) for item in composite.get('groups', [])]
        tool_names.extend(_normalize_group_items(catalog, group_names))
        for explicit in composite.get('tools', []):
            if explicit not in tool_names:
                tool_names.append(explicit)
        notes.append(f'composite:{composite_name}')
    defaults = catalog.get('agent_defaults', {}) if isinstance(catalog.get('agent_defaults', {}), dict) else {}
    if not tool_names and isinstance(defaults.get(chosen_agent), dict):
        entry = defaults[chosen_agent]
        tool_names.extend(_normalize_group_items(catalog, [str(item) for item in entry.get('groups', [])]))
        for explicit in entry.get('tools', []):
            if explicit not in tool_names:
                tool_names.append(explicit)
        if entry.get('notes'):
            notes.extend([str(item) for item in entry.get('notes', [])])
    if not tool_names:
        tool_names.extend(_normalize_group_items(catalog, list((catalog.get('groups') or {}).keys())[:1]))
    return chosen_agent, tool_names, notes


def assign_toolbox(task: str, agent: str | None = None, sprint: str = 'backlog') -> Toolbox:
    catalog = _load_catalog()
    chosen_agent, tool_names, notes = _route_from_catalog(catalog, task, agent)
    tools: list[AssignedTool] = []
    for tool_name in tool_names:
        meta = _tool_meta(catalog, tool_name)
        tools.append(AssignedTool(
            name=tool_name,
            purpose=str(meta.get('purpose', '')),
            reason=f'matched task: {task}',
            category=str(meta.get('category', '')),
            confidence=float(meta.get('confidence', 0.75 if tool_names else 0.0)),
        ))
    toolbox = Toolbox(agent=chosen_agent, sprint=sprint, task=task, tools=tools, notes=notes)
    save_toolbox(toolbox)
    return toolbox


def save_toolbox(toolbox: Toolbox) -> Path:
    TOOLBOXES_DIR.mkdir(parents=True, exist_ok=True)
    safe_agent = re.sub(r'[^A-Za-z0-9._-]+', '-', toolbox.agent).strip('-') or 'agent'
    safe_sprint = re.sub(r'[^A-Za-z0-9._-]+', '-', toolbox.sprint).strip('-') or 'backlog'
    path = TOOLBOXES_DIR / f'{safe_agent}-{safe_sprint}.json'
    save_json(path, toolbox.to_dict())
    return path


def assign_sprint(sprint_id: str, tasks: list[str] | None = None) -> list[Path]:
    catalog = _load_catalog()
    defaults = catalog.get('agent_defaults', {}) if isinstance(catalog.get('agent_defaults', {}), dict) else {}
    agents = list(defaults.keys()) or ['copilot']
    tasks = list(tasks or [])
    paths: list[Path] = []
    for index, agent in enumerate(agents):
        task = tasks[index] if index < len(tasks) else f'sprint {sprint_id} default plan for {agent}'
        toolbox = assign_toolbox(task=task, agent=agent, sprint=sprint_id)
        paths.append(save_toolbox(toolbox))
    return paths


def catalog_summary() -> str:
    catalog = _load_catalog()
    if not catalog:
        return 'no catalog found'
    groups = len(catalog.get('groups', {}) or {})
    tools = len(catalog.get('tools', {}) or {})
    composites = len(catalog.get('composites', {}) or {})
    return f'tool groups={groups} tools={tools} composites={composites}'


def missing_tools() -> list[str]:
    catalog = _load_catalog()
    expected = sorted(set((catalog.get('tools') or {}).keys()))
    if not expected and REGISTRY_PATH.exists():
        text = REGISTRY_PATH.read_text(encoding='utf-8')
        expected = sorted(set(re.findall(r'([A-Za-z0-9_]+)\\.py', text)))
    missing: list[str] = []
    for tool_name in expected:
        if not (TOOLS_DIR / f'{tool_name}.py').exists():
            missing.append(tool_name)
    return missing


TOOL_TEMPLATE = '''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import get_scan_root, print_test_results


def main(argv=None):
    parser = argparse.ArgumentParser(description={description!r})
    parser.add_argument('--root', default='', help='Scan root override')
    parser.add_argument('--test', action='store_true', help='Run self-tests')
    args = parser.parse_args(argv)
    get_scan_root(args.root or None)
    if args.test:
        return print_test_results([('smoke', True, 'template test')])
    print({message!r})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
'''


def create_tool(tool_name: str, description: str = '', category: str = 'general') -> Path:
    path = TOOLS_DIR / f'{tool_name}.py'
    if path.exists():
        raise FileExistsError(f'tool already exists: {path}')
    message = f'{tool_name}: {description or category}'
    path.write_text(TOOL_TEMPLATE.format(description=description or f'BAGO {tool_name} tool', message=message), encoding='utf-8')
    return path


def listen_neural_bus(limit: int = 1) -> int:
    count = 0
    while count < max(1, limit):
        try:
            with urllib.request.urlopen(f'{NEURAL_URL}/toolsmith/events', timeout=1.0) as response:
                payload = response.read().decode('utf-8', errors='replace').strip()
                if payload:
                    # ── Orchestrator gate (opt-in: BAGO_ORCHESTRATE=1) ───────
                    if os.environ.get('BAGO_ORCHESTRATE') == '1':
                        try:
                            import importlib.util as _ilu
                            _orc_path = TOOLS_DIR / 'orchestrator_v4.py'
                            _spec = _ilu.spec_from_file_location('orchestrator_v4', _orc_path)
                            _orc = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
                            _spec.loader.exec_module(_orc)  # type: ignore[union-attr]
                            _orc.configure_paths(str(SCAN_ROOT))
                            _brief = _orc.create_brief(
                                task_description=f"neural_bus event: {payload[:80]}",
                                domain="Backend",
                                priority="P1",
                            )
                            _brief_id = _brief.get('id', '')
                            _orc.assign_brief(_brief_id, agent='Toolsmith Specialist')
                        except Exception:
                            pass  # Orchestrator no disponible — continúa
                    # ─────────────────────────────────────────────────────────
                    print(payload)
                    count += 1
                    continue
        except Exception:
            pass
        print('listen: no bus events')
        count += 1
    return 0


def _print_json(payload: object) -> int:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _parse_tasks(raw: str) -> list[str]:
    return [item.strip() for item in raw.split('|') if item.strip()]


def _run_tests() -> int:
    scratch = Path.cwd() / '.bago' / 'state' / '_selftests' / 'toolsmith'
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        configure_paths(str(scratch))
        results: list[tuple[str, bool, str]] = []
        results.append(('catalog_empty_ok', _load_catalog() == {}, 'missing catalog loads as empty dict'))
        catalog = {
            'groups': {
                'analysis': ['inspector', 'grepper'],
                'build': ['builder'],
            },
            'tools': {
                'inspector': {'purpose': 'inspect code', 'category': 'analysis'},
                'grepper': {'purpose': 'search text', 'category': 'analysis'},
                'builder': {'purpose': 'build project', 'category': 'build'},
            },
            'composites': {
                'analysis-stack': {'groups': ['analysis']}
            },
            'task_routing': [
                {'keywords': ['debug', 'error'], 'agent': 'copilot', 'composite': 'analysis-stack'}
            ],
            'agent_defaults': {
                'copilot': {'groups': ['analysis']},
                'codex': {'groups': ['build']},
            },
        }
        save_json(CATALOG_PATH, catalog)
        toolbox = assign_toolbox('debug failing build', sprint='sprint-1')
        toolbox_path = TOOLBOXES_DIR / 'copilot-sprint-1.json'
        results.append(('assign_creates_file', toolbox_path.exists(), 'assign writes toolbox json file'))
        results.append(('toolbox_structure', isinstance(toolbox.tools, list) and bool(toolbox.tools) and isinstance(toolbox.tools[0], AssignedTool), 'toolbox contains assigned tools'))
        out = io.StringIO()
        with redirect_stdout(out):
            rc_catalog = main(['--root', str(scratch), 'catalog'])
        results.append(('catalog_list_output', rc_catalog == 0 and 'tool groups=' in out.getvalue(), 'catalog command prints summary'))
        err = io.StringIO()
        with redirect_stderr(err):
            rc_missing = main(['--root', str(scratch), 'unknown'])
        results.append(('missing_subcommand', rc_missing == 1, 'unknown subcommand returns 1'))
        sprint_paths = assign_sprint('sprint-2', ['debug auth', 'build release'])
        results.append(('sprint_assignment', len(sprint_paths) == 2 and all(path.exists() for path in sprint_paths), 'sprint assignment creates per-agent toolboxes'))
        return print_test_results(results)
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)
        configure_paths()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Manage BAGO toolboxes for agents')
    parser.add_argument('--root', default='', help='Scan root override')
    parser.add_argument('--test', action='store_true', help='Run self-tests')
    parser.add_argument('--json', action='store_true', help='Output JSON where relevant')
    parser.add_argument('command', nargs='?')
    parser.add_argument('rest', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    configure_paths(args.root or None)

    if args.test:
        return _run_tests()
    if not args.command:
        parser.print_help()
        return 0

    rest = list(args.rest)
    command = args.command

    if command == 'catalog':
        catalog = _load_catalog()
        if args.json:
            return _print_json(catalog)
        print(catalog_summary())
        return 0

    if command == 'assign':
        assign_parser = argparse.ArgumentParser(prog='toolsmith assign')
        assign_parser.add_argument('--task', required=True)
        assign_parser.add_argument('--agent', default='')
        assign_parser.add_argument('--sprint', default='backlog')
        parsed = assign_parser.parse_args(rest)
        toolbox = assign_toolbox(parsed.task, parsed.agent or None, parsed.sprint)
        if args.json:
            return _print_json(toolbox.to_dict())
        print(f'assigned {len(toolbox.tools)} tools to {toolbox.agent} for {toolbox.sprint}')
        return 0

    if command == 'sprint':
        sprint_parser = argparse.ArgumentParser(prog='toolsmith sprint')
        sprint_parser.add_argument('sprint_id')
        sprint_parser.add_argument('--tasks', default='')
        parsed = sprint_parser.parse_args(rest)
        paths = assign_sprint(parsed.sprint_id, _parse_tasks(parsed.tasks))
        if args.json:
            return _print_json([str(path) for path in paths])
        print(f'created {len(paths)} toolbox files for sprint {parsed.sprint_id}')
        return 0

    if command == 'missing':
        missing = missing_tools()
        if args.json:
            return _print_json(missing)
        if not missing:
            print('no tools missing')
        else:
            for item in missing:
                print(item)
        return 0

    if command == 'create':
        create_parser = argparse.ArgumentParser(prog='toolsmith create')
        create_parser.add_argument('tool_name')
        create_parser.add_argument('--desc', default='')
        create_parser.add_argument('--category', default='general')
        parsed = create_parser.parse_args(rest)
        path = create_tool(parsed.tool_name, parsed.desc, parsed.category)
        print(str(path))
        return 0

    if command == 'listen':
        listen_parser = argparse.ArgumentParser(prog='toolsmith listen')
        listen_parser.add_argument('--limit', type=int, default=1)
        parsed = listen_parser.parse_args(rest)
        return listen_neural_bus(parsed.limit)

    if command == 'agent':
        defaults = (_load_catalog().get('agent_defaults') or {})
        if args.json:
            return _print_json(defaults)
        print(json.dumps(defaults, indent=2, ensure_ascii=False))
        return 0

    print(f'unknown subcommand: {command}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
