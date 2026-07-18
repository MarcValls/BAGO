# BAGO Modules

This inventory records what is proven, what is partial, and what is still experimental.
Structural layers and runtime flows live in `docs/ARCHITECTURE.md`.

## Status Legend

- `working`
- `partial`
- `experimental`
- `planned`
- `deprecated`

## Proven Runtime

| Module | Status | Proof |
|---|---|---|
| `bago_core/cli.py` | working | `python bago_core\cli.py validate` |
| `bago_core/launcher.py` | working | `python bago_core\launcher.py --test` |
| `.bago/core/session_manager.py` | working | `python test_e2e.py` |
| `.bago/core/context_store.py` | working | `python test_e2e.py` |
| `.bago/core/config_manager.py` | working | `python test_security_release.py` |
| `.bago/core/credential_manager.py` | working | `python test_e2e.py` |
| `.bago/core/switch_engine.py` | working | `python test_e2e.py` |
| `.bago/core/context_compressor.py` | working | `python test_e2e.py` |
| `bago_core/evidence_bundle.py` | working | `python bago_core\cli.py evidence --test` |
| `bago_core/claim_ledger.py` | working | `python bago_core\cli.py claim --help` |
| `.bago/api/bridge.py` | working | `python .bago\api\bridge.py --test` |

## Partial And Experimental

| Module | Status | Proof |
|---|---|---|
| `ollama-cloud` | partial | `python bago_core\cli.py llm list` |
| `copilot` | partial | `python bago_core\cli.py llm list` |
| `anthropic` | partial | `python bago_core\cli.py llm list` |
| `codex` | partial | `python bago_core\cli.py llm list` |
| `openrouter` | partial | `python bago_core\cli.py llm list` |
| `opencode` | partial | `python bago_core\cli.py llm list` |
| `.bago/core/control_shadow.py` | partial | `python .bago\api\bridge.py --test` |
| `.bago/core/rl_engine.py` | experimental | `python bago_core\cli.py rl status` |
| `bago_core/rl_bridge.py` | experimental | `python bago_core\cli.py rl shadow status` |
| `bago_core/rl_policies.py` | experimental | `python bago_core\cli.py rl eval` |
| `.bago/core/tool_registry.py` | partial | `python test_e2e.py` |
| `.bago/core/knowledge_base.py` | partial | no MVP gate |
| `.bago/core/embedding_store.py` | partial | optional dependency gate |
| `.bago/core/agent_gateway.py` | experimental | no MVP gate |
| `.bago/core/plan_engine.py` | experimental | no MVP gate |
| `apps/mobile-expo` | planned | none |

## Bridges

| Bridge | Status | Proof |
|---|---|---|
| `bago_core/bago_true_bridge.py` | working detection | `python bago_core\cli.py engine status` |
| AppData bridge | working detection | `python bago_core\cli.py appdata status` |
| cmd-RL bridge | working detection | `python bago_core\cli.py cmd-rl status` |

## Rule

Only keep a module marked `working` if a command above still proves it.
