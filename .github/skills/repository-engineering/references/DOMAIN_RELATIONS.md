# DOMAIN RELATIONS — repository.engineering

Status: PROPOSED

## Concrete relations

None declared in v0.1.1.

No other domain id is assumed to exist merely because a related competence can be named conceptually.

## Relation model

When a relation is added, it must declare:

- source domain: `repository.engineering` or the actual origin;
- target domain id;
- reason;
- transferable repository context;
- non-transferable context;
- authority for the transfer;
- handoff mechanism.

## Transferable context by default candidate

Only when material to the receiving operation:

- repository identity/root;
- baseline/revision/ref;
- scoped paths/change set;
- repository source/evidence references;
- executed/not-executed verification checks;
- conflicts/unresolved facts;
- pending operation and next action.

## Non-transferable by association

- entire project history;
- unrelated project canon;
- unrelated repository secrets/credentials;
- domain canon of either side;
- memory not required for the handoff;
- authority not explicitly transferable.

A relation never creates canon inheritance.
