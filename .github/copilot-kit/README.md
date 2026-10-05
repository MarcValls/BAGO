# BAGO toolkit for GitHub Copilot CLI

This is the entry point for the BAGO material that is usable or adaptable in
GitHub Copilot CLI. It is an index, not a new authority: existing files remain
in their native locations and are the source of truth. Do not copy these
resources into a second active authority tree or treat this catalog as proof that a runtime
feature was loaded.

## Portable ZIP delivery

The explicitly requested portable snapshot is built with
`python .github\copilot-kit\build_pack.py --output <new-zip-path>`.
It contains actual source files, not just this index. Nothing is installed or
activated by extracting it. Read `INTEGRATION_PLAN.md` before integration.
The generated `INVENTORY.md`, `INVENTORY.json`, `SOURCE_MANIFEST.json`, and
`PACK_CHECKS.json` enumerate individual files, meaning, origin, hashes,
manifest drift, and packaging evidence. They describe this snapshot, not
runtime certification. Historical and live state are intentionally excluded. The ignored
`backend/.bago/node_control/` directory is local runtime data, not pack source;
its evidence, installation, connector, piece, and compatibility records are
excluded as a whole. The ignored `backend/.bago/runtime/` state and handoff
area is also excluded; continuity source is taken only from the selected
tracked helper roots. The ignored `.gabo/copilot/` continuity tree is also
excluded.

| ZIP section | Content and boundary |
|---|---|
| `01-copilot\source\` | Agents, skills with references, prompts, instructions; preserve source paths for reviewed integration. |
| `02-framework\source\` | Framework agents, roles, prompts, workflows, templates, tools and supporting source modules; not a standalone BAGO installation. |
| `03-integrations-review\source\` | Hooks, MCP, extension and plugin sources, isolated for review; no automatic registration. |
| `04-other-harnesses\source\` | Codex runners/agents/tasks and Pi skills/prompts; adapt rather than install directly. |
| `05-continuity-reference\source\` | Runtime helper scripts only; no active context, memory, receipts, handoffs or credentials. |
| `06-documentation\` | Catalog, integration plan and packaging script. |

The rebarrido identified 54 Python tool sources versus 33 manifest entries;
the builder recalculates missing entries, undeclared sources and hash drift.
The current snapshot also differs from 32 of the 33 historical manifest hashes;
the granular inventory records the exact names.
The roles directory contains definitions plus factory/manifest/documentation;
do not count every file as a distinct operational role.
Source exists does not mean implemented behavior has been exercised.

## Start here

1. Apply `..\copilot-instructions.md` and the relevant files in
   `..\instructions\`.
2. Load `..\skills\bago-toolkit\SKILL.md` when selecting/adapting BAGO assets.
   Load `..\skills\bago-core\SKILL.md` for non-trivial work. Use
   `..\skills\repository-engineering\SKILL.md` for repository changes,
   `..\skills\bago-audit\SKILL.md` for audits, and
   `..\skills\bago-frontend-engineering\SKILL.md` for material frontend work.
3. Select an agent from `..\agents\` that matches the task and its authority.
4. Use a prompt from `..\prompts\` only when its task fits. Prompts 20-22 are
   scoped workflows; implementation requires approval and verification is
   independent and read-only.
5. Resolve the current repository and BAGO state before making claims. Keep the
   `.gabo\copilot\` Copilot continuity runtime, the repository `.bago\` runtime,
   and BAGO framework sources under `backend\.bago\` distinct.

## Copilot-targeted material already in the repository

| Kind | Current source | Use |
|---|---|---|
| Repository instructions | `..\copilot-instructions.md` | Active BAGO engineering, authority, evidence, and delegation constraints. |
| Path-specific instructions | `..\instructions\backend.instructions.md`, `frontend.instructions.md`, `governance.instructions.md`, `release.instructions.md`, `tests.instructions.md` | Load for work under the corresponding area. |
| Custom agents / roles | `..\agents\` | Copilot agent definitions. Prefer these over the legacy Codex TOML roles. |
| Skills | `..\skills\bago-core\`, `bago-audit\`, `bago-frontend-engineering\`, `repository-engineering\` | Native Copilot skill sources with their referenced material. Avoid loading duplicate Pi versions for the same task. |
| Prompts | `..\prompts\` | Audit sequence `bago-00` through `bago-14`; approved implementation and verification `bago-20` through `bago-22`; plus focused `bago-frontend-*` prompts. |
| Hook candidate | `..\hooks\bago-runtime.json` and `..\hooks\bago_hook.py` | Existing event/config and handler sources. Their compatibility with the Copilot CLI extension lifecycle has not been established by this catalog. |
| Plugin catalog | `..\plugin\marketplace.json` | Lists the existing `bago-github-admin` plugin. Treat its installation/runtime compatibility as a separate check. |

### Agent role map

| Responsibility | Agent definitions |
|---|---|
| Orchestration and change coordination | `bago-assistant.agent.md`, `bago-repository-engineer.agent.md` |
| Repository discovery and tracing | `bago-repo-explorer.agent.md`, `bago-code-mapper.agent.md` |
| Read-only audit | `bago-architecture-auditor.agent.md`, `bago-backend-auditor.agent.md`, `bago-contracts-auditor.agent.md`, `bago-frontend-auditor.agent.md`, `bago-hygiene-scanner.agent.md`, `bago-performance-auditor.agent.md`, `bago-security-auditor.agent.md`, `bago-test-auditor.agent.md`, `bago-truth-auditor.agent.md`, `bago-ui-architecture-auditor.agent.md`, `bago-ui-state-tracer.agent.md` |
| Planning, implementation, and mechanical work | `bago-refactor-planner.agent.md`, `bago-implementation-worker.agent.md`, `bago-mechanical-worker.agent.md`, `bago-frontend-engineer.agent.md` |
| Independent verification | `bago-final-verifier.agent.md`, `bago-frontend-verifier.agent.md` |

All names above resolve under `..\agents\`. Keep the boundary intact: auditors
and verifiers do not edit; workers do not certify their own changes.

## Scripts and command-line tools

| Source | Reuse status | Boundary |
|---|---|---|
| `.gabo\copilot\bin\bago.py` | Direct project-local lifecycle helper (`status`, `check`, `verify`, and other state operations). | Run from the BAGO repository root. State-changing subcommands mutate local continuity state; use only when the task calls for them. |
| `.bago\bin\bago.py` | BAGO repository runtime helper. | Keep separate from `.gabo\copilot\` and framework sources under `backend\.bago\`; do not merge their state or authority. |
| `.codex\bago-workpack\Run.ps1`, `Run-Audit.ps1`, `List-Tasks.ps1` | Useful orchestration and task-source reference. | Codex CLI-specific role dispatch is not automatically a Copilot CLI tool. Adapt the runner/dispatch boundary before invoking it from Copilot. |
| `.codex\bago-remediation\Run-Remediation.ps1` | Reusable only as a reviewed high-impact workflow. | Can fetch, create branches/worktrees, push, open PRs, and merge. Do not expose or run automatically; require explicit authorization for each external or destructive effect. |
| `.github\hooks\bago_hook.py` | Existing hook-handler script. | The JSON hook declaration is not a Copilot CLI SDK extension. Verify event mapping and behavior before adapting it. |
| `backend\.bago\tools\` and `backend\.bago\tools.manifest.json` | BAGO-native candidate utilities. The manifest declares 33 tools; `tools\README.md` describes standalone tools and older porting notes. | Not registered as Copilot CLI tools by this catalog. Resolve manifest/source/runtime drift and review each tool's effects before wrapping it. Some tools read/write files, scan secrets, change runtime state, or control services. |
| `backend\.bago\mcp\` | BAGO MCP server, tool catalogs, matrix, and launcher. The checked-in config defaults to read-only and disables mutation/dangerous modes. | The config contains machine-specific checkout roots and legacy routing labels. Do not copy it as-is; rebind the root and confirm the server/tool contracts before use. |

The repository has no project-discoverable BAGO extension under
`.github\extensions\`. A Copilot CLI SDK extension source does exist at
`backend\.bago\extensions\bash-runner\extension.mjs`; it registers
`bash-runner_exec`, `bash-runner_run_script`, and `bash-runner_bago_run`.
However, these expose arbitrary shell commands, arbitrary script paths, and
BAGO commands. Do not install or enable this source as-is for routine agent
use. Review it for least privilege, path/root validation, and per-action
authorization before making it discoverable.

## BAGO-native framework material

The runtime sources under `backend\.bago\` contain additional adaptable
material that is not itself a Copilot agent/skill definition:

| Source | Reusable material | Adapter boundary |
|---|---|---|
| `backend\.bago\agents\` | Agent bootstrap, factory/gateway code, contracts, and project adapter prompts. | Use the behavior and contracts as design input; do not map BAGO runtime agents directly to CLI subagents without preserving the gateway and executor boundaries. |
| `backend\.bago\roles\` | Role factory, role manifest, and role template. | Roles require explicit planning/approval and an executor in their source system; a role definition alone does not grant Copilot delegation. |
| `backend\.bago\prompts\` | Bootstrap, project analysis, task, review, and state-maintenance prompts. | Reconcile with the more specific Copilot prompts in `..\prompts\` before reusing. |
| `backend\.bago\workflows\` | Session start, exploration, implementation, refactor, debug, continuity, and review playbooks. | Treat as workflow source material; select/adapt one flow at a time rather than auto-running the whole set. |
| `backend\.bago\templates\` | Change, evidence, role, workflow, and evaluation templates. | Templates are inputs for artifacts, not executable CLI capabilities. |
| `backend\.bago\extensions\bash-runner\extension.mjs` | Copilot CLI SDK extension source with three shell/script/BAGO runner tools. | Exists outside the CLI project discovery directory and was not verified as loaded. Its broad execution surface needs security hardening and explicit authorization before installation. |

`backend\.bago\tools\README.md` explicitly distinguishes its standalone
utilities from BAGO's runtime `ToolRegistry`. The generated
`backend\.bago\tools.manifest.json` declares 33 tool entries; that declaration
does not prove each file is current, registered, safe to expose, or compatible
with the CLI. The extension above is a separate execution surface. Select and
verify tools individually.

## Roles and skills from other harnesses

| Source | Reuse status |
|---|---|
| `.codex\agents\*.toml` | Fifteen legacy Codex role definitions. Use the corresponding `..\agents\*.agent.md` definition where available; do not copy Codex model or sandbox fields as Copilot CLI configuration. |
| `.agents\skills\bago-auditors\`, `bago-workers\`, `bago-final-verifier\` | Pi-specific skills. Their role boundaries and procedures are reusable concepts, but their Pi metadata/tool assumptions are not a Copilot CLI runtime binding. Prefer the corresponding skills and agents under `..\skills\` and `..\agents\`. |
| `.codex\bago-workpack\tasks\` | Detailed audit, implementation, and verification task prompts. Reuse as source material only after confirming they agree with the current Copilot prompts and repository instructions. |

## Manifests and evidence limits

- `.gabo\manifests\agents.json`, `tools.json`, `prompts.json`, and `roles.json`
  are generated snapshots dated 2026-09-09 with zero entries. They are not a
  complete inventory or authority; inspect the actual source directories.
- The remaining `.gabo\manifests\` files are generated snapshots too:
  `tools_sprints.json` is empty, `api.json` has no configured canonical roots,
  and `ui_react.json` lists seven entries. These snapshots do not inventory the
  runtime assets under `backend\.bago\`.
- `.gabo\copilot\config.json` labels the Copilot engineering pack
  `PREPARED`. The continuity state and existing conflict records also say
  native Copilot CLI loading was not established in the pack's build
  environment. This index does not upgrade that status.
- Existing `.github\agents\`, `.github\skills\`, prompts, and instructions are
  Copilot-targeted assets in native-looking formats. Native CLI loading has not
  been verified for this pack. Workpack runners, Pi/Codex configurations, and
  hook declarations need individual compatibility review before being treated
  as executable Copilot CLI features.

## Scope and maintenance

This catalog covers the active `BAGO` checkout only; release payloads,
archives, and other worktrees are intentionally excluded to avoid mixing
historical copies with current sources. Keep this page as a pointer map:
update it when a source path or adapter changes, and never use it to override
repository instructions, BAGO framework state, or explicit user authorization.
