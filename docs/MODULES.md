# BAGO v4.1.5 Modules

This inventory marks what exists now, how it is proven, and what must not be claimed as stable yet.

## Status Legend

- `working`: covered by an active gate or direct implementation proof.
- `partial`: exists, but coverage or behavior is incomplete.
- `experimental`: available only behind explicit flags, shadow mode, or non-MVP paths.
- `planned`: documented intent without stable implementation.
- `deprecated`: retained only for compatibility or migration.

## MVP Runtime

| Module | Status | Proof command | Known limit |
|---|---|---|---|
| `bago_core/cli.py` | working | `python bago_core\cli.py validate` | delegates many commands to hidden `.bago` runtime |
| `bago_core/launcher.py` | working | `python bago_core\launcher.py --test` | installed-runtime behavior must be tested separately |
| `.bago/core/session_manager.py` | working | `python test_e2e.py` | live model proof is optional |
| `.bago/core/context_store.py` | working | `python test_e2e.py` | stores mutable state outside release packages |
| `.bago/core/config_manager.py` | working | `python test_security_release.py` | config files are per-install state |
| `.bago/core/credential_manager.py` | working | `python test_e2e.py` | credentials must never ship in release artifacts |
| `.bago/core/switch_engine.py` | working | `python test_e2e.py` | semantic quality after switch depends on target model |
| `.bago/core/context_compressor.py` | working | `python test_e2e.py` | downgrade compression is not a guarantee of full semantic fidelity |
| `bago_core/evidence_bundle.py` | working | `python bago_core\cli.py evidence --test` | simulated evidence is the MVP gate |
| `bago_core/claim_ledger.py` | working | `python bago_core\cli.py claim --help` | public claims must be listed in `docs/CLAIMS.md` |

## Providers

| Provider | Status | Proof command | Known limit |
|---|---|---|---|
| `ollama-local` | working | `python bago_core\cli.py llm list` | requires local Ollama for live calls |
| `ollama-cloud` | partial | `python bago_core\cli.py llm list` | requires URL/key configuration |
| `copilot` | partial | `python bago_core\cli.py llm list` | requires token/configuration |
| `anthropic` | partial | `python bago_core\cli.py llm list` | requires API key |
| `codex` | partial | `python bago_core\cli.py llm list` | requires API key/configuration |
| `openrouter` | partial | `python bago_core\cli.py llm list` | requires API key |
| `opencode` | partial | `python bago_core\cli.py llm list` | requires API key/configuration |
| `cpp-local` | experimental | `python bago_core\cli.py llm start --provider cpp-local --dry-run` | hidden from default path and outside MVP |

## API And UI

| Surface | Status | Proof command | Known limit |
|---|---|---|---|
| `.bago/api/bridge.py` | working | `python .bago\api\bridge.py --test` | non-localhost bind requires token |
| `.bago/api/control_shadow.py` | partial | `python .bago\api\bridge.py --test` | observation/control simulation only |
| `ui-react` | optional working | `cd ui-react; npm run build` | Chat surface only; consumes backend API and is not authority |
| `manager` | partial | `node --check manager\js\session-manager.js` | Administration/diagnostics only; installed-runtime health must be validated separately |
| `apps/mobile-expo` | planned | none | not part of current repo gate |

## Experimental Or Partial Core

| Module | Status | Proof command | Known limit |
|---|---|---|---|
| `.bago/core/rl_engine.py` | experimental | `python bago_core\cli.py rl status` | shadow/off by default, no execution authority |
| `bago_core/rl_bridge.py` | experimental | `python bago_core\cli.py rl shadow status` | safe observation only |
| `bago_core/rl_policies.py` | experimental | `python bago_core\cli.py rl eval` | policy output is advisory |
| `.bago/core/tool_registry.py` | partial | `python test_e2e.py` | tool execution must stay permission-gated |
| `.bago/core/knowledge_base.py` | partial | no MVP gate | storage exists, automatic injection is not stable |
| `.bago/core/embedding_store.py` | partial | optional dependency gate | depends on local embedding support |
| `.bago/core/agent_gateway.py` | experimental | no MVP gate | agents are post-MVP |
| `.bago/core/plan_engine.py` | experimental | no MVP gate | planning is not autonomous authority |
| `bago_core/cpp_runtime_host.py` | experimental | `python bago_core\cli.py cpp-runtime --help` | reference host only |

## Bridges

| Bridge | Status | Proof command | Known limit |
|---|---|---|---|
| `bago_core/bago_true_bridge.py` | working detection | `python bago_core\cli.py engine status` | detects external state, does not import authority |
| AppData bridge | working detection | `python bago_core\cli.py appdata status` | optional compatibility surface |
| cmd-RL bridge | working detection | `python bago_core\cli.py cmd-rl status` | optional status only |

## Product Rule

Do not mark a module `working` unless a command above proves it. Do not mention `partial`, `experimental`, or `planned` modules as stable product features in the README.
