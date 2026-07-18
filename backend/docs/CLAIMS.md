# Claim Evidence Matrix

Every public claim must map to at least one proof. Claims without proof stay `partial`, `experimental`, or `planned`.

| Claim | Status | Proof | Limit |
|---|---|---|---|
| BAGO has a functional CLI | Working | `tests/test_cli_root_compat.py` and `tests/test_chat_help_exec.py` | source and install surfaces must be tested separately |
| BAGO persists sessions | Working | `test_e2e.py` | live-model persistence is covered by optional Ollama test |
| BAGO can switch provider/model without losing session availability | Working | `test_e2e.py` | semantic quality after switch depends on model capability |
| BAGO supports Ollama local | Working when installed | `tests/test_ollama_autostart.py` and `tests/test_ollama_discovery.py` | requires local Ollama and downloaded model |
| BAGO can generate evidence bundles | Working | `tests/test_evidence_bundle_split.py` and `tests/test_code_forge_evidence_builder.py` | simulated bundle is the MVP proof |
| BAGO local API is safe by default | Working | `tests/test_security.py` and `test_security_release.py` | external bind requires token |
| BAGO install/update/uninstall flow is supported | Working | `tests/test_install_assistant_contract.py`, `tests/test_install_shortcuts_contract.py`, and `tests/test_install_remote_verification.py` | Windows-first install flow only |
| BAGO security validation is executable | Working | `tests/test_security.py` and `test_security_release.py` | security gates must fail closed |
| React UI is available | Optional | `tests/test_ui_dist_contract.py` and `tests/test_ui_live_smoke.cjs` | UI is not system authority |
| Cloud providers are supported | Partial | `docs/SUPPORT_MATRIX.md` | requires credentials and provider availability |
| RL learns preferences | Experimental | `tests/test_ollama_tool_calling.py` and `tests/test_f4_guardrails.py` | shadow/off by default; no authority |
| Agents/autopilot can execute work | Experimental | no stable MVP proof | must not be advertised as stable |

## Rule

If a claim cannot be mapped here, it must be removed from the README or marked as future/experimental in product docs.
