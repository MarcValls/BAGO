---
name: github-repository-admin
description: Create a GitHub repository through the BAGO GitHub Admin MCP when the user explicitly requests repository creation. Verify the created repository identity before making a verified claim.
---

# GitHub Repository Admin

Use this skill only for explicit repository-creation intent.

## Contract

1. Resolve the intended repository owner, repository name, visibility, description, and whether GitHub should initialize it.
2. Treat creation as a material external mutation. Do not create a repository merely because a later workflow might benefit from one.
3. Call `create_repository` only after the required identity and visibility are resolved from the user request or authoritative context.
4. The MCP may authenticate from `GITHUB_TOKEN`, `GH_TOKEN`, or the GitHub CLI credential helper. Never write, echo, persist, or return the credential.
5. The tool performs read-after-write verification. A successful POST is `EXECUTED`; only `verified: true` supports a repository-exists/identity `VERIFIED` claim.
6. Report the exact owner/name/visibility/default branch returned by the tool and distinguish creation from verification.
7. If creation succeeds but verification fails or mismatches, report `BLOCKED` for verified attribution. Do not retry by creating a second repository under a different identity.
8. This capability creates repositories only. It does not delete, archive, transfer, rename, change visibility, or mutate unrelated repositories.

## Evidence shape

Prefer the tool fields `created`, `verified`, `full_name`, `visibility`, `default_branch`, `repository_id`, `html_url`, and `verification` as the operation evidence.
