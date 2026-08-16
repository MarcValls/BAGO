# DOMAIN MEMORY — repository.engineering

Status: PROPOSED

This file specializes repository-related memory candidates without replacing the kernel memory policy.

## Allowed candidates

- confirmed stable naming conventions;
- recurring repository workflow preferences that are not authoritative state;
- stable relationships between repository and project identifiers for routing, when explicitly confirmed;
- preferred non-critical presentation/reporting conventions for repository work.

## Forbidden as memory-only truth

- current branch/ref/HEAD;
- dirty/clean worktree status;
- exact dependency/tool versions;
- current build/test/CI outcome;
- repository/domain canon;
- current mutation authority;
- evidence that a write, command, commit, push, merge or rollback occurred;
- conformance result;
- unresolved assumptions promoted to fact.

## Requires source refresh

- repository state before material write or verification;
- repository canonical requirements before an audit/change that depends on them;
- mutation authority before repository governance change;
- runtime binding availability before execution;
- project-domain binding when it affects authority or context transfer.

## Refresh/expiry

Any material repository change may invalidate cached repository-state context for affected scope. Memory may guide what to look up, but does not replace the lookup when current accuracy is material.
