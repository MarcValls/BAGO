"""Controlled function-boundary reproductions; no provider, process or runtime imports."""
from __future__ import annotations
import ast
import contextlib
import hashlib
import io
import json
import subprocess
import types
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def source(path, ref=None):
    return subprocess.check_output(['git', 'show', f'{ref}:{path}'], cwd=ROOT).decode('utf-8') if ref else (ROOT/path).read_text(encoding='utf-8-sig')

def function(text, name, namespace):
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0),node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<frozen-source-function>', 'exec'), namespace)
    return namespace[name]

plan_source = source('backend/.bago/core/plan_engine.py')
plan_ast = ast.parse(plan_source)
# Only standard-library imports, literal status constants and the three classes.
nodes = [n for n in plan_ast.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.ClassDef)) or isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id.startswith('VALID_') for t in n.targets)]
mod = types.ModuleType('bago_audit_plan_engine')
sys.modules[mod.__name__] = mod
exec(compile(ast.Module(body=nodes, type_ignores=[]), '<frozen-plan-engine>', 'exec'), mod.__dict__)

current_text = source('backend/.bago/chat/commands.py')
historical_text = source('.bago/chat/commands.py', 'v4.5.0')
current = function(current_text, 'cmd_autopilot', {})
historical = function(historical_text, 'cmd_autopilot', {})

def autopilot(fn, count, reply):
    engine = mod.PlanEngine()
    calls=[]
    def send(prompt):
        calls.append(prompt)
        return '\n'.join(f'{i+1}. Analizar contenido de prueba' for i in range(count)) if len(calls)==1 else reply
    mgr = types.SimpleNamespace(plan_engine=engine, send=send)
    with contextlib.redirect_stdout(io.StringIO()):
        result = fn(mgr, None, ['auditar'])
    plan = result.get('plan') or engine.current_plan
    return {'ok':result['ok'], 'plan_status':plan.status, 'provider_stub_calls':len(calls), 'steps':len(plan.steps), 'done_steps':sum(s.status=='done' for s in plan.steps), 'evidence':[list(s.evidence) for s in plan.steps], 'receipt_ids':[s.receipt_id for s in plan.steps]}

launch_text=source('backend/bago_core/launcher.py')
table = next(ast.literal_eval(n.value) for n in ast.parse(launch_text).body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='_DISPATCH_TABLE')
dispatch = function(launch_text,'_dispatch',{'_DISPATCH_TABLE':table})
help_calls=[]
exit_code=dispatch(types.SimpleNamespace(command='issues-gh'),types.SimpleNamespace(print_help=lambda:help_calls.append(True)))
results={
    'schema':'bago.capability-semantic-probes.v1',
    'scope':'Functions compiled from source AST; real PlanEngine class, stub provider returns text. No real provider, shell, filesystem effect or UI exercised.',
    'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['backend/.bago/chat/commands.py','backend/.bago/core/plan_engine.py','backend/bago_core/launcher.py']},
    'current_text_only':autopilot(current,1,'Una respuesta textual, sin ejecutar ninguna herramienta.'),
    'current_blank_reply':autopilot(current,1,''),
    'current_25_steps':autopilot(current,25,'Texto sin recibo material.'),
    'historical_v450_25_steps':autopilot(historical,25,'Texto sin recibo material.'),
    'issues_gh':{'declared_in_parser':'add_parser("issues-gh"' in source('backend/bago_core/parsers_sections.py') or "add_parser('issues-gh'" in source('backend/bago_core/parsers_sections.py'), 'has_dispatch':'issues-gh' in table,'exit_code':exit_code,'help_calls':len(help_calls)},
    'empty_plan_limit':'No empty-plan success claim: current create_plan always creates a fallback step. Removed empty guard alone does not prove reachable empty plan.',
}
assert results['current_text_only']['plan_status']=='done' and results['current_text_only']['receipt_ids']==['']
assert results['current_blank_reply']['ok'] and results['current_blank_reply']['plan_status']=='blocked'
assert results['current_25_steps']['provider_stub_calls']==26
assert results['historical_v450_25_steps']['provider_stub_calls']==21
assert results['issues_gh']['declared_in_parser'] and exit_code==0 and len(help_calls)==1
results['reproduction_result']='OBSERVED_INCONSISTENCIES_REPRODUCED_NOT_ACCEPTANCE_PASS'
(OUT/'semantic-probes.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in results.items() if k not in ('source_sha256','current_25_steps','historical_v450_25_steps')},ensure_ascii=True,indent=2))
