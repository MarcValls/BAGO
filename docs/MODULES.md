# BAGO v4 Modules

This inventory marks what exists now and how it should be treated for distribution.

## Status Legend

- `working`: covered by current gates or active implementation.
- `partial`: exists but needs more coverage or docs.
- `planned`: documented in `PLAN_VERTICE`, not implemented yet.
- `experimental`: not required for v4 distribution.

## Root Runtime

| Module | Status | Notes |
|---|---|---|
| `bago_core/cli.py` | working | CLI entrypoint; delegates to launcher. |
| `bago_core/launcher.py` | working | `chat`, `launch`, `validate`, `llm`, `engine`, `appdata`, `cmd-rl`, `serve`, `evidence`, `claim`, `config`, `cpp-runtime`. |
| `bago_core/evidence_bundle.py` | working | evidence bundle generation and test mode. |
| `bago_core/claim_ledger.py` | working | traceable claims and validation summary. |
| `bago_core/cpp_runtime_host.py` | experimental | C++ reference host; not distribution blocker. |
| `bago_core/bago_true_bridge.py` | working | detects `bago_true`, RL source, AppData, cmd-rl and Spiral without importing live state. |
| `bago_core/rl_bridge.py` | working | RL status, shadow on/off/status, transition logging with `can_execute=false`. |
| `bago_core/rl_policies.py` | working | LinUCB/BC policy layer with numpy fallback and no execution authority. |

## `.bago/core`

| Module | Status | Notes |
|---|---|---|
| `session_manager.py` | working | session persistence, provider interaction, tests cover save/load. |
| `config_manager.py` | working | secure defaults; `auto_allow_tools=false`. |
| `credential_manager.py` | working | credential set/delete covered by E2E. |
| `context_store.py` | working | messages and timeline. |
| `switch_engine.py` | working | provider switch and downgrade compression path. |
| `provider_adapter.py` | working | provider interface and dataclasses. |
| `context_compressor.py` | working | compression for downgrade path. |
| `rl_engine.py` | partial | local feedback/reward primitives. Advanced policy layer is planned. |
| `tool_registry.py` | partial | command/tool registry; must stay safe-by-default. |
| `knowledge_base.py` | partial | knowledge storage surface. |
| `embedding_store.py` | partial | local embedding support. |
| `agent_gateway.py` | partial | agent abstraction. |
| `plan_engine.py` | partial | planning primitives. |
| `script_registry.py` | working | script discovery categories. |

## Providers

| Provider | Status | Notes |
|---|---|---|
| `ollama-local` | working | current healthy provider. |
| `ollama-cloud` | available | needs URL/config. |
| `copilot` | available | needs token/config. |
| `anthropic` | available | needs API key. |
| `codex` | available | needs API key/config. |
| `openrouter` | available | needs API key. |
| `opencode` | available | needs API key/config. |
| `cpp-local` | experimental | hidden unless explicitly included. |

## API

| Module | Status | Notes |
|---|---|---|
| `.bago/api/bridge.py` | working | local HTTP API, CORS hardened, RL status/shadow endpoints. |
| `.bago/api/control_shadow.py` | partial | shadow/control simulation primitives. |

## UI

| Surface | Status | Notes |
|---|---|---|
| `ui-react` | working | build passes; optional surface with RL bridge status. |
| `apps/mobile-expo` | planned | optional Expo Native UI. |

## Bridges

| Bridge | Status | Target |
|---|---|---|
| `bago_core/bago_true_bridge.py` | working | `C:\bago_true\.bago` |
| `bago_core/rl_bridge.py` | working shadow | `C:\bago_true\.bago\rl` |
| AppData bridge | working detection | `C:\Users\AMTEC_Terminal_1º\AppData\Local\Programs\BAGO` |

## Next Steps

1. Add richer RL transition features.
2. Do not mark a module working unless a gate proves it.
3. Keep policy inference separate from execution authority.
