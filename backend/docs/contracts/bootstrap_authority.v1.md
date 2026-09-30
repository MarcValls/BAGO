# BAGO clean-machine bootstrap authority v1 (proposal)

Status: `PROPOSED` / `NOT_CANON` / `NOT_IMPLEMENTED`.

This document defines the minimum contract needed to close the installer P0
without creating a second `AuthorizationBoundary` or treating NSIS as an
implicit Permit. It is a design input for implementation and verification;
it does not authorize production changes by itself.

## Problem boundary

The normal maintenance route is already:

```text
AuthorizationBoundary
  -> consumed direct-user Permit
  -> ExecutionGateway
  -> system.install.apply / SystemInstallEffectAdapter
  -> one-use helper ticket
  -> materializer
```

A clean machine has no BAGO session or ledger before an installer starts. The
bootstrap must therefore establish a trusted authority host before the first
BAGO-controlled material effect. Passing a checksum, clicking an installer,
or launching a child PowerShell process is not a Permit.

## Non-negotiable invariants

1. There is one canonical `AuthorizationBoundary` and one `ExecutionGateway`.
2. The bootstrap host may be externally trusted by the operating system or a
   release signature, but it must not mint a parallel BAGO Permit format.
3. Each material operation retains its existing canonical owner:
   `system.install.apply` owns install/repair/reinstall; rollback uses
   `system.install.rollback`; uninstall uses `system.install.uninstall`.
   The bootstrap must not collapse these operations or carry approval from one
   operation into another. Any package staging performed by BAGO belongs to
   the matching install owner and occurs only after its Permit is consumed.
4. The install operation identity binds at least:
   `session_id`, `effect_id`, action, trusted bootstrap artifact identity,
   authenticated release manifest identity, source-tree/package digest, helper
   digest, destination identity and its existing `target_state_sha256`, and
   requested options. The canonical `ExecutionRequest` already binds the
   registry `policy_version`; do not create a second policy field or digest.
   Rollback and uninstall each bind their own target state and operation
   identity through their existing contracts.
5. No installation material effect occurs before `system.install.apply` is
   accepted and its Permit consumed. Authority-internal or server-policy
   startup state needed to establish the session may precede that Permit only
   through its existing Gateway owner. Any external OS handoff must be narrowly
   defined, authenticated and bound to the exact bootstrap release; it is not
   itself an installation Permit.
6. A child helper can consume one ticket only once. A ticket for extraction
   cannot authorize registry writes, shortcuts, uninstall or another target.
7. Reparse substitution, destination drift, helper/package replacement,
   replay and concurrent target use fail closed before materialization.
8. Installer and helper sinks remain visible to the inventory. No exclusion,
   lowered confidence or scanner-only reclassification is permitted.

## Required request shape

The bootstrap preparation must produce a canonical request equivalent to:

```json
{
  "effect_id": "system.install.apply",
  "scope": "system",
  "action": "install",
  "bootstrap_artifact_sha256": "<sha256>",
  "release_manifest_sha256": "<sha256>",
  "source_tree_sha256": "<sha256>",
  "package_sha256": "<sha256>",
  "helper_sha256": "<sha256>",
  "install_dir": "<canonical target>",
  "target_state_sha256": "<absent-or-tree-fingerprint>",
  "options": {}
}
```

`action=install`, `source_tree_sha256`, `helper_sha256`, `package_sha256`,
`install_dir`, `target_state_sha256`, and `options` already exist in
`install_plan.py`; the generic `ExecutionRequest` binds `session_id`,
`effect_id`, fingerprint and current policy version. The bootstrap/manifest
identities are an `EXTEND` candidate to that canonical descriptor, not a new
plan object. The host must verify that the signed release manifest binds the
actual tree and helper before requesting approval, and the owner must revalidate
the same identity immediately before materialization.

## Trust handoff options

Only one option may be selected and implemented after review:

### A. Externally trusted bootstrap host (only viable direction so far)

The operating system loads a small signed host that authenticates the complete
authority implementation and release payload before executing mutable bundle
code. The host loads the canonical BAGO authority implementation in-process,
creates the bootstrap session through existing owners, presents a direct-user
approval surface bound to the exact operation, and dispatches to the existing
owner. It must not spawn Electron/Python or extract executable code before the
trust handoff. If the only feasible package format requires OS-mediated bundle
extraction, that handoff must be explicit, authenticated and must replace the
NSIS route; keeping both official paths leaves the P0 open. The signing/build
pipeline must bind host + source tree + helper + release candidate. A code
signature or checksum never substitutes for the operation Permit.

#### A1. Windows MSIX trust handoff (selected direction; implementation open)

A loose Authenticode-signed executable or a signed NSIS setup is not the
required trust handoff: Windows may show a SmartScreen reputation prompt for a
new signed publisher, and the user may proceed. The concrete Windows candidate
is a minimal packaged bootstrap host delivered as a signed MSIX and installed
by Windows App Installer or the Store. Windows package deployment must validate
the package signature and trusted publisher before it registers or launches the
host. The manifest publisher must exactly match the signing certificate
subject. Where supported, declare `uap10:PackageIntegrity` and require its
runtime integrity enforcement (Windows 10 version 2004 / build 19041 or later).
The package may use the documented `windows.fullTrustProcess` extension for a
native host; this capability is not itself authorization to perform BAGO's
installation effects.

The OS-mediated package deployment is a narrowly scoped external provisioning
effect for the signed bootstrap package identity. It may not modify BAGO's
chosen application target, user registry/shortcuts, or BAGO state. After
launch, the host must use the canonical `AuthorizationBoundary` and
`ExecutionGateway`; the actual selected-target install remains
`system.install.apply` after Permit consumption. The repository decision dated
2026-09-29 selects this seed-only boundary for implementation. OS provisioning
of the seed is outside the BAGO selected-target install effect only under these
strict limits; any mutation to the selected target, BAGO state, product
registry, or shortcuts violates the boundary.

Selection authorizes implementation but does not assert that the package
exists or that its publisher/signature has been verified. The repository still
has no MSIX manifest or package build/sign/publish path. The protected
`release-signing` environment and publisher identity have not been verified for
MSIX, and no package signer or thumbprint/rotation policy may be assumed from
workflow YAML. The P0 remains open until the artifacts and clean-machine checks
pass.

#### Independent architecture review (read-only)

The independent review concludes
`MSIX_SEED_HANDOFF = ARQUITECTÓNICAMENTE_COMPATIBLE_CON_CONDICIONES`, while
`P0-INS-NSIS-01 = OPEN`, `PASS_FOR_PLANNING = NO`, and
`UNIQUE_EXECUTION_BOUNDARY = NOT_YET`. MSIX is a viable spike direction only
if Windows provisions and launches the signed seed package while every effect
on BAGO's selected target remains under the existing Boundary -> Gateway ->
owner path. This is a conditional design review, not implementation approval.

The following contract gaps remain mandatory blockers:

1. **Authenticated package identity:** `package_sha256` is caller-supplied by
   the current handler/plan and does not authenticate the MSIX identity,
   publisher, manifest, release candidate or helper. Derive and revalidate
   these values from trusted OS/package context and an authenticated release
   manifest.
2. **Native interaction proof:** `X-Bago-Channel: desktop` is forgeable and
   the current boundary accepts channel labels as context. A one-use native
   interaction capability must bind package identity, session, operation
   fingerprint and target without creating a second Permit issuer.
3. **Elevated helper handoff:** install/apply, uninstall, and process
   termination now resolve inbox Windows PowerShell from the OS-reported
   system directory instead of searching `PATH` or trusting `SystemRoot`.
   The helper still trusts user-writable JSON ledger/ticket state; same-user
   process isolation is not supplied by file mode bits. The handoff must
   authenticate the exact operation across the privilege boundary before
   this gap can close.
4. **Target exclusivity:** the current worktree now wraps install/apply,
   rollback, uninstall, and archive rollback dispatch in one canonical
   install-target lease/fencing claim. Focused local concurrency and resource
   identity tests pass. A Windows multiprocessing regression now exercises the
   full Gateway path: an apply adapter holds the target while a separate
   process presents an uninstall Permit for the same target; the contender is
   rejected as `system_install_target_busy` before its adapter runs. Clean-
   machine and elevated-helper lifecycle evidence remain required before this
   item can be closed.
5. **Pre-Permit bootstrap isolation:** `SessionManager` may prepare a mutable
   workspace mirror during construction. Bootstrap must load authority code,
   modules and DLLs only from the authenticated package path and must not stage
   payload or mutate a mirror before Permit consumption.
6. **Seed lifecycle boundary:** MSIX seed update/removal is OS-owned lifecycle
   for the seed package only. It must not be conflated with BAGO target
   `system.install.rollback` or `system.install.uninstall`.
7. **Post-install launch:** the existing `process.execute` contract does not
   yet cover launching installed Electron, and Electron currently starts the
   backend directly. Extend the existing process owner and remove the parallel
   launch path.
8. **Reachable NSIS removal:** NSIS remains in three official workflow paths.
   Build, publish, E2E and operational lifecycle routes must all move to the
   approved bootstrap; any reachable official NSIS route keeps the P0 open.

#### Implementation progress 2026-09-29

The current dirty worktree asks the backend to show a server-side native
confirmation for strong API challenges before issuing a Permit. It also adds
one canonical target lease across install/apply, rollback, uninstall, and
archive rollback dispatch, and replaces PATH-based PowerShell selection with
the OS-reported inbox interpreter for the install helpers and governed process
termination. The scoped tests for authorization, install, uninstall, native
confirmation, Windows executor resolution, and claim fencing pass locally.

These changes close code-level subparts of gaps 2, 3, and 4; the respective
acceptance items remain open because Windows interaction evidence, authenticated
helper IPC across elevation, and clean-machine install evidence have not been
run. The cross-process SQLite/Gateway race regression passes on the current
Windows candidate, but does not emulate UAC or a clean machine. Gaps 1, 5, 6, 7,
and 8 remain open. No MSIX artifact or replacement release route exists yet.

The review used the current install plan/handler/adapter, authorization
boundary, execution gateway, SessionManager and release workflows as evidence.
It made no source changes and ran no tests. All eight findings remain
unresolved; retain the P0 stop and do not begin the global sink partition or
sink repairs until this bootstrap authority gap is closed through its required
clean-machine evidence.

#### Remote signing configuration check (read-only)

On 2026-09-27, the authenticated GitHub API confirmed that repository
environment `release-signing` exists. Its configured secret names are
`AZURE_CLIENT_ID`, `AZURE_SUBSCRIPTION_ID` and `AZURE_TENANT_ID`; no values were
retrieved. Its non-secret variable names are `BAGO_SIGNING_ACCOUNT`,
`BAGO_SIGNING_ENDPOINT`, `BAGO_SIGNING_PROFILE` and `BAGO_SIGNING_PUBLISHER`,
and each was confirmed non-empty without printing values. This confirms
configuration presence only; it does not prove credential validity, Azure
role assignment, publisher-to-package identity equality or a successful MSIX
signature.

The environment initially had no protection rules and `deployment_branch_policy`
was null (GitHub defines null as allowing deployments from all branches). The
environment was then restricted to the explicit `main` branch policy and the
API read-back confirmed that rule. `main` currently requires the `validate`
status check, enforces branch protection for administrators, and disallows
force pushes/deletion; its required PR approval count is zero. The release
workflow is `workflow_dispatch` with a validated `release_tag` input, so it
must be dispatched from `main` and use the input to select the immutable tag.
This remote configuration change narrows who can expose the signing
environment; it does not replace package identity verification, add reviewer
approval or close any installer sink.

Microsoft documents Azure Artifact Signing as the recommended production
signing path for MSIX packages and provides SignTool integration for GitHub
Actions: <https://learn.microsoft.com/en-us/windows/msix/package/sign-msix-package-guide>.
That confirms the format is supported in principle. BAGO's existing
`azure/artifact-signing-action@v2` workflow has only been exercised for a loose
EXE and NSIS setup; compatibility of its exact profile with the package
publisher and the produced MSIX remains unverified until an actual package is
built, signed and checked by Windows package deployment.

#### Current P0 sink map (scoped; not the global partition)

The candidate-bound inventory identifies 33 runtime-unbound sinks in
`releases/bago-installer.nsi`, all in one reachable production installer file.
Their compression is `33 sinks -> 1 file -> 1 root cause -> 2 repair clusters ->
2 existing owners`. Root cause: NSIS owns install and uninstall material
effects outside BAGO's current authorization boundary.

| Cluster | Sinks and operations | Target owner | Class | Evidence and required extension |
|---|---|---|---|---|
| `P0-NSIS-APPLY` | 27: 14 `filesystem.write`, 2 `process.execute`, 11 `system.configuration.write`; `bago-installer.nsi:48-100` | `system.install.apply` / `SystemInstallEffectAdapter` | `EXTEND` | Same material responsibility and existing strong-Permit owner, but the clean-machine request must bind trusted MSIX/manifest/publisher identity and the owner must govern the exact product registration and shortcut effects now performed directly by NSIS. Current owner path uses `install-v4.ps1`, which manages payload, PATH and Explorer context-menu operations; it does not contain the NSIS `Software\\BAGO` install identity and uninstall registration writes. |
| `P0-NSIS-UNINSTALL` | 6: 4 `filesystem.delete`, 2 `system.configuration.write`; `bago-installer.nsi:111-116` | `system.install.uninstall` / `SystemInstallUninstallEffectAdapter` | `EXTEND` | Reuse the existing strong-Permit uninstall owner, but bind and remove the exact NSIS registration keys and desktop/Start-menu shortcuts under its target identity. The current lifecycle helper makes a recoverable install-tree backup and removes BAGO PATH/context-menu entries; it does not implement the NSIS registration/shortcut cleanup. |

`system.install.rollback` remains a separate owner and operation; do not merge
rollback into apply or uninstall. The scanner evidence is bound to the current
inventory file and exact worktree snapshot. This scoped two-cluster map does
not classify the other 232 runtime-unbound findings, so it is not
`PASS_FOR_PLANNING` and does not permit global repair lanes.

Closure of this P0 requires replacing the reachable NSIS installer and its
uninstaller, plus all NSIS build/release/E2E/lifecycle routes, with the approved
package flow. Tests must prove denial before any file, registry, shortcut or
process effect, replay/drift rejection, rollback/uninstall identity separation,
and clean-machine rejection of unsigned, untrusted, altered or mismatched
package identity. Existing tests that assert the NSIS path must be replaced by
these owner-contract tests; scanner rules and visibility remain intact.

The current test surface divides as follows:

| Test surface | Required disposition |
|---|---|
| `test_embedded_installer_rollback.py` | Replace NSIS extraction/finalize and NSIS toolchain assumptions with clean-machine MSIX acceptance/rejection, consumed-Permit first-effect, rollback, retry and crash-recovery tests. |
| `test_authenticode_release_contract.py` | Replace the signed-NSIS lifecycle assertions with signed-MSIX manifest/Publisher/package-integrity checks and ensure the signing job is bound to `main` and an exact release tag. |
| `test_global_install_closure.py` | Replace “NSIS initializes plugin dir before extract” with package-root immutability and proof that no target, registry, shortcut, helper process or mirror effect precedes Permit consumption. |
| `test_system_install_gateway.py` | Extend apply-owner coverage for package/manifest/publisher identity, target lease/fencing, helper authentication, replay and all pre-effect denials. |
| `test_system_install_uninstall_gateway.py` | Extend uninstall-owner coverage for exact legacy registry/shortcut cleanup, recoverable backup and target-bound identity; prove rollback remains a separate effect. |
| `test_effect_sink_inventory.py::test_vbscript_and_nsis_scanners_detect_installer_effects` | Keep this scanner fixture. It proves the detector still finds NSIS sinks; never remove NSIS detection or add exclusions. |

The release replacement must update `build-installer.yml`,
`build-release-installer.yml`, and both installer-producing jobs in
`canonical-ci.yml`; an E2E-only or release-only swap leaves an official NSIS
route reachable.

#### MSIX host implementation spike 2026-09-29

The repository contains a native .NET full-trust MSIX seed host under
`bootstrap/msix-host/`. It embeds CPython 3.14.7 and Python.NET 3.1.0, loads
the canonical AuthorizationBoundary, ExecutionGateway, and SessionManager in
process, disables the workspace mirror, and verifies the signed package
manifest and payload digest before importing the authority. The manifest
requests `runFullTrust`, runtime Package Integrity, and Windows build 19041+.
The seed UI intentionally exposes no install action while package-bound native
approval and authenticated elevated-helper handoff remain open.

The local Windows trial closed AppX publisher trust for this one test: a
short-lived certificate (`DE162FC62302DAF9D92415872EBF8ADB6FA2F9BD`) was
placed in the required trust stores, SignTool `/pa` passed, and
`Add-AppxPackage` registered identity
`BAGO.Bootstrap.Test_4.11.1.0_x64__n45qsze3n717y`. The test exposed and fixed
one digest mismatch: Windows adds `AppxMetadata/CodeIntegrity.cat` after
registration, so the host now excludes that OS-generated catalog along with
block map and signature metadata while continuing to hash the authority and
payload. The isolated repackage reached AppX activation, but the host then
exited before Python initialization; no new canonical session was observed.
The test certificate and package were subsequently removed. No production
publisher, clean-machine startup, or release claim is established.

The test also exposed that the build script must retain `hostpolicy.dll` from
the self-contained publish; the build now asserts its presence. The launched
Windows process still reported that this DLL could not be loaded from its
WindowsApps package path. Resolve that MSIX full-trust host limitation and
prove in-process session creation before treating the MSIX host as executed
end-to-end. `backend/tests/test_msix_bootstrap.py` (3 passed), dotnet publish,
and the successful AppX add/remove are bounded local evidence only. Gaps 1,
2, 5, 6 and P0 remain open.
### B. Pre-provisioned authority runtime

The installer is allowed to operate only when a trusted BAGO authority runtime
already exists. This reuses the existing maintenance owner but does not satisfy
first-install clean-machine support; it would be a deliberate product-scope
restriction and would leave the standalone installer out of closure.

### C. Native installer adapter

The installer host itself implements the canonical adapter boundary. This is
acceptable only if it is the same owner and protocol as the Python gateway,
with no second Permit issuer or divergent identity rules. A merely signed NSIS
script is not sufficient.

This remains a proposal, not canon. Option A is the only direction identified
so far that could preserve clean-machine installation and the single BAGO
authority, but it is not yet proved implementable. In particular, existing
`build_install_plan()` requires a real source directory and helper before the
challenge; the bootstrap must either use an authenticated OS-extracted bundle
that replaces NSIS, or extend the existing owner to consume embedded package
bytes after Permit consumption. `package_sha256` alone proves neither release
authenticity nor the relation between the helper and source tree.

## Verification matrix before implementation closure

- first-effect trace on a clean machine;
- forged, absent, expired and replayed ticket;
- changed package/helper/target after approval;
- target reparse substitution and destination drift;
- two concurrent installs targeting one root;
- crash before ticket claim, after claim and before finalize;
- rollback and uninstall with unrelated or prior successful permits;
- no second Permit issuer and no duplicate registered owner;
- complete inventory retains every installer sink;
- `--strict-classification` and `--strict-runtime` on the same committed
  candidate;
- full backend suite and independent final verification.

Until this matrix is implemented and passes, the P0 remains open and
`UNIQUE_EXECUTION_BOUNDARY` must remain `NOT_YET`.
