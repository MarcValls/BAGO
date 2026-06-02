# Claim Evidence Matrix

Every public claim must map to at least one proof. Claims without proof stay `partial`, `experimental`, or `planned`.

| Claim | Status | Proof | Limit |
|---|---|---|---|
| BAGO has a functional CLI | Working | `python bago_core\cli.py validate` | source and install surfaces must be tested separately |
| BAGO persists sessions | Working | `python test_e2e.py` | live-model persistence is covered by optional Ollama test |
| BAGO can switch provider/model without losing session availability | Working | `python test_e2e.py` | semantic quality after switch depends on model capability |
| BAGO supports Ollama local | Working when installed | `python bago_core\cli.py llm list` and dry-run start | requires local Ollama and downloaded model |
| BAGO can generate evidence bundles | Working | `python bago_core\cli.py evidence --test` | simulated bundle is the MVP proof |
| BAGO local API is safe by default | Working | `python test_security_release.py` and `python .bago\api\bridge.py --test` | external bind requires token |
| React UI is available | Optional | `cd ui-react; npm run build` | UI is not system authority |
| Cloud providers are supported | Partial | provider configuration plus `llm list` | requires credentials and provider availability |
| RL learns preferences | Experimental | `python bago_core\cli.py rl status` | shadow/off by default; no authority |
| Agents/autopilot can execute work | Experimental | no stable MVP proof | must not be advertised as stable |
| C++ runtime exists | Experimental | `python bago_core\cli.py cpp-runtime --help` | excluded from required release path |

## Rule

If a claim cannot be mapped here, it must be removed from the README or marked as future/experimental in product docs.
