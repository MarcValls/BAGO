---
name: bago-audit
description: Run the BAGO repository audit pipeline adapted from the Codex workpack using Copilot custom agents, preserving evidence, RunId isolation and read-only audit boundaries.
---

# BAGO Audit

Use for full or targeted audits of BAGO. The task definitions are in `references/tasks/`.

Recommended sequence: `00-preflight`, `01-inventory`, `02-architecture`, `03-frontend`, `04-backend`, `05-contracts`, `06-workspace`, `07-features`, `08-security`, `09-tests-ci`, `10-hygiene`, `11-performance`, `12-truth-authority`, `13-synthesis`, then `14-refactor-plan`.

Implementation tasks `20`, `21` and verification task `22` require an explicitly approved change scope.

For each audit run, bind findings to one RunId and one baseline HEAD. Audit agents must not edit. Test execution must record pre/post Git status. Synthesis must re-check critical/high findings rather than blindly concatenate subagent output.
