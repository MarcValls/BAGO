# Broker redesign — detailed design work record

Status: `EXECUTED` for read-only design work; architecture/protocol remains `BLOCKED`.
Goal: `CRIT-HOST-HELPER-IPC-NOOP-20260930-SUCCESSOR`.
Candidate inspected: HEAD `b10178bf8a13d0035079e989e46c36760dbd2a46`, branch `fix/spbe-runtime-fix1-20260927`; porcelain inventory 7,863 entries, manifest SHA-256 `6b471e7d8be4a1b233aaf432eb35a0dac84b97d912893d0cc84b91a0be870c29`. This is a hash of the porcelain manifest, not a complete content fingerprint. Preserve all pre-existing dirty work.

No product code was edited. No tests, builds, signing, process/helper launch, UAC prompt, activation, service installation, or material effect was run.

## Decision frame and seven-point disposition

The requested seven actions are handled in order. Each item is classified `CLOSED_FOR_DESIGN`, `OPEN`, or `BLOCKED`; completion of a written analysis is not proof that Windows behavior works.

### 1. Broker model, identity, and privileges — `OPEN`

**Current chain (observed in source):**

```text
backend/.bago/api/handlers_install.py
  -> AuthorizationBoundary + ExecutionGateway
  -> SystemInstallEffectAdapter.execute()
  -> _write_helper_ticket() [user-state JSON]
  -> PowerShell process / Start-Process -Verb RunAs
  -> backend/install-v4.ps1 materializes installation effects
```

The API constructs the canonical request and boundary/Gateway flow. `ExecutionGateway.execute()` consumes the Permit before calling the adapter; `SystemInstallEffectAdapter` then revalidates the plan/request, writes a user-state ticket, and spawns a PowerShell child. The PowerShell child reads the ledger/ticket and checks the consumed Permit proof; `Invoke-SelfElevatedInstall` then uses `Start-Process -Verb RunAs` if elevation is needed. The script claims the ticket and performs payload, registry/environment, shortcut and Explorer integration work. Relevant source points include `handlers_install.py:51-73`, `execution_gateway.py` Gateway dispatch, `system_install.py:151-267`, and `install-v4.ps1:170-260, 364-390, 691-755, 1467-1536`.

**Candidate ranking (not a selection):**

- First investigate a signed, one-operation elevated broker process. It avoids a persistent privileged daemon and could own the existing Boundary/Gateway/adapter chain for the duration of one confirmed operation. This is only a candidate: MSIX package activation/elevation semantics and operation-specific trusted UI are not established.
- Retain a persistent Windows service only as a second candidate if a one-shot packaged broker cannot be launched with a provable OS identity. A service needs a dedicated service identity/SID, restricted token/privilege inventory, service-object and binary-directory ACLs, process-object access tests, and a solution for UI in the active user session. Do not default to `LocalSystem`.

**Required design decision:** Compare concrete Windows launch models, including supported MSIX full-trust activation, signed packaged executable elevation, and a dedicated service installer. For each, state process token user/SIDs, integrity level, enabled privileges, process DACL at creation, executable/configuration ACL, package identity, lifetime and recovery. Reject any model where a same-user medium process can obtain `PROCESS_VM_WRITE`, `PROCESS_VM_OPERATION`, `PROCESS_CREATE_THREAD`, or `PROCESS_DUP_HANDLE` against the authority process. A service SID alone is not accepted without the actual token/DACL proof.

Microsoft documentation consulted:
- [Interactive Services](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services): services cannot directly interact with users on supported Windows; documented patterns use `WTSSendMessage` or a separate GUI process communicating over ACL-protected IPC. It warns against LocalSystem windows on the interactive desktop.
- [Process Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights): process-object DACL and process rights.
- [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw): callers creating processes can provide an initial process security descriptor; MSIX activation's ability to do so is not established.

### 2. Direct user confirmation resistant to spoofing — `BLOCKED`

**Documented fact:** UAC consent/credential prompts are displayed on the secure desktop by default. The prompt authorizes an executable to run elevated; the cited Microsoft description does not establish that a custom operation's exact target/options are displayed and approved by that prompt. Windows documents that services should communicate through a separate GUI process; it does not make a normal user-session GUI trustworthy merely because a service requested it. UIAccess is restricted to assistive-technology scenarios and is not adopted for BAGO.

**Candidate to evaluate:** Broker derives the immutable effect/target/options itself and presents them in broker-owned UI only after OS-mediated broker launch. Host strings are never displayed as authority. The UI must be bound to the same elevated process that owns the Permit/Gateway, or provide a separately proven authenticated UI decision. A normal high-integrity window is not assumed to defeat visual overlay/spoofing; that residual risk must be resolved against the stated threat model.

**Hard stop:** If Windows offers no supported operation-bound confirmation surface resistant to same-user medium-integrity spoofing/automation for the selected launch model, this design cannot pass. Do not substitute a host UI, forged desktop channel header, custom non-secure prompt, UIAccess misuse, or a generic UAC prompt that does not show the exact effect/target.

**Verification gate:** Documentation/API review first. Any no-op interactive Windows feasibility test that builds/signs/activates a test package or invokes UAC requires separate explicit authorization. That test must include overlay, window-message/input automation, spoofed prompt, cancel, and exact-target display cases; no installation effects.

References:
- [How UAC works](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/how-it-works)
- [Interactive Services](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services)
- [UI Automation Security Overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview)

### 3. Mutual IPC authentication — `OPEN`, downstream of 1–2

**Candidate transport:** one-shot local named pipe created by the broker with a non-default explicit security descriptor. The default pipe DACL is too broad for this purpose. Bind ACLs to the intended logon/session identity and the expected packaged client as applicable; reject remote clients and unexpected sessions. Treat host payloads as untrusted proposals, not permits.

**Minimum peer evidence to specify:** pipe security descriptor; first-instance/squatter behavior; server PID and client PID from OS APIs; process creation time to detect PID reuse; process token user/logon SID/integrity/package SID; package full name and publisher/certificate validation; release-manifest/helper digest; protocol version, bounded canonical framing, per-operation nonce/replay cache, deadline and cancellation. PID by itself, nonce by itself, pipe name by itself, caller-supplied publisher strings, and user-writable files are insufficient.

`GetNamedPipeClientProcessId` returns a PID only; it does not authenticate image, package or publisher. Microsoft documents custom named-pipe security descriptors and warns that the default DACL grants broad read access. A logon SID can limit access to a logon session. These facts support a candidate test plan, not protocol selection.

References:
- [Named Pipe Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
- [GetNamedPipeClientProcessId](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid)

**Verification gate:** wrong/same-user process, wrong package/publisher, pipe squatting, remote/cross-session caller, PID reuse, replay, malformed framing, peer exit, denial of process-query rights, and host-injected misleading proposal. On any ambiguity, deny without material effects. Actual OS tests only after protocol and separate test authorization as applicable.

### 4. Existing effect-owner placement — `OPEN`

**Direction-level placement proposal:** move the canonical authorization runtime and Gateway into the selected broker process. The MSIX host becomes an untrusted request/progress client. `AuthorizationBoundary` remains the unique Permit issuer; `ExecutionGateway` consumes the Permit; the existing `system.install.*` adapter remains the unique logical effect owner. The helper remains a materialization endpoint and never creates authority.

The owner-placement review must trace all actions individually:

| Operation/effects | Existing authority/owner candidate | Required disposition |
|---|---|---|
| apply/repair/reinstall | effect `system.install.apply` -> `SystemInstallEffectAdapter` -> `install-v4.ps1` | `REUSE/EXTEND` only if one canonical adapter retains validation and the helper cannot operate without its exact consumed request. Replace the user-writable ticket/argv proof channel with the approved in-memory broker channel. |
| rollback | effect `system.install.rollback` -> `SystemInstallRollbackEffectAdapter` | Keep its own effect identity, Permit and adapter; never accept an apply Permit. |
| uninstall | effect `system.install.uninstall` -> `SystemInstallUninstallEffectAdapter` | Keep its own target-state binding and owner; do not treat helper as Permit issuer. |
| post-install launch / shell integration | existing process/system configuration owners, with NSIS paths still open | Map each material sink to its current canonical owner before migration. No NSIS bypass or new parallel owner. |

**Service-account issue:** the installer mutates both machine-sensitive state and user-specific surfaces (e.g., user PATH/profile/shortcuts and Explorer context menu). A service or alternate-admin token may not be the target interactive user's identity. For every resource, list required hive/profile/token, owner SID, access needed, whether impersonation is required, and TOCTOU/replay controls. If cross-account UAC cannot bind the initiating user's direct intent to those user-scoped effects, explicitly fail closed for that scenario rather than silently modifying the admin account's profile.

Do not yet run Python.NET or the whole backend inside a privileged service. First identify the minimum canonical authority/runtime dependencies and whether they can be hosted without loading user-writable modules/DLLs. This is an architecture decision, not justification for duplicating the Gateway.

### 5. UAC cancellation and alternate administrator credentials — `OPEN`

Windows documents that standard-user elevation requires valid administrator credentials and that UAC prompts normally use the secure desktop. That verifies OS elevation interaction, not BAGO's exact operation-level intent or which user's HKCU/profile should be modified.

Required policy decision for detailed design:
- For same-user admin consent, bind the elevated broker to the original session and user SID.
- For over-the-shoulder (different admin account) credentials, either prove user/session/target binding and user-profile ownership end-to-end, or explicitly reject/fail closed in the initial supported contract. Never persist credentials, pass them to the medium host, or allow admin-token identity to silently replace the initiating user's identity.
- Cancel, timeout, UAC policy denial, unexpected token/SID/session, broker restart, or retry means no effect; retry needs fresh intent and a new Permit.

No UAC prompts were run. Testing cancellation and alternate credentials is a separately authorized Windows gate.

Reference: [How UAC works](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/user-account-control/how-it-works).

### 6. Broker install/update/recovery — `OPEN`

Before selecting service vs one-shot process, create a release lifecycle design covering: trusted initial provisioning, publisher/certificate pinning and rotation, immutable package/release manifest, protected executable and configuration directories, atomic update/rollback, service registration ACL if applicable, uninstall and stale state, crash recovery, signed helper validation, and denial when Windows/package policy or signatures cannot be checked.

No first-run self-installing service from a user-writable host/script. No user-writable service executable/config path. Do not conflate OS provisioning of a bootstrap/broker with the selected-target `system.install.*` effect. If a service installer itself changes machine state, document its distinct, explicit bootstrap authorization and owner; do not let it become an unattended second installer owner.

**Evidence gate:** clean-machine service/package install/update/uninstall and tamper rejection, after separate explicit authorization for any activation or material system effect. Until that gate, lifecycle design is not verified.

### 7. Independent review and authorization gates — `OPEN`

Direction-only review already returned `PASS_FOR_DETAILED_DESIGN`; it did not review this detailed design, choose a concrete protocol, or approve implementation. A fresh independent review must assess the completed service/process model, UI proof, IPC specification, owner mapping, alternate-account contract, lifecycle/recovery, threat model, and candidate-bound evidence. Every critical finding must be resolved before implementation.

Separate explicit authorizations remain mandatory for:
1. Any broker authority-boundary product implementation not covered by the earlier IPC implementation authorization.
2. Build/sign/package deployment/activation and no-op UAC or interactive OS peer-authentication tests.
3. Clean-machine material installation or other system-state changes.

Do not claim P0 closure or investigate the historical UI close as part of this goal. That causal question remains separate and unresolved.

## Ordered next actions

Dependency order: `1 -> 2 -> 3 [hard stop if unsupported] -> (4 and 5) -> 6 -> 7`. Work on downstream design remains conditional; no protocol or implementation proceeds while point 3 is blocked.

1. Complete a resource-by-resource effect/identity map for apply, repair, rollback, uninstall, shortcuts, PATH, registry and post-install launch from current owners.
2. Compare one-shot elevated broker and persistent service against exact supported Windows activation, token, DACL, UI/session, account and lifecycle APIs. Select neither until the exact UI route passes documentation feasibility.
3. Close operation-bound confirmation feasibility. This is the earliest hard gate: stop the redesign if no supported resistant confirmation surface exists.
4. Only after point 3, specify IPC APIs, ACL, mutual peer identity, framing/replay/deadline and negative tests.
5. Choose owner placement and alternate-account policy from the effect map; prove no duplicate Permit/Gateway/owner.
6. Complete signed deployment/update/recovery model and adversarial test plan.
7. Request independent review of the detailed design; update goal/status and request appropriate separate execution authorizations.

## Evidence performed in this block

- Source read-only trace: `handlers_install.py`, `authorization_boundary.py`, `system_install.py`, `install_plan.py`, `install-v4.ps1`, MSIX host files, and bootstrap authority contract.
- Microsoft Learn pages fetched: Interactive Services, Named Pipe Security and Access Rights, GetNamedPipeClientProcessId, How UAC works, UI Automation Security Overview.
- Web search service returned errors for additional queries; therefore no claim of exhaustive documentation review.
- `git diff --check`: PASS for current documentary changes (to be refreshed after any further edit).
- No product tests or Windows runtime gates were run.

Overall: points 1, 3–7 are documented as concrete design work but remain open pending choices and proof; point 2 is currently the critical `BLOCKED` feasibility gate. Goal stays `BLOCKED`, installation disabled, P0 `OPEN`.
