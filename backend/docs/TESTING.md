# BAGO Testing

Testing defines the executable gates for claims and surfaces.

## Required Gates

```powershell
python --version
python -m py_compile bago_core\cli.py bago_core\launcher.py .bago\api\bridge.py .bago\core\config_manager.py test_security_release.py test_e2e.py
python test_e2e.py
python -m pytest tests\test_canonical_contract_state.py -q
python bago_core\cli.py validate
python test_security_release.py
python bago_core\cli.py evidence --test
python bago_core\cli.py llm list
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

## Optional Gates

- `python test_ollama_live_optional.py`
- `cd ui-react; npm run build`
- `python bago_core\cli.py engine status`
- `python bago_core\cli.py appdata status`
- `python bago_core\cli.py cmd-rl status`
- `python bago_core\cli.py rl status`
- `python bago_core\cli.py rl shadow on`
- `python bago_core\cli.py rl shadow status`
- `python bago_core\cli.py rl shadow off`
- `python bago_core\cli.py rl train bc`
- `python bago_core\cli.py rl eval`
- `python .bago\api\bridge.py --test`
- `python scripts\package_v4.py --test`
- `python scripts\package_v4.py`
- `python -m pytest tests\test_workspace_seed_contract.py -q`

## Rules

- no gate may pass with missing credentials, state leaks, or hidden authority
- UI is optional, backend is not
- RL remains shadow/off unless a dedicated gate proves otherwise
- release validation must match the published package manifest
