# BAGO Release Checklist

Use this before publishing a tag, GitHub release, or release ZIP.

## Scope

- [ ] Stable MVP boundary still matches `docs/MVP.md`.
- [ ] No experimental module is promoted as stable in `README.md`.
- [ ] Version is unified across `release_version.txt`, `versions.json`, launchers, README, manual, landing page, release notes, and installer.
- [ ] Python minimum is unified as Python 3.11+.
- [ ] Documentation language strategy is respected: README in English, manual in Spanish.

## Gates

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

Optional live model proof:

```powershell
python test_ollama_live_optional.py
```

UI gate, only if shipping UI assets:

```powershell
cd ui-react
npm run build
```

## Security

- [ ] `auto_allow_tools=false` by default.
- [ ] API defaults to `127.0.0.1`.
- [ ] `0.0.0.0` or non-localhost bind requires token.
- [ ] CORS has no wildcard origin.
- [ ] Tokens are not in UI bundle.
- [ ] Credentials are not in docs, samples, release ZIP, or evidence bundles.
- [ ] RL/agents/autopilot have no execution authority unless explicitly authorized.

## Packaging

- [ ] No `.bago/state`.
- [ ] No `.bago/logs`.
- [ ] No credentials.
- [ ] No `node_modules`.
- [ ] No Python caches.
- [ ] No temporary release folders.
- [ ] No large checkpoints unless intentionally published.
- [ ] Package can be generated cleanly.

## Evidence

- [ ] Release evidence bundle exists or the release notes state which gates passed.
- [ ] Claims in `README.md` are represented in `docs/CLAIMS.md`.
- [ ] Known limitations are listed before publishing.
