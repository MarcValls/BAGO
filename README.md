# BAGO v4 — Session-First AI Control Plane

[![Version](https://img.shields.io/badge/version-4.1.5-blue)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

> BAGO is a local-first, session-persistent CLI for orchestrating AI providers. It keeps context across model switches, validates claims with evidence, and learns from your conversation style.

## What BAGO Does

- **Session Persistence** — conversations survive provider and model switches.
- **Provider Orchestration** — Ollama (local/cloud), Copilot, Anthropic, OpenRouter, Codex.
- **Intent-Aware Tooling** — BAGO auto-classifies your intent (chat / review / execute / work) and only offers tools when they are actually needed, preventing over-eager tool calls from small local models.
- **Auto-Training** — BAGO rescans your conversation history before each context compression to learn how you speak and refine its intent classifier.
- **Evidence & Contracts** — every claim BAGO makes can be recorded, bundled, and validated.

## Quick Start

### 1. Install
```powershell
# Windows (PowerShell)
.\install-v4.ps1 -Mode Express

# Or from an installed/runtime copy
bago install --mode Express

# Or clone and run directly
python bago_core\cli.py validate
```

The installer writes per-install non-secret settings to `install_config.json`.
Credentials default to session-only storage; persistent storage and external export require explicit opt-in and are encrypted.

### 2. Uninstall
```powershell
bago uninstall --dry-run
bago uninstall

# Remove user state too
bago uninstall --purge-state
```

Uninstall creates a backup ZIP before deleting the install directory and removes BAGO from PATH where possible.

### 3. Start Chatting
```powershell
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b
```

### 4. Dry-Run Check (no chat window)
```powershell
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

## Validation Gates

Before any release, the following must pass:

```powershell
python test_security_release.py
python test_e2e.py
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
```

## Project Structure

| Path | Description |
|------|-------------|
| `.bago/chat/` | REPL, system prompts, commands |
| `.bago/core/` | Session manager, tool registry, context compression, RL engine |
| `.bago/providers/` | Provider adapters (Ollama, Copilot, Anthropic, ...) |
| `.bago/api/` | Optional local REST API |
| `bago_core/` | Legacy CLI and runtime bridges |
| `docs/` | Architecture, security, testing, and distribution contracts |
| `scripts/` | Registered utility scripts |

## Documentation

- [`MANUAL.md`](MANUAL.md) — user manual
- [`docs/DISTRIBUTION_CONTRACT.md`](docs/DISTRIBUTION_CONTRACT.md) — presentation & distribution rules
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — distribution plan
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — runtime architecture
- [`docs/SECURITY.md`](docs/SECURITY.md) — security defaults and gates
- [`docs/TESTING.md`](docs/TESTING.md) — validation commands

## Distribution Rule

> Ship only what can be installed cleanly, started predictably, and validated with evidence.

See [`docs/DISTRIBUTION_CONTRACT.md`](docs/DISTRIBUTION_CONTRACT.md) for the full contract.
