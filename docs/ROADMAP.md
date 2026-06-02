# BAGO v4.1.5 Distribution Roadmap

This is the execution plan for keeping BAGO v4.1.5 small, verifiable, and releaseable.

## Decision

BAGO v4 ships as Python + React + contracts + evidence.

C++ is out of the main release path. Existing C++ files may stay as experimental references, but they do not block the release and must not be documented as required runtime.

Canonical operating docs:

- `docs/MVP.md` freezes the stable MVP.
- `docs/MODULES.md` marks working, partial, experimental, planned, and deprecated surfaces.
- `docs/CLAIMS.md` maps public claims to proof.
- `docs/SUPPORT_MATRIX.md` declares operating-system support.
- `RELEASE_CHECKLIST.md` is the release gate.

## Non-Negotiable Boundaries

- Source workspace: `C:\Bago_v4`
- Installed runtime: `C:\Program Files\BAGO`
- Mutable user state: `C:\ProgramData\BAGO\user`
- Do not package live state, logs, credentials, caches, `node_modules`, or temporary build output.
- Do not claim a capability unless a command or evidence bundle proves it.
- Python minimum: 3.11+.

## Phase 0 - Scope Freeze

Goal: define the product without expanding it while packaging.

Deliverables:

- Root `README.md` identifies BAGO v4 as a session-first AI control plane.
- C++ marked as future or experimental.
- Provider list confirmed: `codex`, `copilot`, `anthropic`, `openrouter`, `opencode`, `ollama-local`, `ollama-cloud`.
- React UI documented as optional surface, not a CLI dependency.

Exit criteria:

- No required v4 path depends on `cpp_runtime`.
- Roadmap and docs agree on install/state/source separation.

## Phase 1 - Real Baseline

Goal: document the system that exists, not the system we wish existed.

Actions:

- Inventory `.bago/core`, `.bago/providers`, `.bago/api`, `bago_core`, `ui-react`, `docs/contracts`.
- Mark every module as `working`, `partial`, `stub`, or `experimental`.
- Identify release exclusions in `.gitignore` and packaging scripts.
- Run the current validation commands.

Commands:

```powershell
python test_e2e.py
python test_security_release.py
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
```

Exit criteria:

- `docs/ARCHITECTURE.md` can be written from verified modules.
- Open risks are listed before feature work continues.

## Phase 2 - Security Gate

Goal: close the known distribution blockers.

Actions:

- `auto_allow_tools` defaults to `false`.
- `execute_command` remains allowlisted and uses `shell=False`.
- API defaults to `127.0.0.1`.
- Token is mandatory for non-localhost exposure.
- CORS never returns `Access-Control-Allow-Origin: *`.
- Security tests fail on regression.

Exit criteria:

- `python test_security_release.py` passes.
- `python bago_core\cli.py validate` reports no security failures.

## Phase 3 - Launcher And Provider Session

Goal: make startup predictable.

Actions:

- Normalize `bago.cmd`, `bago.ps1`, and `bago_core/cli.py` around one launch path.
- Implement or document `bago llm start` as provider-aware startup.
- Distinguish installed, configured, available, and selected providers.
- Persist the selected provider for the full session.
- Degrade clearly when a selected provider is unavailable.
- Keep experimental providers such as `cpp-local` out of the default startup path.

Current implementation:

```powershell
python bago_core\cli.py llm list
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
python bago_core\cli.py launch
```

Exit criteria:

- CLI starts from `C:\Bago_v4`.
- Installed package starts from `C:\Program Files\BAGO`.
- Provider choice survives the session.

## Phase 4 - Provider Contract

Goal: make provider behavior consistent.

Actions:

- Standardize provider methods: `chat`, `models`, `health`, `capabilities`.
- Keep local/Ollama opt-in where appropriate.
- Keep credentials outside the repo.
- Document provider configuration and failure modes.

Exit criteria:

- `docs/MODULES.md` reflects real provider behavior.
- `/providers`, `/models`, `/switch`, and `/status` behave consistently.

## Phase 5 - React UI

Goal: make UI useful without becoming the authority.

Actions:

- UI talks only to the local API.
- UI handles backend missing, provider down, no session, and auth errors.
- UI never embeds credentials or tokens in built assets.
- Build output goes to `ui-react/dist`.

Commands:

```powershell
cd ui-react
npm run build
```

Exit criteria:

- CLI works without UI.
- UI works when served by the API.

## Phase 6 - Evidence And Contracts

Goal: make release claims reproducible.

Actions:

- Keep `docs/contracts` as the truth boundary.
- Generate a release evidence bundle.
- Include manifest, checksums, report, command results, and session metadata.
- Separate sample evidence from release evidence.

Exit criteria:

- Release bundle exists under `docs/evidence/release-v4/`.
- Claims in `README.md` have evidence or are explicitly marked future.

## Phase 7 - OSS Documentation

Goal: make the project resumable and distributable.

Required docs:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/SECURITY.md`
- `docs/MODULES.md`
- `docs/RL_ENGINE.md`
- `docs/INTEGRATION.md`
- `docs/TESTING.md`
- `docs/ROADMAP.md`

Exit criteria:

- A new contributor can install, run, test, and understand limits without reading `SIGUIENTE.txt`.

## Phase 8 - Packaging

Goal: produce a clean installable artifact.

Include:

- `bago_core`
- `.bago/core`
- `.bago/providers`
- `.bago/api`
- `docs`
- `ui-react/dist`
- root launchers and install scripts

Exclude:

- `.bago/state`
- `.bago/logs`
- credentials
- `ui-react/node_modules`
- Python caches
- temporary release folders
- local session evidence unless intentionally packaged as sample docs

Exit criteria:

- Install creates runtime in `C:\Program Files\BAGO`.
- User state is created in `C:\ProgramData\BAGO\user`.
- Smoke test passes on a clean target.
- Local clean package can be generated with `python scripts\package_v4.py`.

## Phase 9 - Final Gate

Commands:

```powershell
python -m py_compile bago_core\cli.py
python test_e2e.py
python test_security_release.py
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
powershell -NoProfile -ExecutionPolicy Bypass -File .\smoke-test.ps1
```

Ship only when:

- No C++ dependency is required.
- No live state or credentials are packaged.
- Provider startup is deterministic.
- Security gate passes.
- Evidence bundle exists.
- Docs match behavior.
