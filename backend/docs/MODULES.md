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
| `ollama-cloud` | working | `python bago_core\cli.py llm verify` |
| `copilot` | working | `python bago_core\cli.py llm verify` |
| `anthropic` | working | `python bago_core\cli.py llm verify` |
| `codex` | working | `python bago_core\cli.py llm verify` |
| `openrouter` | working | `python bago_core\cli.py llm verify` |
| `opencode` | working | `python bago_core\cli.py llm verify` |
| `.bago/api/control_shadow.py` | working | `python .bago\api\control_shadow.py --test` |
| `.bago/core/rl_engine.py` | working (observer-only) | `python .bago\core\rl_engine.py --test` |
| `bago_core/rl_bridge.py` | working (shadow/off only) | `python bago_core\cli.py rl shadow status` |
| `bago_core/rl_policies.py` | working (non-executing) | `python -m pytest -q tests\test_rl_contract.py` |
| `.bago/core/tool_registry.py` | partial | `python test_e2e.py` |
| `.bago/core/knowledge_base.py` | working: SQLite + FTS5 + deprecation + hybrid API | `python -m pytest -q tests\test_knowledge_embeddings_advanced.py` |
| `.bago/core/embedding_store.py` | working: validated upsert + cosine search + filters + stats | `python -m pytest -q tests\test_knowledge_embeddings_advanced.py` |
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

Cloud verification is deterministic and offline; live use still requires each
provider's own credential and account access.
