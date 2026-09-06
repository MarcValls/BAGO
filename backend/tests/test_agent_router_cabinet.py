from __future__ import annotations

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
