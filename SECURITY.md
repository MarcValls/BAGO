# Security Policy

## Scope

BAGO is a local-first framework. Its main attack surface is:

- local CLI execution,
- local state manipulation under `.bago/state/`,
- optional local/LAN HTTP and UDP services (`miniapp`, `peer`, discovery helpers).

By default, hardened HTTP services should bind to `127.0.0.1` unless explicitly overridden.

## CI-enforced local service guarantees

Static policy tests in `tests/test_security.py` fail when any of these guarantees drift:

- a Python HTTP service implemented with `HTTPServer` or `socketserver.TCPServer` appears without being added to the documented inventory below;
- a local HTTP service defaults to `0.0.0.0` without a documented exception;
- a mutating HTTP handler uses wildcard CORS (`Access-Control-Allow-Origin: *`) instead of an explicit origin allowlist or equivalent token-gated exception.

| Command / entrypoint | Source | Default bind | Enforced notes |
|---|---|---|---|
| `python3 .bago/tools/bago_miniapp_server.py` | `.bago/tools/bago_miniapp_server.py` | `127.0.0.1` | Mutating routes must not use wildcard CORS; uses an explicit same-host origin and mandatory token auth on mutating endpoints when exposed beyond localhost (`--token` required if `--host` is not local). |
| `bago peer serve` | `.bago/tools/peer_link.py` | `127.0.0.1` | Opt-in LAN via `--host`; CI requires the localhost default to remain and keeps this command documented as an intentional LAN-capable exception. |
| `python3 .bago/tools/live_dashboard.py` | `.bago/tools/live_dashboard.py` | `localhost` | Read-only local dashboard; not allowed to drift to wildcard bind. |
| `bago telemetry --web` | `.bago/tools/bago_telemetry_web.py` | `127.0.0.1` | Read-only local telemetry UI; not allowed to drift to wildcard bind. |
| `http-discover` | `.bago/tools/http_discover.py` | `0.0.0.0` | Legacy experimental LAN exception for discovery-only workflows; intentional and documented so CI can distinguish it from unsafe defaults elsewhere. |

Documented exception mechanism:

- only commands listed in the inventory above may be treated as intentional LAN-visible exceptions;
- new exceptions must be added to both `SECURITY.md` and `tests/test_security.py` in the same change;
- if an exception ever needs wildcard CORS on a mutating route, the change must also add an explicit allowlist/token gate and the corresponding static test coverage.

## Threat model (short)

1. **Miniapp server exposed to LAN**  
   Mitigation: default bind `127.0.0.1`, restricted CORS, mandatory token auth on mutating endpoints when `--host` is not a local address (startup aborts if no token is provided).

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
