# Protocol decision block — same-user host integrity

Status: `BLOCKED` / read-only decision; no transport selected and no implementation started.
Goal: `CRIT-HOST-HELPER-IPC-NOOP-20260930-SUCCESSOR`
Candidate: HEAD `b10178bf8a13d0035079e989e46c36760dbd2a46`, branch `fix/spbe-runtime-fix1-20260927`, fingerprint before this report `f177e91d78981f819f160d88dcc57d4cc048275f14ea7325ac2e71fa7e87510a`.

## User authorization and action boundary

The user has now explicitly authorized implementation. This supersedes the preparation-only authorization recorded when `goal.md` was created, but it does not authorize a no-op test build/sign/activation/UAC run or clean-machine material installation. The immutable goal remains unchanged; the status records the later authorization. This block follows the goal's required read-only protocol-decision step before implementation.

No product files were edited. No tests, builds, signing, helper/process launches, UAC prompts, package activations, or material effects were performed.

## Evidence observed

- `bootstrap/msix-host/AppxManifest.xml` declares `runFullTrust`; its app is a full-trust Win32 process.
- `bootstrap/msix-host/Program.cs` verifies its own package root, manifest and publisher policy, then loads Python.NET and canonical authority in-process. It has no IPC implementation or process hardening policy.
- `bootstrap/msix-host/BootstrapForm.cs` keeps installation disabled.
- The production adapter `backend/.bago/core/execution_adapters/system_install.py` writes the consumed request/authorization proof to a user-state JSON ticket, then starts PowerShell with command-line data. `backend/install-v4.ps1` reads the ticket/ledger and self-elevates with `Start-Process -Verb RunAs`. The host does not currently retain the elevated child process handle.
- The existing proposal in `.bago/runtime/HOST_HELPER_IPC_DESIGN_20260930.md` assumes a trusted host and explicitly lists host injection/handle duplication as unresolved.
- A fresh-context reviewer evaluated the existing helper, a dedicated signed native helper, and other local IPC approaches. Verdict: `BLOCKED`; none protects a compromised host's in-memory authorization decision.

## Candidate assessment

| Candidate | Useful property | Blocking limitation |
|---|---|---|
| Pipe with current PowerShell helper | OS can report pipe peer PID; DACL, first-instance and remote rejection can constrain connections. | Current launch is adapter `Popen` -> PowerShell -> self-elevation, so the host does not own/retain the elevated process handle. The `powershell.exe` image does not authenticate the `.ps1`; the script/ticket path remains mutable unless bound to protected package content. It does not protect host memory from same-user injection. |
| Dedicated signed native helper in the MSIX plus a pipe | Package integrity/signature can bind the helper executable and avoid PowerShell script identity ambiguity. A launch handle can potentially be bound to the pipe PID. | Requires a different launch/package design and actual Windows proof. It still trusts the host to create the request and enforce the consumed Permit; if that host is subverted, authenticated IPC faithfully transports attacker-controlled authority. |
| AppService, COM, RPC, loopback, scheduled task | May supply alternate broker/transport semantics. | No candidate has been shown to keep the existing single Boundary/Gateway/owner while authenticating the integrity of the host against its same-user attacker. A persistent privileged broker/task also changes the one-shot owner/lifecycle contract. |

Transport authentication and host decision integrity are separate requirements. Authenticating a PID, package identity, publisher, or signed helper cannot prove that an uncompromised copy of the host's authorization logic produced the request.

## Windows trust facts and boundaries

1. Microsoft documents that full-trust packaged desktop apps run at medium integrity; the current `runFullTrust` host is not thereby isolated from other medium-integrity processes. Source: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/app-capability-declarations
2. Process access is checked against the process object's DACL; default process DACLs derive from the creator token, and rights include `PROCESS_VM_WRITE`, `PROCESS_VM_OPERATION`, `PROCESS_CREATE_THREAD`, and `PROCESS_DUP_HANDLE`. The current host does not set or verify a restrictive self-DACL. Source: https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights
3. Windows integrity/UIPI restrictions are across integrity levels; the cited UIAccess documentation says same-integrity UIPI does not isolate applications, and `uiAccess=true` is intended for accessibility applications (and is not an option for UWP apps). BAGO is not an assistive-technology product, so UIAccess is not an adopted mitigation. Sources: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview and https://learn.microsoft.com/en-us/windows/win32/secauthz/mandatory-integrity-control
4. `SetProcessMitigationPolicy` offers mitigations such as dynamic-code and image-signature policies. Those can reduce attack surface but the documentation does not establish that they prevent another same-integrity process from obtaining process handles or corrupting authorization data. Do not treat these mitigations as proof of host isolation. Source: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setprocessmitigationpolicy
5. Protected App / protected-process packaging is a restricted Store capability whose approval and publisher eligibility are not established for BAGO. It is not assumed available. Source: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/app-capability-declarations

## Finding / stop condition

**Rule:** successor goal requires peer authentication and explicit handling of same-user process injection/handle duplication; one authority chain must remain trustworthy across elevation.

**Observed:** current host is medium-integrity full trust, has no established restrictive process DACL or pre-start isolation, and holds the Boundary/Gateway decision in-process. Every proposed IPC protocol ultimately trusts that process to send the exact authorized request.

**Impact:** If an attacker can alter the host's decision state or invoke the trusted host as a deputy, a named pipe or other transport may authenticate the *right process* while accepting a request produced by compromised logic. No IPC-only patch can close this trust gap. No evidence currently proves the required host isolation.

**Classification:** `BLOCKED` before transport selection and implementation. This does not assert that the gap is impossible to close; it says the current architecture has no proven isolation mechanism.

## Minimum next design block (read-only until it passes)

1. Prove whether a restrictive process-object DACL using an explicit `OWNER RIGHTS` ACE can be applied early enough to prevent same-user medium peers from acquiring write/operation/thread/duplicate-handle rights, without breaking OS launch, debugging policy, package activation, or the helper's query-only identity checks. Analyze and test the process-start race before relying on this. Do not add the DACL in production as an experiment.
2. Determine whether any BAGO-eligible, supported OS launch configuration establishes a higher integrity or otherwise protected host boundary. UIAccess is not accepted as an application hardening shortcut; protected-process capability/publisher requirements are unestablished.
3. If neither can be proved, present a successor architecture decision: move native intent/Permit consumption and the existing Gateway into an OS-isolated broker/secure context, or narrow the guarantee only with explicit user/repository approval and independent security review. That is an authority-boundary change, not a pipe implementation detail.
4. Only after the host trust boundary is independently accepted, select a dedicated signed native helper plus one-shot IPC, specify process-handle/PID/package/publisher verification, then implement. The actual no-op Windows UAC test still needs its separately explicit build/sign/activation authorization; clean-machine material install needs another separate authorization.

## Decision

## Fresh host-isolation review (read-only)

A fresh-context reviewer evaluated whether the host trust gap can be closed without changing the sole in-process authority chain. Verdict: **BLOCKED; no proofable in-scope implementation**.

- A process DACL can be supplied at creation by APIs such as `CreateProcess`, and `OWNER RIGHTS` (`S-1-3-4`) can constrain implicit owner access. But MSIX full-trust activation is performed by the OS activation path, not an app-controlled `CreateProcess` call. The host can only harden its own process after creation, leaving a startup race before the restriction is applied. No supported MSIX manifest/activation option was found for a custom initial process DACL or suspended start.
- `SetProcessMitigationPolicy` does not set the process DACL or prevent process rights already granted to another process.
- `uiAccess` is restricted to assistive-technology scenarios and does not solve in-process authorization integrity. BAGO is not eligible.
- AppContainer/broker isolation is a plausible stronger OS boundary, but moving the current sole Boundary/Permit/Gateway authority into a broker would be an explicit authority-boundary redesign requiring approval and review.

Microsoft Learn references consulted:
- [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw) — initial process security descriptor when the caller creates the process.
- [Process Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights) — process DACL access checks and VM/thread/duplicate-handle rights.
- [Well-Known SID Structures](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-dtyp/81d92bba-d22b-4a8c-908a-554ab29148ab) — OWNER RIGHTS SID semantics.
- [UI Automation Security Overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview) — UIAccess eligibility and constraints.
- [SetProcessMitigationPolicy](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setprocessmitigationpolicy) — process mitigations.

The independent reviewer found no basis to pass this gate. These mitigations must not be represented as proof against same-user injection.

## Architecture decision — selected direction, review pending

**Selected direction: redesign the authority boundary around an OS-isolated broker.** Reject narrowing the same-user threat guarantee: same-user medium-integrity injection remains in scope, and the user has not approved weakening that guarantee.

This is an architecture direction for independent review, **not** a protocol selection or authorization to implement the broker. No Windows service model, broker identity, IPC transport, package lifecycle, or deployment mechanism is yet approved.

The proposal's invariants are:

1. The broker—not the MSIX UI host—owns the one canonical `AuthorizationBoundary → direct user intent → Permit → ExecutionGateway → existing effect owner` chain. The broker consumes the Permit; the helper/transport endpoint never issues one.
2. Host messages are untrusted operation proposals, never authorization or Permit proof. The broker independently renders the operation and exact target for direct user confirmation before it constructs/consumes authorization.
3. Existing material-effect owners remain unique. They move behind or execute within the broker only if each owner remains the sole registered materializer; do not add a parallel installer owner.
4. The broker uses an OS-enforced identity/isolation boundary against same-user medium-integrity peers, least privilege, and authenticated IPC. A named pipe is only a transport candidate; its ACL/peer identity/lifecycle need separate proof.
5. Broker install, update, recovery, and shutdown must fail closed and must not accept user-writable executable/script/ticket authority. Admin credentials are never persisted or supplied to the host.
6. If independent review cannot show that a supported Windows service/broker can enforce this boundary while preserving direct user intent and the existing unique owner, the result remains `BLOCKED`; do not silently fall back to a narrower guarantee.

Independent review completed: **`PASS_FOR_DETAILED_DESIGN` (direction-level only)**. The reviewer found the broker direction coherent with one authority chain and the current threat model, but explicitly did not approve a transport, concrete broker, protocol, or implementation. Detailed design may now proceed read-only. Protocol selection and implementation remain blocked until the critical design findings below have supported answers and a new independent review.

Critical design findings from the reviewer: (1) choose a service identity/token/integrity level/process DACL that resists same-user process access; (2) define mutual IPC peer/package/process-instance authentication; (3) prove a broker-owned direct-intent UI that cannot be spoofed or driven by the compromised host; (4) specify UAC and alternate-admin behavior; (5) establish signed install/update/recovery and protected binary locations; (6) prevent deputy abuse/DoS/replay; (7) place each existing effect owner without duplication; (8) bind host and broker to release/publisher identity; and (9) eliminate residual host influence over authorization. The reviewer also cautions that Windows service session-0 UI and running Python.NET in a service are high-risk feasibility questions.

The user's prior implementation authorization does not authorize implementing this newly selected authority-boundary redesign, service installation, build/sign/activation, UAC testing, or material installation. Keep those separate gates intact.

Keep installation disabled, the known user-writable ticket path unenabled, the successor goal `BLOCKED`, and bootstrap P0 `OPEN`. Build/sign/activation/UAC and clean-machine material installation remain separate authorization gates.