# DOMAIN RUNTIME BINDINGS — repository.engineering

Status: PROPOSED
Concrete universal bindings: none.

The domain declares semantic capabilities but does not assume tool names or availability. Each execution resolves bindings from the active runtime.

## Binding registry template

semantic_operation:
binding_name:
dependency:
availability_condition:
executable_condition:
scope/limitations:
verification_evidence:
fallback:

## Semantic operations that may require bindings

- repo.read
- repo.enumerate
- repo.write
- vcs.inspect
- vcs.mutate
- command.execute
- remote.check.read

## Availability rule

A named tool, connector, CLI or API is not AVAILABLE merely because it appears in documentation or memory. Availability requires current runtime exposure or equivalent direct evidence.

## Execution rule

AVAILABLE does not automatically mean EXECUTABLE for a particular operation. Repository scope, permissions, command/effect authorization and preconditions must also resolve.

## Fallback rule

When a material binding is missing:

- prepare the product that can be constructed without execution;
- narrow the verification scope if that remains useful;
- or return BLOCKED/handoff.

Do not simulate repository execution.

## v0.1.1 state

No concrete runtime binding is recorded in the manifest. `vcs.inspect` covers revision/ref/status/diff inspection rather than declaring a separate diff capability. This is intentional at design stage and must be resolved before the later real integration/conformance exercise that depends on execution.
