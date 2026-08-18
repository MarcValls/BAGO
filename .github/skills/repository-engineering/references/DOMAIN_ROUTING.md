# DOMAIN ROUTING — repository.engineering

Status: PROPOSED
Final routing authority: kernel.

## Positive signals

- inspect/audit/fix/refactor/patch/test/build/typecheck/lint a repository or codebase;
- determine repository baseline, branch, revision, diff or worktree state for an engineering operation;
- compare repository implementation with repository-local architecture/contracts;
- apply repository changes and prove what changed;
- verify a change with repository-declared checks;
- prepare rollback/containment of an attributable repository change;
- modify repository-local governance/canon with explicit mutation intent.

## Negative signals

- conceptual coding education with no repository object/state;
- generic writing or documentation unrelated to repository engineering;
- pure product/business planning;
- specialist security/legal/compliance judgment where repository state is not the primary product;
- kernel/domain architecture governance unless the current object is specifically the repository.engineering package and another design/governance mode has been selected.

## Ambiguous cases

- pasted source code without repository state: allow reference-only analysis; do not claim repository audit/verification.
- Git/GitHub education: remain outside unless a concrete repository operation/state matters.
- vulnerability/dependency issue: resolve repository evidence needed for handoff, but route specialist judgment to the appropriate domain when one exists.
- CI failure: activate if the task is to diagnose/fix repository implementation; handoff if failure belongs to infrastructure outside authorized repository scope.

## Activation preconditions

- kernel selects this domain;
- repository or repository artifact is identified enough to satisfy the requested product;
- required authority and capability are resolved before material effects.

## Deactivation

- requested product becomes non-repository-specific;
- required target is outside authorized repository scope;
- another domain becomes primary and only repository evidence/handoff is needed;
- unresolved critical authority/state/capability requires return to kernel.

## Handoff targets

- kernel;
- applicable project/repository governance authority;
- applicable specialist domain;
- runtime/operator able to supply a missing binding.

## Minimum repository-specific handoff extension

In addition to the kernel handoff payload, include when available:

- repository identity/root;
- baseline/revision/ref;
- dirty/pre-existing state relevant to attribution;
- affected paths/change set;
- checks executed and not executed;
- runtime capability missing or constrained;
- repository-canon source relevant to the pending operation.
