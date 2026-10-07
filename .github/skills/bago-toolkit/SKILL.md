---
name: bago-toolkit
description: Discover and reuse BAGO scripts, tools, prompts, roles, skills, agents, workflows, and Copilot CLI adapters. Use when assembling or adapting BAGO capabilities for GitHub Copilot CLI.
---

# BAGO toolkit for GitHub Copilot CLI

Use this skill as the routing entry point for BAGO assets. The inventory and
compatibility notes are in `../../copilot-kit/README.md`; read that catalog
before selecting a source. Existing source files remain authoritative. Do not
copy whole trees, silently promote proposals to canon, or claim a CLI feature
loaded merely because a source file exists.

## Select the right source

- **BAGO repository engineering:** use `bago-core` and
  `repository-engineering`, then the matching `.github/agents/*.agent.md`
  role and `.github/prompts/` prompt.
- **Repository audits:** use `bago-audit` and a read-only audit agent. Do not
  let audit or verification roles edit files.
- **Frontend work:** use `bago-frontend-engineering`, the applicable
  path-specific instructions, and a frontend engineer or auditor as appropriate.
- **BAGO framework workflows, role definitions, and templates:** consult
  `backend/.bago/{workflows,roles,prompts,templates}` as source material.
  Reconcile conflicts against current repository instructions and explicit
  user intent before adapting.
- **BAGO tools and MCP:** inspect `backend/.bago/tools/`,
  `backend/.bago/tools.manifest.json`, and `backend/.bago/mcp/` for each
  candidate. A manifest entry or MCP tool name is not proof that the capability
  is current, registered, or safe to expose to an agent.
- **Project continuity:** use `.gabo/copilot/` only for Copilot project-local
  continuity. Keep it distinct from repository `.bago/` state and framework
  sources under `backend/.bago/`.

## Compatibility and safety

1. Prefer the existing Copilot-targeted files under `.github/agents/`,
   `.github/skills/`, `.github/prompts/`, `.github/instructions/`, and
   `.github/copilot-instructions.md`; verify CLI discovery separately.
2. Treat `.codex/` and Pi-specific `.agents/skills/` files as source material,
   not directly loadable CLI configuration. Preserve their role boundaries
   when adapting.
3. Treat hooks, plugins, MCP configuration, and `extension.mjs` sources as
   separate runtime integrations. Check the actual CLI contract, binding,
   permissions, working-directory handling, and failure behavior before
   enabling them.
4. Do not expose arbitrary shell execution, arbitrary script paths, network
   mutation, repository writes, or BAGO state-changing commands through an
   automatically invoked tool. Require narrowly scoped operations and the
   applicable explicit authorization.
5. Preserve separation of duties: auditors/verifiers are read-only; workers
   execute only approved scopes; a worker does not certify its own change.
6. Report what was inspected, adapted, loaded, or executed as separate facts.
   Use `PROPOSED`, `PREPARED`, `EXECUTED`, `VERIFIED`, and `VALIDATED`
   accurately; never promote a status without its required evidence.

This skill is an adapter index, not a new BAGO authority and not proof that
every listed integration has passed native Copilot CLI verification.
