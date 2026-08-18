# BAGO Evidence Protocol — Provisional Adapter

For each material claim, maintain this chain:

`claim -> source/action -> evidence -> verification scope -> conclusion`

## Rules

1. Attribute repository claims to actual file/VCS/tool evidence.
2. Attribute runtime claims to actual command/tool execution.
3. Record identity when it matters: path, branch, commit SHA, artifact hash, environment, version, workflow/run id, or timestamp.
4. Verification must target the final state being concluded about.
5. Earlier successful checks do not automatically verify later edits.
6. A tool being documented does not prove the capability is currently available.
7. An action being intended does not mean it was executed.
8. If evidence is partial, narrow the conclusion instead of expanding the claim.

## Example

Claim: unit tests pass for final branch HEAD.

Source/action: CI workflow run triggered by final HEAD.

Evidence: workflow id + head SHA + completed status + success conclusion.

Verification scope: exact final branch HEAD, workflow jobs covered by that run.

Conclusion: tests covered by that workflow are `VERIFIED`; anything outside its jobs remains unverified.
