# BAGO Release Checklist

Use this before publishing a tag, GitHub release, or release ZIP.

Public release policy:

- [`docs/PUBLIC_RELEASE_POLICY.md`](PUBLIC_RELEASE_POLICY.md) - public publication order, gates, limits, and release note template.
- [`docs/RELEASE_NOTES_4.5.0.md`](RELEASE_NOTES_4.5.0.md) - canonical 4.5.0 release notes.

## Scope

- [ ] Stable MVP boundary still matches `docs/MVP.md`.
- [ ] No experimental module is promoted as stable in `README.md`.
- [ ] Version is unified across `release_version.txt`, `versions.json`, launchers, README, manual, landing page, release notes, and installer.
- [ ] Python minimum is unified as Python 3.11+.
- [ ] Documentation language strategy is respected: README in English, manual in Spanish.

## Gates

```powershell
python --version
python -m compileall -q bago_core .bago scripts tests
python -m py_compile bago_core\cli.py bago_core\launcher.py .bago\api\bridge.py .bago\core\config_manager.py tests\test_security_release.py tests\test_e2e.py
python tests\test_security_release.py
python tests\test_e2e.py
python -m pytest -q
python scripts\clean_install_smoke.py
python scripts\verify_release_drift.py
python scripts\verify_docs.py --repo .
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
python .bago\api\bridge.py --test
python .bago\tools\dep_audit.py requirements.txt --format json --out dep-audit.json
python bago_core\cli.py llm list
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
python scripts\package_v4.py --test
```

Optional live model proof:

```powershell
python tests\test_ollama_live_optional.py
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

## Install Manager Hardening

- [ ] Source tree, installed runtime, active role, remote installer, and published release have no drift.
- [ ] Install/update/rollback/uninstall lifecycle actions take one lock before mutating files.
- [ ] Process health is checked before replacing or deleting a runtime.
- [ ] Rollback restore path has current evidence.
- [ ] Uninstall impact analysis protects shared PieceStore data, overlays, connectors, and user state unless purge is explicit.
- [ ] Runtime health is validated after install/update and before promotion.

## Evidence

- [ ] Release evidence bundle exists or the release notes state which gates passed.
- [ ] Claims in `README.md` are represented in `docs/CLAIMS.md`.
- [ ] Known limitations are listed before publishing.
