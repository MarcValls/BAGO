# BAGO MSIX seed host

This is the native full-trust seed host. It loads the canonical Python authority
with Python.NET in the host process. Installation stays disabled until the
package-bound interaction capability and authenticated elevated helper contract
are implemented and reviewed.

`build-msix-bootstrap.ps1` requires an already prepared, candidate-bound runtime
payload; it does not build, stage over, or delete `releases/compiled`. Test
signing and deployment are separate explicit steps. A self-signed test package
is not a trusted release package.
