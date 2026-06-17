# BAGO v4.6.2

[![Version](https://img.shields.io/badge/version-4.6.2-blue)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

BAGO is a local-first AI control plane. Its main job is to keep the session as the source of truth while providers and models remain interchangeable execution engines.

## What Problem It Solves

Most AI tools bind context to one provider or model. BAGO separates session state from model execution so a user can keep continuity while switching provider, model, API surface, or UI surface.

## Current Product Status

The stable MVP is intentionally small:

| Capability | Status | Proof |
|---|---|---|
| CLI | Working | `python bago_core\cli.py validate` |
| Persistent session | Working | `python test_e2e.py` |
| Provider/model switch | Working | `python test_e2e.py` |
| Ollama local startup | Working when Ollama is installed | `python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run` |
| Local API | Working, localhost-first | `python .bago\api\bridge.py --test` |
| Evidence bundles | Working | `python bago_core\cli.py evidence --test` |
| Security validation | Working | `python test_security_release.py` |
| React UI | Optional surface | `cd ui-react; npm run build` |

Post-MVP or experimental:

| Capability | Status | Boundary |
|---|---|---|
| RL policy layer | Experimental | shadow/off by default, no execution authority |
| Agents and autopilot | Experimental | must not be claimed as stable product behavior |
| C++ runtime | Experimental | not required for install, release, or validation |
| Cloud multiprovider completeness | Partial | depends on configured credentials and provider health |
| Advanced knowledge/embedding store | Partial | must remain separate from the MVP claim set |

## Install

Requirements:

- Windows-first runtime.
- Python 3.11 or newer.
- Ollama is optional, but required for the local live-model path.
- Cloud provider keys are optional and must stay outside the repository.

```powershell
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
.\install-v4.ps1 -Mode Express
```

Direct source run:

```powershell
python bago_core\cli.py validate
python bago_core\cli.py llm list
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

Remote installer for the latest published release:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1 -OutFile install-remote.ps1; .\install-remote.ps1"
```

Installation manager:

```powershell
bago profiles
bago install --profile des
bago install --profile ign
bago install --profile stable
```

## Minimum Use

```powershell
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b
```

Validation without opening a chat:

```powershell
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

Agent/headless command mode:

```powershell
bago exec /help
bago exec /commands json
bago exec /doctor
bago exec /status
```

## Main Commands

| Command | Purpose |
|---|---|
| `python bago_core\cli.py validate` | checks contracts, security defaults, and provider configuration |
| `bago exec /commands json` | exports the slash-command catalog for agents |
| `bago exec /doctor` | checks command catalog, headless execution, install roles, and provider health |
| `python bago_core\cli.py evidence --test` | validates evidence bundle generation |
| `python bago_core\cli.py llm list` | lists provider/model availability |
| `python bago_core\cli.py llm start ...` | starts or dry-runs provider-aware startup |
| `python bago_core\cli.py serve --host 127.0.0.1 --port 8080` | starts the local API |
| `python bago_core\cli.py rl status` | reports RL/shadow state without granting authority |

## Branch Governance (mandatory)

BAGO works with exactly three base branches:

- `main` (source of truth)
- `windows` (platform adaptation)
- `android` (platform adaptation)

Mandatory flow:

1. Common work merges into `main`.
2. Platform branches are updated from `main`.
3. No reverse-merges from `windows`/`android` into `main`.

Enforcement implemented in-repo:

- GitHub required check: `.github/workflows/branch-flow-guard.yml`
- Local push guard hook: `.githooks/pre-push`
- Hook setup: `pwsh scripts/setup_git_hooks.ps1`
- Branch protection apply script: `pwsh scripts/apply_branch_protection.ps1`

Break-glass (owner only, emergency):

1. Temporarily relax protection in GitHub branch settings.
2. Apply hotfix via PR flow if possible.
3. Re-apply guardrails with `pwsh scripts/apply_branch_protection.ps1`.

## Providers

| Provider | Status | Notes |
|---|---|---|
| `ollama-local` | Working | default local path when Ollama is installed |
| `ollama-cloud` | Partial | requires URL/key configuration |
| `copilot` | Partial | requires GitHub token/configuration |
| `anthropic` | Partial | requires API key |
| `codex` | Partial | requires API key/configuration |
| `openrouter` | Partial | requires API key |
| `opencode` | Partial | requires API key/configuration |
| `cpp-local` | Experimental | hidden from the default path unless explicitly requested |

## Security

BAGO must remain safe by default:

- API binds to `127.0.0.1` by default.
- Non-localhost API exposure requires a token.
- CORS must never use wildcard origin.
- Credentials must not enter Git, release ZIPs, UI bundles, or evidence samples.
- Tool execution is reject-by-default unless explicitly allowed.
- RL, agents, and automation remain suggestion/shadow surfaces unless explicitly authorized.

## Evidence

Every public claim must have at least one validation path:

- command,
- automated test,
- evidence bundle,
- functional contract,
- or minimal demo.

See [`docs/CLAIMS.md`](docs/CLAIMS.md) for the claim-to-evidence matrix.

## Roadmap

The near-term order is:

1. keep the MVP frozen,
2. keep version and Python requirements unified,
3. run the clean-machine gate before releases,
4. require evidence for every public claim,
5. keep partial/experimental modules out of stable product claims.

See [`docs/MVP.md`](docs/MVP.md), [`docs/MODULES.md`](docs/MODULES.md), and [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md).

## Known Limits

- The project is Windows-first today.
- macOS and Linux are experimental until their install and runtime gates are verified.
- A live Ollama conversation is optional and depends on a local Ollama service plus installed model.
- React UI is not the system authority; it consumes the backend API.
- RL, agents, C++ runtime, and advanced orchestration are not part of the stable MVP.

## License

BAGO is proprietary at this stage.

Allowed:

- inspect the public source,
- run local validation,
- submit issues or proposed changes through GitHub.

Not allowed without written permission:

- redistribute BAGO as a competing package,
- sell hosted or packaged copies,
- remove attribution,
- extract private release assets for third-party distribution.

Future licensing may change, but the current release line remains proprietary.

## Documentation

- [`MANUAL.md`](MANUAL.md) - user manual in Spanish.
- [`docs/MVP.md`](docs/MVP.md) - MVP boundary.
- [`docs/MODULES.md`](docs/MODULES.md) - module status matrix.
- [`docs/CLAIMS.md`](docs/CLAIMS.md) - claim evidence matrix.
- [`docs/SUPPORT_MATRIX.md`](docs/SUPPORT_MATRIX.md) - operating system support.
- [`docs/SECURITY.md`](docs/SECURITY.md) - security defaults and gates.
- [`docs/TESTING.md`](docs/TESTING.md) - validation commands.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) - distribution roadmap.
