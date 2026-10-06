# Backend boundary graph audit — 2026-10-06

Scope: the HTML graph and its JSON inventory; source tracing of the displayed routes. This is not backend certification or a global sink audit.

Repository HEAD: `aec40891271310281a165214ed0fb5da4733c029`; dirty worktree.

## Baseline

- HTML SHA-256: `02aa9fc630c2296a0db82b6ce0074fed69b9baeb634a3f9b7a3e32321c62ebaa`.
- JSON SHA-256: `1bab80b5f7d129e8fa2cf1f0de278bcb45de6a51a1656a6b05bde1a1eab45bd8`.
- Primary review: required edits to relation semantics, evidence scope and omitted owners.
- Independent architecture critic: `REQUIRES_EDIT`; read-only, no backend tests run.

## Independent findings passed to the editor

1. Evidence score 3 contradicts a rubric requiring no known material gap; ownership remains pending.
2. Historical focused test counts have no retained exact-candidate receipt in the graph sidecar; no current validation may be inferred. Strict-runtime exit-code reports conflict.
3. Direct ClaimLedger reads are proved; a canonical requirement to use the plan-child filesystem.read adapter is not proved. Green routes must remain hypotheses.
4. Gateway-to-AuthorizationBoundary consumption is missing from the displayed authority path.
5. The plan route omits preparation, PlanEngine lookup/callback, ExecutionClaimStore and ingress guards.
6. HTTP, dispatch, data binding, registry registration and execution are visually conflated; edges need stable identities, types and source references.
7. The bridge-to-api_state relation is not a bidirectional call. Manager injection and standalone construction are distinct.
8. Existing paths cross other paths or traverse unrelated nodes.

## Authorized edit and acceptance criteria

The user requests an upper lateral-to-lower central funnel layout, with linear descent only where source behavior supports it. Branches and nested execution must remain explicit. Repeated visual instances of one source file must be distinguished from unique source files.

- Source-backed real edges carry IDs, types, symbols, line ranges and source hashes.
- Missing/proposed green dashed edges are separate from real edges and labelled hypotheses where unresolved.
- Red identifies a pending direct-read boundary without falsely certifying a violation.
- Gateway authority consumption, plan adapter, PlanEngine callbacks and nested child dispatch are represented.
- Selected routes can be followed to a concrete result/HTTP response.
- HTML and JSON counts agree; evidence scope and historical observations are explicit.
- Repository production sources remain untouched by this task.
- A fresh read-only review follows editing; closure is bound to final graph artifact hashes.

## First edited candidate — independent re-audit

Frozen HTML: `26d225546961a015d7747f0706d2bbdc9427c017ae38b6125aef1d9ed63337df`.
Frozen JSON: `fd01da2427c1b1e2bf67440b753ba5476789651cb28dc91f19393734a7d05d7e`.
Frozen renderer: `5d5c132355c8f7175509fb218e3b7fb70d0013ac8653633fea35f803fd967186`.

Independent final reviewer verdict: `FAIL` for this scoped graph candidate.

- The Plan selector omits dispatcher-to-jobs E05, leaving a disconnected route.
- E49 traverses unrelated node boxes in hypothesis and inventory views.
- Constructor-to-ledger E49 is incorrectly attributed to direct reads; constructor is inert. The real `.latest()` and `.get()` causal calls need distinct edges.
- A forced Gateway instance appears without selected connections in non-Gateway paths.

Executed checks: source inventory/hash/excerpt checks PASS; JavaScript parsing and Node DOM/SVG evaluation PASS as execution checks; geometry/route acceptance FAIL on the findings above; scoped diff whitespace check PASS. Browser rendering NOT_RUN because CUA has no connected browser. Backend tests/global scans NOT_RUN for this documentary edit.

The user subsequently requested fewer crossings. The editor is authorized to replace global coordinates/shared lanes with route-specific layouts and explicit visual phases. This first edited candidate is not certified.

## Final review

Corrective editor candidate v2:

- HTML: `fa3d0c99daca235d8b8eb53f704a6780dd7bb1f590048bf7ee75c39aa8d918a4`.
- JSON: `ba125c621d53ee1e94e00576ebb421f97f3e0bdf84d2f9c267b9fcb1d2fad5a3`.
- Renderer: `8a7a381e23ea11b048b0caf91cb80685e67144584e9dbfa65647895920031c51`.

Primary reviewer executed `python scripts/render_backend_boundary_map.py --check`: PASS for 12 connected local views, 0 node-box traversals and 0 edge intersections/overlaps using exact generated segments. Actual inline JavaScript was executed using Node and a minimal DOM for all 12 selections: PASS. Embedded inventory/source checks PASS: 25 unique files, 53 observed relations and 2 hypotheses. Scoped `git diff --check`: PASS. Artifact hashes match the editor freeze.

The corrected graph separates inert ClaimLedger construction from the causal latest/get reads, includes the plan dispatch edge and the GET ingress edge, and has no forced isolated Gateway. Phase instances and semantic layers are explicit. Browser visual rendering remains NOT_RUN; this structural check is not an actual browser screenshot or product validation.

Independent v2 verdict: `FAIL` for route-level semantic coherence, despite structural checks passing. The claims-list and individual-claim views combine the dispatch edge for `/evidence/latest` with other handler methods. The providers view combines GET `/providers` dispatch with POST `/providers/configure` execution. The editor must add endpoint-specific dispatch and matching serialization edges, then assert method/path/handler coherence in each relevant view.

Independent positive verification: all four earlier findings closed; actual emitted DOM/SVG boxes, edge IDs, paths, table rows, colors and dashes match the checked model across 12 views. Plan response serialization is correctly source-ordered after execution; the lateral position is explicitly not chronology.

## Final candidate v3 — independent PASS

Final artifact identities, checked before and after independent review:

- HTML: `10ba6552bf631a3e009b9b5f3cfb7a03503a327af1b4a939025020d14c16f97a`.
- JSON: `29882515b34bc72d84e97ff2f1caa3c04580ccedc6971e3516ca4e1f8215c4d7`.
- Renderer: `4c4e3d5dce8c017974b864e29b57f3c5a14a2f0a97f8810562c2eda9130994f1`.

Independent verdict: **PASS**, scoped to the selected graph, source correspondence and static JavaScript/SVG rendering. Primary reviewer repeated the checker and source/artifact identity checks: PASS.

Executed acceptance evidence:

- `python scripts/render_backend_boundary_map.py --check`: all 12 views connected, endpoint/method/AST caller coherent, 0 node-box traversals and 0 edge intersections/overlaps.
- Actual inline JavaScript executed using Node and a minimal DOM for all 12 selections.
- Independent comparison: emitted SVG node boxes, edge IDs, exact path coordinates, table IDs, colors and hypothesis dashes match the checked embedded view model.
- Inventory: 25 unique source files, 58 observed relations and 2 hypotheses; source hashes/excerpts/types/statuses consistent.
- Endpoint fixes: E54/E56 claims-list, E55/E57 individual claim, E58/E27 provider configuration; no mixed GET/POST or handler paths in those views.
- Earlier findings closed: E05 plan dispatch present, no forced isolated Gateway, inert constructor observed blue, causal latest/get/read edges OWNER_PENDING, hypotheses explicitly noncanonical.
- Scoped `git diff --check`: PASS. Audited artifact hashes unchanged throughout independent review.

Browser/pixel inspection: **NOT_RUN**, CUA browser unavailable. Backend suites/global inventories: **NOT_RUN** for this documentary task. Historical 256-test and 538-unbound observations remain reported history, not freshly certified results. No production backend files were changed by this task. This scoped PASS does not certify complete architecture coverage, a globally frozen backend or VALIDATED product state.
