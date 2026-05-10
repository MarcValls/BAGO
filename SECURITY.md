# Security Policy

## Scope

BAGO is a local-first framework. Its main attack surface is:

- local CLI execution,
- local state manipulation under `.bago/state/`,
- optional local/LAN HTTP and UDP services (`miniapp`, `peer`, discovery helpers).

By default, hardened HTTP services should bind to `127.0.0.1` unless explicitly overridden.

## Threat model (short)

1. **Miniapp server exposed to LAN**  
   Mitigation: default bind `127.0.0.1`, restricted CORS, optional token auth on mutating endpoints.

2. **`bago peer serve` exposed to LAN**  
   By design this can be network-visible when configured with non-localhost host; use only on trusted networks.

3. **`bago autonomous` / `bago auto` executing system actions**  
   Mitigation: explicit opt-in (`--yes`) and dry-run support where applicable.

4. **`bago install` modifying autorun/autostart behavior**  
   Mitigation: explicit unsafe flag (`--unsafe`) required.

5. **`bago secrets` scanning repository contents**  
   Read-only operation intended for leak detection; no mutation required.

## Reporting vulnerabilities

Please report vulnerabilities through **GitHub Security Advisories** (private reporting) for this repository:

- https://github.com/MarcValls/BAGO/security/advisories

If private reporting is unavailable in your context, open an issue with minimal public detail and request a private channel.

## Dependencies and supply chain

- Core runtime is stdlib-only.
- Optional or future third-party dependencies should be audited with `pip-audit`.

## What BAGO does NOT do

- It does not send telemetry by default.
- It does not perform network calls without an explicit command path that requires it.
- It does not sign blockchain transactions in miniapp claim flows; wallets sign user-side.
