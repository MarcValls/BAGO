"""Materialize CRIT-BAGO-CAPABILITY-PRESERVATION-01 required artifacts."""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MATRIX = json.loads((HERE / "capability-matrix.json").read_text(encoding="utf-8"))
FREEZE = json.loads((HERE / "freeze-before.json").read_text(encoding="utf-8"))
PROBES = json.loads((HERE / "semantic-probes.json").read_text(encoding="utf-8"))

CLASS = {
    "C01":"EXTENDED","C02":"EXTENDED","C03":"EXTENDED","C04":"PRESERVED","C05":"REPLACED_EQUIVALENTLY","C06":"REPLACED_EQUIVALENTLY","C07":"EXTENDED","C08":"RESTRICTED_INTENTIONALLY","C09":"RESTRICTED_INTENTIONALLY","C10":"UNKNOWN","C11":"ACCIDENTALLY_LOST","C12":"REPLACED_NON_EQUIVALENTLY","C13":"UNKNOWN","C14":"EXTENDED","C15":"REPLACED_NON_EQUIVALENTLY","C16":"EXTENDED","C17":"EXTENDED","C18":"EXTENDED","C19":"PRESERVED","C20":"RESTRICTED_INTENTIONALLY","C21":"RESTRICTED_INTENTIONALLY","C22":"PRESERVED","C23":"EXTENDED","C24":"PRESERVED","C25":"REPLACED_NON_EQUIVALENTLY","C26":"REPLACED_NON_EQUIVALENTLY","C27":"UNKNOWN","C28":"RESTRICTED_INTENTIONALLY","C29":"REPLACED_EQUIVALENTLY","C30":"REPLACED_NON_EQUIVALENTLY","C31":"UNKNOWN","C32":"UNKNOWN","C33":"REPLACED_NON_EQUIVALENTLY","C34":"UNKNOWN","C35":"UNKNOWN","C36":"UNKNOWN","C37":"REMOVED_INTENTIONALLY","C38":"UNKNOWN","C39":"UNKNOWN",
}
INTRO = {"C01":"v4.0.0-mvp","C02":"v4.5.0","C03":"v4.5.0","C04":"v4.5.0","C05":"v4.5.0","C06":"v4.8.0","C07":"v4.9.0","C08":"v4.8.0","C09":"v4.8.0","C10":"v4.5.0","C11":"v4.5.0","C12":"v4.5.0","C13":"v4.5.0","C14":"v4.0.0-mvp","C15":"v4.0.0-mvp","C16":"v4.5.0","C17":"v4.8.0","C18":"v4.8.2","C19":"v4.9.0","C20":"v4.9.0","C21":"v4.8.0","C22":"v4.8.0","C23":"v4.8.0","C24":"v3.5.0","C25":"v4.5.0","C26":"v3.2-kernel","C27":"v4.5.0","C28":"v4.8.7","C29":"v4.9.0","C30":"v4.9.0","C31":"v3.5.0","C32":"v3.5.0","C33":"v3.5.0","C34":"v4.5.0","C35":"v4.5.0","C36":"v4.5.0","C37":"v4.5.0","C38":"v4.5.0","C39":"v4.5.0"}

def version(text):
    for x in ("v4.11.10","v4.11.0","v4.10.0","v4.9.0","v4.8.7","v4.8.2","v4.8.0","v4.5.0","v4.0.0-mvp","v3.5.0","v3.2-kernel"):
        if x in text: return x
    return "UNKNOWN"

def write(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

current=[]; historical=[]; preservation=[]
for r in MATRIX["capabilities"]:
    cid=r["id"]; cls=CLASS[cid]; src=r["current_source"].split(":",1)[0]
    status="IMPLEMENTED" if cls in {"PRESERVED","EXTENDED","RESTRICTED_INTENTIONALLY","REPLACED_EQUIVALENTLY"} else "PARTIAL" if cls in {"REPLACED_NON_EQUIVALENTLY","ACCIDENTALLY_LOST"} else "UNKNOWN"
    evidence=r["historical_evidence"]+[r["current_source"]]+r["test_paths"]
    current.append({"capability_id":cid,"name":r["capability"],"description_observable":r["comparison"],"owner_current":r["owner"],"modules_current":[src],"entrypoints_routes_current":r["route"],"effects_associated":"Owner/ruta identificados; material effect NOT_RUN.","authorization_required":"Según contrato del owner; runtime NOT_RUN.","preconditions":"Static reachability traced; live preconditions NOT_RUN.","evidence_receipt_expected":"Receipt/contract where owner requires it; live receipt NOT_RUN.","tests_current":r["test_paths"],"state":status,"evidence":r["evidence"],"confidence":"HIGH" if r["evidence"] in {"FUNCTION_BOUNDARY_REPRODUCED","EXPLICIT_BUG_FIX"} else "MEDIUM"})
    historical.append({"capability_id":cid,"name":r["capability"],"introduced_version":INTRO[cid],"last_known_full_version":version(" ".join(r["historical_evidence"])),"historical_owner":r["owner"],"historical_routes":r["route"],"historical_tests":r["test_paths"],"historical_evidence":r["historical_evidence"],"behavior":r["comparison"],"confidence":"MEDIUM" if r["intent"]=="NOT_ESTABLISHED" else "HIGH"})
    preservation.append({"capability_id":cid,"capability_name":r["capability"],"introduced_version":INTRO[cid],"last_known_full_version":version(" ".join(r["historical_evidence"])),"current_status":status,"classification":cls,"historical_owner":r["owner"],"current_owner":r["owner"],"historical_routes":r["route"],"current_routes":r["route"],"historical_tests":r["test_paths"],"current_tests":r["test_paths"],"restriction_reason":r["comparison"] if cls=="RESTRICTED_INTENTIONALLY" else "","replacement_capability_id":None,"evidence":evidence,"confidence":"HIGH" if r["evidence"] in {"FUNCTION_BOUNDARY_REPRODUCED","EXPLICIT_BUG_FIX"} else "MEDIUM","notes":r["intent"]+"; "+r["equivalence"]})

write("CAPABILITY_INVENTORY_CURRENT.json",{"schema":"bago.capability-inventory-current.v1","candidate_head":FREEZE["head"],"surface_sha256":FREEZE["surface_sha256"],"status":"FROZEN_STATIC_SURFACE","live_execution":"NOT_RUN","capabilities":current})
write("CAPABILITY_INVENTORY_HISTORICAL.json",{"schema":"bago.capability-inventory-historical.v1","candidate_head":FREEZE["head"],"source":"local tags/contracts/tests/commits","tags_inspected":55,"capabilities":historical})
write("CAPABILITY_PRESERVATION_MATRIX.json",{"schema":"bago.capability-preservation-matrix.v1","candidate_head":FREEZE["head"],"surface_sha256":FREEZE["surface_sha256"],"classifications":["PRESERVED","EXTENDED","RESTRICTED_INTENTIONALLY","REPLACED_EQUIVALENTLY","REPLACED_NON_EQUIVALENTLY","REMOVED_INTENTIONALLY","ACCIDENTALLY_LOST","UNKNOWN"],"records":preservation})

findings=[
 {"id":"CAP-LOSS-P1-001","capability_id":"C11","title":"Autopilot perdió límite histórico de 20 pasos","severity":"P1","classification":"ACCIDENTALLY_LOST","evidence":["v4.5.0 max_steps=20","semantic-probes current_25_steps=26 calls vs historical=21"],"impact":"El handler actual procesa todos los pasos; no hay decisión de retirada localizada.","verification":"Boundary probe reproducido; provider/runtime real NOT_RUN."},
 {"id":"CAP-LOSS-P1-002","capability_id":"C12","title":"Agent spawn/list/run/kill cruza dos registros","severity":"P1","classification":"REPLACED_NON_EQUIVALENTLY","evidence":["4aa0eb66 añade agent_kit list/run/describe/plan antes de spiral_agent spawn/kill/status","cmd_tools.py ramas actuales"],"impact":"La continuidad de identidad entre comandos no está demostrada.","verification":"Trace estático; flujo live NOT_RUN."},
 {"id":"CAP-LOSS-P2-001","capability_id":"C30","title":"Interpretation detail por ID devuelve colección","severity":"P2","classification":"REPLACED_NON_EQUIVALENTLY","evidence":["legacy_aliases.py redirige detail a history","handlers_interpret ignora ID; client espera InterpretationResult"],"impact":"Contrato cliente/API incoherente; callsite UI no encontrado.","verification":"Trace estático; HTTP/UI NOT_RUN."},
 {"id":"CAP-LOSS-P2-002","capability_id":"C27","title":"issues-gh parser sin dispatcher","severity":"P2","classification":"UNKNOWN","evidence":["parser lo declara; dispatcher lo omite; probe devuelve 0 y help","mismo defecto en v4.5"],"impact":"Defecto conservado, no pérdida nueva demostrada.","verification":"Boundary probe reproducido."},
 {"id":"CAP-LOSS-P2-003","capability_id":"C31","title":"RoleSpiralBuilder ausente del backend actual","severity":"P2","classification":"UNKNOWN","evidence":["v3.5 role_embedded + test_v35_features","símbolo ausente en backend rastreado; tags desconectados"],"impact":"Implementación exacta ausente; reemplazo conceptual sin resolver.","verification":"Source trace; equivalencia NOT_RUN."},
 {"id":"CAP-LOSS-P2-004","capability_id":"C32","title":"SignalMetrics band/channel/hz ausente","severity":"P2","classification":"UNKNOWN","evidence":["v3.5 prompt_router + tests","routing actual no demuestra equivalente"],"impact":"Preservación no certificable; no se prueba eliminación lineal.","verification":"Source trace; equivalencia NOT_RUN."},
]
write("EVIDENCE_INDEX.json",{"schema":"bago.capability-evidence-index.v1","candidate_head":FREEZE["head"],"surface_sha256":FREEZE["surface_sha256"],"commands":["collect.py freeze","collect.py collect","probe_semantics.py","collect.py check","finalize.py"],"executed":{"freeze":"PASS","collection":"EXECUTED static local tags","semantic_probes":"EXECUTED controlled boundary","freeze_check":"PASS","test_suites":"NOT_RUN","live_routes":"NOT_RUN","remote_fetch":"NOT_RUN"},"chain":"claim -> historical source -> current source -> inspection -> evidence -> comparison -> classification -> conclusion","findings":findings})

(HERE/"SEMANTIC_OVERWRITE_FINDINGS.md").write_text("# Semantic overwrite findings\n\nNo P0 loss is demonstrated.\n\n"+"\n".join(f"## {x['id']} · {x['title']}\n\nSeverity **{x['severity']}** · `{x['classification']}` · {x['impact']}\n\nEvidence: {'; '.join(x['evidence'])}\n\nVerification: {x['verification']}\n" for x in findings),encoding="utf-8")
(HERE/"CAPABILITY_PRESERVATION_GAPS.md").write_text("""# Capability preservation gaps

The findings justify five missing controls: a stable capability ledger; compatibility tests at capability level for autopilot, agent identity, interpretation-by-ID and parser/dispatcher reachability; replacement-equivalence tests for owner migrations; intentional-removal decision records for public interfaces; and a semantic diff gate comparing observable outcomes and authorization boundaries.

These are audit findings, not implementation work. They prevent route/module names from being mistaken for preserved behavior.
""",encoding="utf-8")

lineage=["# Capability lineage","",f"Freeze `{FREEZE['head']}` · surface `{FREEZE['surface_sha256']}`.","","The full records are in CAPABILITY_PRESERVATION_MATRIX.json. Early tags are not all ancestors of HEAD; divergent history cannot prove a deletion on the current branch.",""]
for r in preservation: lineage += [f"## {r['capability_id']} · {r['capability_name']}","",f"{r['introduced_version']} → {r['last_known_full_version']} → {r['current_status']} → **{r['classification']}**",f"Owner {r['historical_owner']} → {r['current_owner']}",f"Routes {r['historical_routes']} → {r['current_routes']}",f"Evidence: {'; '.join(r['evidence'])}",f"Notes: {r['notes']}",""]
(HERE/"CAPABILITY_LINEAGE.md").write_text("\n".join(lineage),encoding="utf-8")

report=f"""# CRIT-BAGO-CAPABILITY-PRESERVATION-01 report

Freeze: `{FREEZE['head']}` · `{FREEZE['surface_sha256']}`. The static current inventory has {len(current)} families. Local tags, contracts, source and test files were inspected; no live routes, providers, UI, external hosts or material effects were executed. Controlled probes did run at function boundaries.

BAGO has accumulated significant capabilities: session persistence/recovery, conversation state, governed writes, capability packages, scheduling/delegation, provider bridges and Node Control. The evolution is mixed. Several changes are intentional restrictions, while other transitions are non-equivalent or unresolved. Therefore route/module similarity cannot establish preservation.

The strongest confirmed preservation gap is the historical autopilot limit: v4.5.0 stopped after 20 steps; the current boundary probe processes 25. The current handler also marks non-empty model text as evidence and `done` without a material receipt. A second P1 finding is the agent registry split introduced by 4aa0eb66, where spawn/kill/status remain on spiral_agent while list/run/describe/plan use agent_kit. These need a compatibility decision before Framework/CLI/App extraction.

Intentional restrictions include filesystem writes behind ExecutionGateway, material plan execution requiring evidence/receipt, scheduled execution requiring delegation, and HTTP GitHub mutation returning 410 while process authorization is the alternate owner. Historical v3 prompt-cycle and SignalMetrics implementations, and several old CLI interfaces, remain UNKNOWN because their tags are divergent or their conceptual replacements are not demonstrated.

Architectural shifts are MIXED: governance, eligibility, AuthorizationBoundary, ExecutionGateway and WorldStateSnapshot add layers around preserved operations; PlanEngine/autopilot and provider routing also contain semantic changes that require capability-level tests.

Artifacts: CAPABILITY_INVENTORY_CURRENT.json, CAPABILITY_INVENTORY_HISTORICAL.json, CAPABILITY_PRESERVATION_MATRIX.json, CAPABILITY_LINEAGE.md, SEMANTIC_OVERWRITE_FINDINGS.md, CAPABILITY_PRESERVATION_GAPS.md, EVIDENCE_INDEX.json.

Verdict is `PASS WITH FINDINGS` only as a scoped audit result with open P1 preservation findings; a release gate requiring no unresolved P1 must stop at `NO GO`.
"""
(HERE/"CRIT-BAGO-CAPABILITY-PRESERVATION-01_REPORT.md").write_text(report,encoding="utf-8")
print(json.dumps({"capabilities":len(preservation),"findings":len(findings),"head":FREEZE["head"]}))
