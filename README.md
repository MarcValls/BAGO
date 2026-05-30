# BAGO v4

BAGO v4 is a session-first AI control plane.

The user talks to BAGO. BAGO keeps the session, chooses the active provider, preserves context across switches, and records evidence for claims that need to be proven.

## Current Scope

The v4 distribution path is:

- Python CLI and runtime
- provider-aware startup
- local HTTP API
- optional React UI
- contracts and evidence bundles
- secure defaults

C++ is not required for v4 distribution. Existing C++ runtime files are experimental references only and must not block the main release path.

## Runtime Boundaries

- Source workspace: `C:\Bago_v4`
- Installed runtime: `C:\Program Files\BAGO`
- Mutable user state: `C:\ProgramData\BAGO\user`

Do not package live state, logs, credentials, caches, `node_modules`, or temporary build output.

## Quick Start

```powershell
python bago_core\cli.py validate
python bago_core\cli.py llm list
python bago_core\cli.py llm start --provider ollama-local
```

For a dry startup check without opening the chat:

```powershell
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

## Provider Startup

`bago llm list` separates providers into:

- installed/configured providers ready to use
- providers available to configure
- experimental providers hidden from the main path

`cpp-local` is hidden by default because C++ is out of scope for the main v4 release.

To show experimental providers explicitly:

```powershell
python bago_core\cli.py llm --include-experimental list
```

## Validation

Minimum local gate:

```powershell
python test_security_release.py
python test_e2e.py
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
```

## Documentation

- `docs/ROADMAP.md` - distribution plan
- `docs/ARCHITECTURE.md` - runtime architecture and boundaries
- `docs/SECURITY.md` - security defaults, gates, and release exclusions
- `docs/MODULES.md` - implementation inventory and status
- `docs/RL_ENGINE.md` - RL shadow-first integration plan
- `docs/INTEGRATION.md` - install/state/backend integration rules
- `docs/TESTING.md` - gate commands and expected results
- `docs/contracts/` - runtime, REPL, evidence, knowledge, governance, and engineering contracts
- `docs/COMMUNITY.md` - community knowledge and evidence model
- `MANUAL.md` - current user manual

## Distribution Rule

Ship only what can be installed cleanly, started predictably, and validated with evidence.
