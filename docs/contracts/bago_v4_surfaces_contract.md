# BAGO Chat and Manager Surfaces Contract

Status: closed for review

## Principle

The backend owns state and execution. Chat and Manager are clients with different responsibilities; neither is an authority.

## Ownership

| Surface | Owns | Must not own |
|---|---|---|
| BAGO Chat | current conversation, composer, history, active session, recent session load/save, active model switch, chat-safe commands | credentials, provider registry, global catalog, RL/simulation controls, installations, releases, connector policy, audit administration |
| BAGO Manager | installations, PieceStore, connectors, policies, releases, jobs, rollback, health, drift, credentials, provider/catalog defaults, RL/simulation settings, tool permissions, session administration and diagnostics | conversation composer, duplicate chat history, provider execution logic, session state as a private copy |
| Backend / SessionManager | session identity, context, provider calls, switching, permissions, validation, evidence and persistence | presentation-specific state |

## Chat API Budget

The React chat may request only the data needed for the active conversation:

- `GET /session`
- `GET /history`
- `GET /menu` for saved-session shortcuts
- `GET /models/<active-provider>`
- `POST /chat`
- `POST /command`
- `POST /switch`

Chat must not poll catalog, simulation, RL, provider registry, release, installation or audit endpoints.

## Manager Rules

- Session administration may create, inspect and reconfigure sessions.
- Conversation and orchestration prompts open in BAGO Web or BAGO CLI, not inside Manager.
- Every mutation is requested through backend commands and remains subject to policy, validation and evidence.
- Secrets are never rendered or copied into browser state.

## Shared Rules

- A provider/model change preserves the session identity when the backend allows it.
- UI state never overrides backend state.
- A capability may exist in CLI/headless form without being exposed in Chat.
- Administrative commands remain discoverable in Manager, not in the primary Chat interface.

## Acceptance Checks

1. Building `ui-react` succeeds without catalog, simulation, RL or provider-registry state.
2. The Manager has no conversation composer or duplicate message history.
3. Chat can load history, send a message, save/load a session and switch the active model.
4. Manager mutations still pass backend preflight and evidence gates.

Regression check:

```powershell
python -m unittest discover -s tests -p test_surface_contract.py
```
