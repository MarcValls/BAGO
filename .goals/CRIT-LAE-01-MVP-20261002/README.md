# CRIT-LAE-01 — isolated MVP candidate

This directory is an isolated candidate implementation of the v0.9-FIX8
contract core. It is not imported by BAGO runtime and has no filesystem,
subprocess, network, authorization, or persistence authority.

The reference implementation covers LAE-01..LAE-07: immutable root/layer
identity, exact parent and digest binding, stale rejection, explicit rebase,
lineage and deterministic snapshot materialization, receipts, idempotent apply,
and failure without HEAD advancement.

Run from this directory:

```powershell
python -m unittest -v
```
