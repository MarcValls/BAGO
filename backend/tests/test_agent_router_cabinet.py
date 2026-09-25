from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


BAGO = Path(__file__).resolve().parents[1] / '.bago'


@pytest.fixture
def router(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    import agent_router

    monkeypatch.setattr(agent_router, 'BAGO_ROOT', BAGO)
    return agent_router


@pytest.mark.parametrize(('task', 'task_type', 'needs_generator'), [
    ('implement a widget and run tests', 'execution', True),
    ('please write unit tests for the parser', 'execution', True),
    ('fix the failing test', 'execution', True),
    ('por favor corrige el parser y verifica las pruebas', 'execution', True),
    ('verify existing code', 'validation', False),
    ('audit implementation', 'validation', False),
    ('check the build output', 'validation', False),
    ('review the backend contract', 'system_change', False),
    ('fix credential permissions', 'security', False),
    ('implement a legacy migration and run tests', 'history_migration', False),
])
def test_primary_change_request_keeps_implementation_and_verification_roles(
    router, task, task_type, needs_generator,
):
    plan = router.plan_cabinet(task)

    assert plan['task_type'] == task_type
    role_ids = {role['id'] for role in plan['roles']}
    assert ('role_production_generador' in role_ids) is needs_generator
    assert 'role_production_validador' in role_ids
    assert all(len(wave) <= 3 for wave in plan['waves'])
    assert plan['execution'].startswith('plan-only;')


@pytest.mark.parametrize(('task', 'workflow_file'), [
    ('analyze the repository', 'workflow_analisis.md'),
    ('design a widget', 'workflow_diseno.md'),
    ('implement a widget and run tests', 'workflow_ejecucion.md'),
    ('verify the widget', 'workflow_validacion.md'),
    ('review the backend contract', 'workflow_cambio_sistemico.md'),
    ('migrate the archive', 'workflow_migracion_historial.md'),
])
def test_plan_uses_the_canonical_workflow_id(router, task, workflow_file):
    document = (BAGO / 'core' / 'workflows' / workflow_file).read_text(encoding='utf-8')
    canonical_id = re.search(r'## id\s+`([^`]+)`', document)

    assert canonical_id is not None
    assert router.plan_cabinet(task)['workflow'] == canonical_id.group(1)


@pytest.mark.parametrize(('task', 'task_type', 'workflow', 'expected_roles'), [
    ('organize the repository', 'organization', 'workflow_execution', {'role_production_organizador'}),
    ('bootstrap this project', 'project_bootstrap', 'workflow_bootstrap_repo_first', {'role_production_analista'}),
])
def test_canonical_task_types_have_explicit_policies(router, task, task_type, workflow, expected_roles):
    plan = router.plan_cabinet(task)
    role_ids = {role['id'] for role in plan['roles']}

    assert plan['task_type'] == task_type
    assert plan['workflow'] == workflow
    assert expected_roles <= role_ids


def test_system_change_keeps_architect_as_high_risk_escalation_only(router):
    ordinary = {role['id'] for role in router.plan_cabinet('review the backend contract')['roles']}
    risky = {role['id'] for role in router.plan_cabinet('implement a high-risk cross-module system change')['roles']}
    risky_execution = {role['id'] for role in router.plan_cabinet('implement a high-risk production feature')['roles']}

    assert 'role_production_arquitecto' not in ordinary
    assert 'role_production_arquitecto' in risky
    assert 'role_production_arquitecto' in risky_execution
    assert 'role_production_generador' in risky_execution


def test_embedded_test_command_is_removed_without_creating_state(router, tmp_path):
    with pytest.raises(SystemExit) as exc:
        router.main(['--root', str(tmp_path), '--test'])

    assert exc.value.code == 2
    assert not (tmp_path / '.bago' / 'state').exists()


def test_router_json_cli_uses_supplied_root_without_eager_state_creation(router, tmp_path, monkeypatch, capsys):
    expected = {'agent': 'codex', 'model': 'gpt-5', 'reason': 'test', 'task': 'review'}
    monkeypatch.setattr(router, 'route_task', lambda *_args, **_kwargs: expected)

    assert router.main(['--root', str(tmp_path), '--task', 'review', '--json', '--no-classifier']) == 0

    assert json.loads(capsys.readouterr().out) == expected
    assert not (tmp_path / '.bago' / 'state').exists()


@pytest.mark.parametrize('task', [
    'Can you implement a widget and run tests?',
    'Could you fix the failing test?',
    'Por favor, corrige el parser y verifica las pruebas.',
    '¿Puedes implementar un widget y ejecutar pruebas?',
    '¿Podrías corregir el parser y verificar las pruebas?',
])
def test_polite_change_requests_keep_generator_role(router, task):
    role_ids = {role['id'] for role in router.plan_cabinet(task)['roles']}

    assert 'role_production_generador' in role_ids
