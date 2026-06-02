# BAGO v4 Testing

Testing is the gate between a plan item and a completed feature. A feature is not done because it exists; it is done when its contract passes.

## Base Gate

Run from the repository root:

```powershell
python --version
python -m py_compile bago_core\cli.py bago_core\launcher.py .bago\api\bridge.py .bago\core\config_manager.py test_security_release.py test_e2e.py
python test_security_release.py
python test_e2e.py
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
python bago_core\cli.py llm list
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

Required result:

- Python reports 3.11 or newer.
- all commands pass.
- `validate` reports contracts present.
- no security regression.
- no open culpas.
- no failed claims.

## Provider Startup Gate

```powershell
python bago_core\cli.py llm list
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
python bago_core\cli.py llm start --provider cpp-local --dry-run
```

Expected:

- `ollama-local` starts in dry-run when available.
- `cpp-local` is blocked unless experimental mode is explicit.

## Optional Live Ollama Gate

This gate is skipped automatically if Ollama is not running or no local model is installed. It is not required for every commit, but it is the cleanest proof of the live local-model path.

```powershell
python test_ollama_live_optional.py
```

Expected:

- detects local Ollama.
- sends one short live prompt.
- saves the session.
- exercises the provider/model switch path.
- reloads the session and verifies the history remains available.

## UI Gate

```powershell
cd ui-react
npm run build
```

Expected:

- build passes.
- no credentials in bundle.
- CLI remains usable if UI is missing.
- UI can show RL bridge status when API is available.

## Optional Dependency Gate

```powershell
node --version
npm --version
python -c "import importlib.util; print('numpy', bool(importlib.util.find_spec('numpy')))"
```

Expected:

- missing Node/npm blocks only UI.
- missing numpy blocks only advanced RL.

## Bridge Gates

```powershell
python bago_core\cli.py engine status
python bago_core\cli.py appdata status
python bago_core\cli.py cmd-rl status
```

Expected:

- missing external folders report unavailable.
- commands do not crash v4.
- live state is reported as excluded, never imported.
- AppData is optional and not required for boot.

## RL Bridge Gates

```powershell
python bago_core\cli.py rl status
python bago_core\cli.py rl shadow on
python bago_core\cli.py rl shadow status
python bago_core\cli.py rl shadow off
python bago_core\cli.py rl train bc
python bago_core\cli.py rl eval
```

Expected:

- missing external folders report unavailable.
- commands do not crash v4.
- RL shadow does not execute actions.
- policy commands report `no_samples`, `no_policy`, `disabled`, or `ok` explicitly.
- policy commands never execute actions.

## API RL Gate

```powershell
python .bago\api\bridge.py --test
```

Expected:

- `/rl/status` returns `can_execute=false`.
- `/rl/shadow` can turn shadow off without granting authority.

## Release Gate

Before packaging:

```powershell
python --version
python test_security_release.py
python test_e2e.py
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
python bago_core\cli.py llm list
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

Manual release checks:

- no `.bago/state`.
- no `.bago/logs`.
- no credentials.
- no `node_modules`.
- no heavy checkpoints.
- no C++ requirement.
- backup/rollback defined.

Package scanner:

```powershell
python scripts\package_v4.py --test
python scripts\package_v4.py
```

## Plan Monitor

The monitor is optional evidence for execution flow:

```powershell
python PLAN_VERTICE\monitor\plan_monitor_server.py --host 127.0.0.1 --port 8766
```

It records plan execution events in:

```text
PLAN_VERTICE\monitor\events.jsonl
```

## Next Steps

1. Add release package scanner.
2. Store release evidence under `docs/evidence/release-v4`.
3. Add policy quality metrics before canary.
