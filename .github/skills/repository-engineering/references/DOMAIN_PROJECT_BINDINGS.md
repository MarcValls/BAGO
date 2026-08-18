# DOMAIN PROJECT BINDINGS — repository.engineering

Status: PROPOSED
Active concrete bindings: none.

## Binding model

The relation between `repository.engineering` and projects is explicitly many-to-many.

A project may bind this domain for selected repository operations while also using other domains. This domain may serve many projects without transferring canon, state or evidence among them.

## Required binding record

project_id_or_class:
purpose:
transferable_context:
non_transferable_context:
authority:
activation:
deactivation:
handoff:

## Binding rules

- Binding does not make a project an instance, child or property of the domain.
- Binding does not make a repository the domain's property.
- The project retains its own canon, state and governance authority.
- The domain contributes only repository-engineering semantics/operations.
- Context transfer is minimum and explicit.
- A shared domain does not permit cross-project canon or state inheritance.
- The kernel retains final routing/activation authority.

## Test-project rule

Any project later selected to exercise DOMAIN CONFORMANCE TEST v1.2 is merely an application context bound for the test. It must remain independently identifiable and governable.
