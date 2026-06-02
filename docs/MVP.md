# BAGO MVP Boundary

This document freezes the current BAGO product boundary. Anything outside this table is not a stable product claim until it has a command, test, evidence bundle, or contract proving it.

## Stable MVP

| Area | Included | Minimum proof |
|---|---|---|
| CLI | `bago_core\cli.py`, launchers, validation commands | `python bago_core\cli.py validate` |
| Session persistence | save/load session state and context | `python test_e2e.py` |
| Provider switch | switch provider/model while keeping the session available | `python test_e2e.py` |
| Ollama local | local model path when Ollama is installed | `python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run` |
| API local | localhost API bridge for integrations and UI | `python .bago\api\bridge.py --test` |
| Evidence | simulated evidence bundle generation | `python bago_core\cli.py evidence --test` |
| Security gate | defaults, CORS, token, secrets and shell checks | `python test_security_release.py` |
| Install | basic Windows install/update/uninstall flow | `.\install-v4.ps1 -Mode Express` |

## Outside The MVP

| Area | Status | Rule |
|---|---|---|
| RL active execution | Experimental | shadow/off by default; no execution authority |
| Agents | Experimental | no stable product claim without per-agent proof |
| Autopilot/orchestrator | Experimental | suggestion/planning only unless explicitly authorized |
| C++ runtime | Experimental | not required for release or install validation |
| Full cloud multiprovider support | Partial | depends on credentials and provider-specific health |
| Advanced knowledge base | Partial | document as partial until tested end to end |
| Embeddings/vector search | Partial | optional dependency path only |
| Complex React UI | Optional | UI consumes backend only and is not authority |
| Extended monitoring | Experimental | evidence-only, no surveillance or control authority |

## Product Rule

BAGO is a session-first control plane. The session is the source of truth; providers and models are replaceable engines.

The release line must stay small until the MVP proves reproducible on a clean Windows target.
