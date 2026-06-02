# BAGO v4 Security

Security in BAGO v4 is enforced by defaults, tests, validation, and release exclusions.

## Defaults

| Control | Required state |
|---|---|
| Tool auto-approval | disabled by default |
| API host | local by default |
| CORS | no wildcard |
| Non-localhost API | token required |
| C++ runtime | experimental only |
| RL authority | shadow/off by default |

## Tool Execution

Commands must avoid broad shell execution. The current release gate checks that command execution does not expose `shell=True`.

Allowed future command execution must be:

- explicit.
- allowlisted where needed.
- logged.
- reject-by-default for unsafe operations.

## API Exposure

Local development can use:

```text
127.0.0.1
localhost
::1
```

Any non-localhost bind must require a token. CORS must echo only allowed local origins and must never return `Access-Control-Allow-Origin: *`.

## UI Authority

The React UI is a visual/control surface only:

- session state lives in the backend.
- provider selection lives in the backend.
- credentials never enter the UI bundle.
- critical commands go through backend permission checks.
- a missing UI build must not break the CLI.

## RL, Agents, And Automation

RL, agents, plans, and autopilot are not execution authority in the stable MVP.

Required defaults:

- RL is `shadow/off` by default.
- `can_execute=false` unless a future explicit gate enables it.
- suggestions and execution are separate actions.
- decisions are logged before promotion to canary/full modes.
- public docs must mark these surfaces as experimental until they have dedicated tests.

## Secrets

Secrets must not be committed or packaged.

Disallowed in release artifacts:

- credentials.
- API keys.
- live session state.
- `.bago/state`.
- `.bago/logs`.
- `C:\ProgramData\BAGO\user`.
- checkpoints unless explicitly released as public sample data.

## Evidence Before Claims

A public claim is valid only if it has:

- a command that proves it, or
- an evidence bundle, or
- a contract that declares its validation path.

Claims without evidence remain future or experimental.

## Security Gates

Run:

```powershell
python test_security_release.py
python bago_core\cli.py validate
```

Expected:

- `auto_allow_tools=false`.
- no open CORS wildcard.
- token required for non-localhost API.
- no exposed `shell=True`.
- no open culpas.
- no failed claims.

## Monitor Scope

`PLAN_VERTICE/monitor` records plan execution events only. It must not capture:

- keystrokes.
- screen content.
- user browsing.
- passwords.
- unrelated process activity.

## Stop Rules

Stop immediately if:

- a security gate fails.
- a release artifact includes state or credentials.
- a feature cannot be validated but is documented as working.
- a command would overwrite installed runtime without backup/rollback.

## Next Steps

1. Add negative tests for future bridge commands.
2. Add release artifact scanning before ZIP/installer generation.
3. Keep all new external integrations token-safe by default.
