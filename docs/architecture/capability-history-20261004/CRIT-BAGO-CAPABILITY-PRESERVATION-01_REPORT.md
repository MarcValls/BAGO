# CRIT-BAGO-CAPABILITY-PRESERVATION-01 report

Freeze: `b9b2eda8f21be16f5ade510b5f069abe09ae5387` · `e5558324b436c03cb6f8470522951b05ff468fd673cfdbdde433c6f557fcf908`. The static current inventory has 39 families. Local tags, contracts, source and test files were inspected; no live routes, providers, UI, external hosts or material effects were executed. Controlled probes did run at function boundaries.

BAGO has accumulated significant capabilities: session persistence/recovery, conversation state, governed writes, capability packages, scheduling/delegation, provider bridges and Node Control. The evolution is mixed. Several changes are intentional restrictions, while other transitions are non-equivalent or unresolved. Therefore route/module similarity cannot establish preservation.

The strongest confirmed preservation gap is the historical autopilot limit: v4.5.0 stopped after 20 steps; the current boundary probe processes 25. The current handler also marks non-empty model text as evidence and `done` without a material receipt. A second P1 finding is the agent registry split introduced by 4aa0eb66, where spawn/kill/status remain on spiral_agent while list/run/describe/plan use agent_kit. These need a compatibility decision before Framework/CLI/App extraction.

Intentional restrictions include filesystem writes behind ExecutionGateway, material plan execution requiring evidence/receipt, scheduled execution requiring delegation, and HTTP GitHub mutation returning 410 while process authorization is the alternate owner. Historical v3 prompt-cycle and SignalMetrics implementations, and several old CLI interfaces, remain UNKNOWN because their tags are divergent or their conceptual replacements are not demonstrated.

Architectural shifts are MIXED: governance, eligibility, AuthorizationBoundary, ExecutionGateway and WorldStateSnapshot add layers around preserved operations; PlanEngine/autopilot and provider routing also contain semantic changes that require capability-level tests.

Artifacts: CAPABILITY_INVENTORY_CURRENT.json, CAPABILITY_INVENTORY_HISTORICAL.json, CAPABILITY_PRESERVATION_MATRIX.json, CAPABILITY_LINEAGE.md, SEMANTIC_OVERWRITE_FINDINGS.md, CAPABILITY_PRESERVATION_GAPS.md, EVIDENCE_INDEX.json.

The audit verdict is `FAIL` under the supplied gate: one P1 `ACCIDENTALLY_LOST` behavior and one P1 `REPLACED_NON_EQUIVALENTLY` transition remain without an accepted decision. This is not a P0 failure and does not prove that the whole product regressed.

VERDICT:
FAIL

CAPABILITY COUNTS:
CURRENT: 39
HISTORICAL: 39
PRESERVED: 4
EXTENDED: 9
RESTRICTED_INTENTIONALLY: 5
REPLACED_EQUIVALENTLY: 3
REPLACED_NON_EQUIVALENTLY: 6
REMOVED_INTENTIONALLY: 1
ACCIDENTALLY_LOST: 1
UNKNOWN: 10

FINDINGS:
P0=0
P1=2
P2=4

MOST IMPORTANT LOSSES: C11 autopilot 20-step guard; C12 agent identity continuity across spawn/list/run/kill

MOST IMPORTANT PRESERVED CAPABILITIES: session persistence/recovery; chat and streaming; Node Control; capability packages; RL shadow boundary; provider bridges

SEMANTIC OVERWRITES:
6 findings: autopilot evidence/limit, agent registry split, interpretation detail alias, issues-gh parser/dispatcher mismatch, historical cancel-to-interpret alias (corrected), and GitHub mutation facade restriction.

NEXT EXACT ACTION:
Resolve and test C11 and C12 at capability level before extracting or moving any Framework, CLI, or App owner.
