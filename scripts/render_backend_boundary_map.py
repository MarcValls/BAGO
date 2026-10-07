"""Rebuild the selected source-backed boundary graph; --check checks evidence."""
from pathlib import Path
import hashlib, json, re, sys, math, shutil, subprocess, ast

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/architecture/evidence/backend-territory-maturity-20261006.json'
HTML = ROOT / 'docs/architecture/BACKEND_BOUNDARY_MAP_20261006.html'

FILES = {
 'client':'frontend/src/api/client.ts', 'bridge':'backend/.bago/api/bridge.py',
 'auth':'backend/.bago/api/api_auth.py', 'dispatch':'backend/.bago/api/api_dispatch.py',
 'jobs':'backend/.bago/api/handlers_jobs.py', 'session':'backend/.bago/api/handlers_session.py',
 'context':'backend/.bago/api/handlers_context_attach.py', 'providers':'backend/.bago/api/handlers_providers.py',
 'evidence':'backend/.bago/api/handlers_evidence.py', 'state':'backend/.bago/api/api_state.py',
 'manager':'backend/.bago/core/session_manager.py', 'store':'backend/.bago/core/context_store.py',
 'boundary':'backend/.bago/core/authorization_boundary.py', 'gateway':'backend/.bago/core/execution_gateway.py',
 'registry':'backend/.bago/core/effect_registry.py', 'contract':'backend/.bago/contracts/bago.effect-registry.v1.json',
 'planadapter':'backend/.bago/core/execution_adapters/plan.py', 'contextadapter':'backend/.bago/core/execution_adapters/context.py',
 'filesystem':'backend/.bago/core/execution_adapters/filesystem.py', 'pipeline':'backend/.bago/core/governed_work_pipeline.py',
 'engine':'backend/.bago/core/plan_engine.py', 'claims':'backend/.bago/core/execution_claims.py',
 'ledger':'backend/bago_core/claim_storage.py', 'sink':'backend/.bago/core/filesystem_effects.py', 'response':'backend/.bago/api/api_serializers.py',
}

def digest(path): return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
def build():
 d=json.loads(DATA.read_text(encoding='utf-8'))
 # Historical reports lack candidate-bound command logs. Preserve values without promoting them.
 for run in d['focused_test_runs']: run['evidence_status']='HISTORICAL_REPORTED_NOT_REVERIFIED'; run['candidate_binding']='MISSING'
 d['effect_sink_gates']['evidence_status']='HISTORICAL_REPORTED_NOT_REVERIFIED'
 runtime=d['effect_sink_gates']['strict_runtime']
 if runtime.get('reported_exit_code') is None:
  # Original map recorded 1; preserve this historical report, not a fresh gate.
  runtime['reported_exit_code']=runtime.get('exit_code') if runtime.get('exit_code') is not None else 1
 d['effect_sink_gates']['strict_runtime'].update(evidence_status='CONFLICTED',exit_code=None,conflict='Earlier map reports exit 1; critic found receipt exit 2. No fresh gate executed; exact exit is unresolved.')
 d['route_contract']['evidence_status']='HISTORICAL_REPORTED_NOT_REVERIFIED'
 d['rubric']['scale']='ORDINAL 0-4; not a ratio, percentage of quality, completeness or runtime coverage'
 d['rubric']['3']='Code and explicit contract plus fresh bounded checks with source identities; unavailable from historical test counts alone.'
 for score in d['scores']:
  score['previous_reported_score']=score.get('previous_reported_score',score['score'])
  if score['score']==3: score['score']=2
  score['assessment_status']='SOURCE_CONTRACT_ONLY; historical test claims are not current validation'
 d['candidate']['note']='Local selected-source trace only. Dirty checkout; no fresh full candidate-bound gates or backend freeze claim.'
 edges=[]
 def edge(a,b,kind,symbol,needle=None,source=None,status='OBSERVED',note='',occurrence=1):
  path=FILES[source or a]; lines=(ROOT/path).read_text(encoding='utf-8').splitlines(); needle=needle or symbol
  matches=[i+1 for i,line in enumerate(lines) if needle in line]
  if not matches: raise ValueError((a,b,needle,path))
  line=matches[occurrence-1]
  edges.append(dict(id=f'E{len(edges)+1:02}',from_node=a,to_node=b,type=kind,symbol=symbol,status=status,note=note,source=dict(path=path,line_start=line,line_end=line,sha256=digest(path),excerpt=lines[line-1].strip())))
 edge('client','bridge','TRANSPORT','fetch','fetch(')
 edge('bridge','auth','AUTHORIZE','BagoAuthMixin._origin_allowed_for_mutation','if not self._origin_allowed_for_mutation()',note='POST origin guard before dispatch; GET has its own token check.',occurrence=3)
 edge('bridge','auth','AUTHORIZE','BagoAuthMixin._check_auth','if not self._check_auth()',occurrence=4)
 edge('bridge','dispatch','ROUTE','do_POST.resolve_post','matched, call = resolve_post')
 for target,needle in [('jobs','handle_plans_execute'),('session','handlers_session'),('context','handlers_context_attach'),('providers','handlers_providers'),('evidence','handlers_evidence')]:
  edge('dispatch',target,'ROUTE','resolve_get/resolve_post: '+needle,needle)
 for a in ['jobs','session','context','providers','evidence']: edge(a,'state','LOOKUP','get_mgr','get_mgr(')
 edge('bridge','manager','BIND','BagoAPIHandler.session_mgr','BagoAPIHandler.session_mgr = self.session_mgr',note='Inject existing manager; does not construct it here.')
 edge('bridge','manager','CONSTRUCT','main.SessionManager','mgr = SessionManager(provider=args.provider',note='Separate bootstrap main, not request dispatch.')
 edge('manager','store','CONSTRUCT','SessionManager.__init__.ContextStore','self.store = ContextStore')
 edge('manager','engine','CONSTRUCT','SessionManager.__init__.PlanEngine','self.plan_engine = PlanEngine')
 edge('jobs','engine','LOOKUP','handle_plans_execute.get_plan','plan = engine.get_plan',occurrence=2)
 edge('jobs','pipeline','PREPARE','_plan_execution_request.plan_execution_target','target=plan_execution_target(plan)')
 edge('jobs','boundary','AUTHORIZE','handle_plans_execute.create_challenge','challenge = boundary.create_challenge',note='Alternative request branch; challenge and approve return before execute.')
 edge('jobs','boundary','AUTHORIZE','handle_plans_execute.approve_challenge','authorization = boundary.approve_challenge')
 edge('jobs','gateway','EXECUTE','handle_plans_execute.ExecutionGateway.execute','result, authorization = ExecutionGateway(boundary).execute')
 for a in ['context','providers']:
  edge(a,'boundary','AUTHORIZE','approve_challenge','boundary.approve_challenge(')
  edge(a,'gateway','EXECUTE','ExecutionGateway.execute','ExecutionGateway(boundary).execute(')
 edge('gateway','boundary','AUTHORIZE','ExecutionGateway.execute.consume_permit','authorization = self.boundary.consume_permit(')
 edge('gateway','boundary','AUTHORIZE','execute_server_owned.authorize_server_policy','authorization = self.boundary.authorize_server_policy(',note='Separate server-owned execution branch, not plan execute.')
 edge('gateway','boundary','AUTHORIZE','execute_nested.consumed_authority_lease','with self.boundary.consumed_authority_lease(')
 edge('gateway','registry','LOOKUP','canonical effect policy REGISTRY','from effect_registry import REGISTRY')
 edge('registry','contract','LOOKUP','CONTRACT_PATH','CONTRACT_PATH = Path(')
 for b,needle in [('planadapter','registry.register(PlanRuntimeEffectAdapter())'),('contextadapter','registry.register(ContextAttachEffectAdapter())'),('filesystem','registry.register(FilesystemReadEffectAdapter())')]: edge('gateway',b,'REGISTER','build_default_effect_adapter_registry',needle,note='Registration establishes availability, not execution.')
 edge('gateway','planadapter','EXECUTE','ExecutionGateway.execute.adapter.execute','result = adapter.execute(',note='Generic dispatch; target plan adapter selected only for plan.execute.')
 edge('planadapter','engine','LOOKUP','PlanRuntimeEffectAdapter.execute.get_plan','plan = engine.get_plan(plan_id)')
 edge('planadapter','pipeline','EXECUTE','execute_plan_through_gateway','return execute_plan_through_gateway(')
 edge('pipeline','engine','BIND','engine.set_executor','engine.set_executor(_executor)')
 edge('pipeline','engine','EXECUTE','engine.execute_plan','plan_result = engine.execute_plan(')
 edge('engine','pipeline','CALLBACK','PlanEngine._executor','raw = self._executor(',note='Callback bound by pipeline for this execution; restored after the run.')
 edge('pipeline','gateway','EXECUTE','gateway.execute_nested','child_result, _ = gateway.execute_nested(')
 edge('pipeline','claims','LOOKUP','gateway.claim_store_for','gateway.claim_store_for(context.manager)',note='Coordination owner; not authorization.')
 edge('gateway','claims','LOOKUP','execution_claim_store_for','return execution_claim_store_for(manager)')
 edge('gateway','filesystem','EXECUTE','_execute_nested_effect.adapter.execute','return adapter.execute(request, context)',note='Generic nested dispatch; filesystem target only for filesystem.read children, not every plan step.')
 edge('filesystem','sink','EXECUTE','FilesystemReadEffectAdapter.read_file_effect','return read_file_effect(')
 edge('jobs','response','TRANSPORT','handle_plans_execute.send_json','send_json(handler, 200 if bool(response.get("ok")) else 409, response)')
 edge('evidence','response','TRANSPORT','handle_latest.send_json','send_json(handler, 200, {',note='HTTP serialization; returns of child calls are not new dispatch edges.')
 edge('evidence','ledger','CONSTRUCT','_claim_ledger.ClaimLedger','return ClaimLedger(',note='Inert constructor: initializes paths; does not itself read files.')
 edge('ledger','ledger','LOOKUP','ClaimLedger.load_all.read_text','self.claims_file.read_text(',status='OWNER_PENDING',note='Raw persisted read. The available filesystem.read adapter is plan-child scoped; suitability for API ledger reads remains unresolved.')
 edge('evidence','ledger','LOOKUP','handle_claims.ClaimLedger.latest','_claim_ledger(mgr).latest()',status='OWNER_PENDING',note='Invokes persisted reads; canonical ownership violation remains unproven.')
 edge('evidence','ledger','LOOKUP','handle_claim.ClaimLedger.get','_claim_ledger(mgr).get(target)',status='OWNER_PENDING',note='Invokes persisted reads and evidence revalidation for verified claims.')
 edge('bridge','dispatch','ROUTE','do_GET.resolve_get','matched, call = resolve_get(')
 edge('dispatch','evidence','ROUTE','GET /evidence/claims -> handle_claims','"/evidence/claims",')
 edge('dispatch','evidence','ROUTE','GET /evidence/claims/<claim_id> -> handle_claim','return True, _call("handlers_evidence", "handle_claim", claim_id)')
 edge('evidence','response','TRANSPORT','handle_claims.send_json','send_json(handler, 200, {',occurrence=2,note='Final serialization after latest() returns; no ledger-to-response dispatch.')
 edge('evidence','response','TRANSPORT','handle_claim.send_json','send_json(handler, 200, {"ok": True, "claim": claim.to_dict()',note='Success serialization after get() returns; 404/500 branches also exist.')
 edge('dispatch','providers','ROUTE','POST /providers/configure -> handle_configure','"/providers/configure",')
 for a,b in [('evidence','boundary'),('evidence','gateway')]:
  edges.append(dict(id=f'H{sum(x["status"]=="HYPOTHESIS" for x in edges)+1:02}',from_node=a,to_node=b,type='AUTHORIZE' if b=='boundary' else 'EXECUTE',symbol='Candidate governed ledger-read path',status='HYPOTHESIS',source=None,note='OPTION pending ownership decision; not canonical, implemented or approved architecture.'))
 d['source_edges']=edges
 for e in edges:
  if e['type']=='ROUTE':
   excerpt=e['source']['excerpt'];m=re.search(r'\("(GET|POST)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"',excerpt)
   if m:e['endpoint']={'method':m[1],'path':m[2],'handler_module':m[3],'handler_function':m[4]}
   elif e['from_node']=='bridge':e['endpoint']={'method':'GET' if 'resolve_get' in excerpt else 'POST','path':'*','handler_function':'resolve_get' if 'resolve_get' in excerpt else 'resolve_post'}
   elif e['id']=='E55':e['endpoint']={'method':'GET','path':'/evidence/claims/<claim_id>','handler_module':'handlers_evidence','handler_function':'handle_claim'}
   else:raise ValueError(('ROUTE_METADATA_MISSING',e['id']))
 d['architecture_files']=[{'id':k,'path':v,'sha256':digest(v)} for k,v in FILES.items()]
 d['architecture_graph']={'layout':'nested funnels: lateral upper ingress, central control, descending plan branch; direction preserves calls','unique_files':len(FILES),'observed_relations':sum(e['status']!='HYPOTHESIS' for e in edges),'hypotheses':2,'scope':'Selected paths only; not complete endpoint or material sink inventory','visual_instances_note':'Gateway parent and nested are two phases of the same file; counts separate unique files from visual instances.'}
 d['source_edges_note']='Every observed edge stores source symbol, exact line/excerpt and SHA256. REGISTER is distinct from EXECUTE. Proposed edges have no runtime source.'
 d['architecture_views']=views(edges)
 DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 render(d)

def views(edges):
 by={e['id']:e for e in edges}
 road_expectations={
  'plan':('Después del último efecto representado: verificar resultado, claim, evidencia y revalidación contra el mismo candidato.','Efecto autorizado ejecutado; resultado y evidencia vinculados al candidato y verificados.'),
  'ingress':('Después de dispatch: inventariar y comprobar las rutas concretas de cada handler, con sus guardas y respuestas.','Cada ruta HTTP permitida llega a su handler correcto; las demás se rechazan antes de despachar.'),
  'prepare':('Después de construir el target: verificar binding de plan, sesión, workspace y precondiciones vigentes.','Plan y target ligados a identidad y recursos actuales; preparado sin ejecutar efectos.'),
  'challenge':('Al volver de challenge/approve: comprobar identidad de operación, recurso, expiración y revalidación antes del efecto.','Autorización vigente y ligada a la operación concreta; el efecto sólo continúa por su owner gobernado.'),
  'session':('Después de la lectura: comprobar esquema de respuesta, identidad de sesión y evidencia fresca del candidato.','Proyección de sesión correcta y trazada al SessionManager vigente.'),
  'context':('Después de ExecutionGateway: verificar adapter/efecto, autorización consumida, resultado y evidencia candidate-bound.','Efecto de contexto correcto, autorizado ahora y con resultado verificable ligado al candidato.'),
  'providers':('Después de ExecutionGateway: comprobar operación y adapter concretos, permiso vigente y evidencia del resultado.','Cambio/configuración de provider gobernado, con identidad, resultado y evidencia verificados.'),
  'evidence':('En ClaimLedger.latest(): resolver el owner correcto para la lectura persistida y verificar su evidencia; el bypass no está declarado como infracción.','Lectura del ledger bajo un owner aprobado, con provenance y frescura de la evidencia preservadas.'),
  'claim':('En ClaimLedger.get(): resolver el owner de la lectura y revalidar la claim histórica contra estado y política actuales.','Claim recuperada con procedencia preservada y estado actual revalidado; la lectura no convierte historial en validez.'),
  'hypothesis':('En el ledger: decidir si reutilizar un owner existente o definir otro; después especificar y verificar la integración.','Decisión de ownership aprobada y ruta ejecutable comprobada. Las alternativas verdes aún no son arquitectura.'),
  'registration':('Tras registrar el adapter: verificar resolución de política, selección para la operación y ejecución gobernada.','Adapter disponible y seleccionado por policy; ejecución, permiso, resultado y evidencia verificados por separado.'),
  'bootstrap':('Tras construir SessionManager, store y engine: arrancar el servicio real y comprobar readiness, binding y cierre.','Runtime inicializado con owners coherentes y readiness observada en una ejecución candidate-bound.'),
 }
 specs=[
 ('plan','Plan completo · ingreso y ejecución de un hijo read_file',['E01','E04','E05','E23','E36','E38','E40','E41','E42','E45','E46'], [('E02',1),('E03',1),('E28',4),('E30',9),('E37',5),('E39',6),('E43',8),('E47',3)],'El callback vuelve a una instancia visual del mismo pipeline, luego al mismo Gateway en fase nested. Un hijo filesystem.read es un ejemplo condicional. E47 serializa después del retorno de execute; su posición lateral no adelanta esa acción.'),
 ('ingress','Ingreso HTTP · origin, token y dispatch',['E01','E04'],[('E02',1),('E03',1)],'Las guardas preceden dispatch; ramas laterales muestran sus llamadas. Sin bootstrap ni registro.'),
 ('prepare','Plan · lookup y preparación del target',['E05','E20'],[('E10',1),('E19',1)],'Preparación previa a autorización; no ejecución de pipeline. PlanEngine y api_state se consultan desde el handler.'),
 ('challenge','Plan · challenge / approve (peticiones alternativas)',['E05','E21'],[('E22',1)],'Challenge y approve son acciones alternativas de petición; no se ejecutan ambas como cadena.'),
 ('session','Sesión · lookup',['E01','E53','E06','E11'],[], 'Ingreso GET y consulta de SessionManager mediante api_state; sin bootstrap.'),
 ('context','Contexto · autorización y ejecución',['E01','E04','E07','E25'],[('E24',3),('E28',4)],'Approve es petición alternativa. No se introduce pipeline universal ni registro como ejecución.'),
 ('providers','Providers · autorización y ejecución',['E01','E04','E58','E27'],[('E26',3),('E28',4)],'POST /providers/configure → handle_configure. Approve es petición alternativa. Vista acotada al handler y frontera, no cadena completa de todos los adapters.'),
 ('evidence','Claims · lectura real y owner pendiente',['E01','E53','E54','E51','E50'],[('E14',3),('E56',3)],'GET /evidence/claims → handle_claims → latest(). E56 serializa tras retorno de lectura, no antes. Constructor inerte E49 está en inventario azul. Rojo = owner pendiente, no violación demostrada.'),
 ('claim','Claim individual · get y lectura',['E01','E53','E55','E52','E50'],[('E14',3),('E57',3)],'GET /evidence/claims/<claim_id> → handle_claim → get(). E57 serializa tras retorno de lectura. get() puede revalidar evidencia histórica; esta vista no inventa todas sus lecturas internas.'),
 ('hypothesis','Evidencia · opciones futuras sin decisión',['E01','E53','E54'],[('H01',3),('H02',3)],'Opciones verdes separadas. No se afirma conexión secuencial AuthorizationBoundary → Gateway ni compatibilidad con adapter plan-child.'),
 ('registration','Disponibilidad · registro de adapter plan',['E33'],[], 'REGISTER no ejecuta un plan. Las demás relaciones permanecen en inventario.'),
 ('bootstrap','Bootstrap · construcción de owners',['E16','E18'],[('E17',1)],'Main construye SessionManager; SessionManager construye PlanEngine/ContextStore. No es una petición HTTP.')]
 result=[]
 for key,label,chain,side,note in specs:
  nodes=[];links=[]
  def add_node(file,i,x,y,phase):
   layers={'client':'Ingreso','bridge':'Ingreso / guardas HTTP','dispatch':'Resolución','jobs':'Preparación / dispatch','state':'Lookup de estado','session':'Resolución de sesión','context':'Preparación de contexto','providers':'Preparación de provider','evidence':'Resolución de evidencia','boundary':'Autorización','gateway':'Autorización / ejecución','planadapter':'Ejecución de plan','pipeline':'Preparación / callback gobernado','engine':'Ejecución / callback','filesystem':'Ejecución del adapter','sink':'Efecto material','response':'Salida HTTP','ledger':'Lectura / ownership pendiente','manager':'Bootstrap de owners','store':'Owner de persistencia','claims':'Coordinación / fencing'}
   id=f'{key}-n{i}';nodes.append(dict(id=id,file_id=file,x=x,y=y,width=260,height=74,phase=phase,layer=layers.get(file,'Registro / contrato')));return id
  first=by[chain[0]];previous=add_node(first['from_node'],0,120,55,'entrada lateral / owner')
  for i,eid in enumerate(chain):
   e=by[eid];assert nodes[i]['file_id']==e['from_node'],(key,eid)
   phase='fase '+str(i+1)
   if key=='plan' and e['to_node']=='gateway':phase='fase parent' if i==3 else 'fase nested'
   if key=='plan' and e['to_node']=='pipeline':phase='preparación executor' if i==5 else 'callback de hijo'
   dest=add_node(e['to_node'],i+1,600,55+(i+1)*122,phase)
   points=[[730,55+i*122+74],[730,55+(i+1)*122]] if i else [[250,129],[250,155],[730,155],[730,177]]
   links.append(dict(edge_id=eid,from_instance=previous,to_instance=dest,points=points,road_class='TRUNK'))
   previous=dest
  sides={}
  for eid,index in side:
   e=by[eid];source=nodes[index];assert source['file_id']==e['from_node'],(key,eid,index)
   slot=sides.get(index,0);assert slot<2;sides[index]=slot+1
   x=120 if slot==0 else 1080;y=source['y'];dest=add_node(e['to_node'],len(nodes),x,y,'rama / condición · '+eid)
   links.append(dict(edge_id=eid,from_instance=source['id'],to_instance=dest,points=[[source['x'] if slot==0 else source['x']+260,y+37],[x+260 if slot==0 else x,y+37]],road_class='SECONDARY'))
  endpoint=next((by[eid]['endpoint'] for eid in chain if by[eid]['type']=='ROUTE' and by[eid]['endpoint']['path']!='*'),None)
  work_start,expected_terminal=road_expectations[key]
  result.append(dict(id=key,label=label,note=note,expected_endpoint=endpoint,nodes=nodes,links=links,height=55+(len(chain)+1)*122+42,work_start=work_start,expected_terminal=expected_terminal))
 return result

def _render_graph_markup(d):
 old=HTML.read_text(encoding='utf-8'); start=old.index('<section class="panel" aria-label="Arquitectura'); end=old.find('<section class="grid">',start)
 if end<0:end=old.index('</main>',start)
 data=json.dumps({'nodes':d['architecture_files'],'edges':d['source_edges'],'graph':d['architecture_graph'],'views':d['architecture_views']},ensure_ascii=False).replace('</','<\\/')
 section='''<section class="panel" aria-label="Arquitectura de BAGO por archivos fuente">
<div class="panel-head"><div><h2>Embudo de control · seguir un recorrido real</h2><p>Entradas laterales superiores convergen en control. Sólo los tramos realmente secuenciales descienden por el eje; lookup, preparación, registro y callbacks conservan su dirección. El pipeline corresponde a plan.execute.</p></div><span class="score" id="graph-count"></span></div>
<style>
.path-picker{margin:18px 24px 14px;padding:18px 20px;border:1px solid #63e0bb;border-radius:14px;background:linear-gradient(110deg,#102b38,#132332);box-shadow:0 0 0 2px #63e0bb22}
.path-picker label{display:block;margin-bottom:9px;color:#63e0bb;font-size:13px;font-weight:800;letter-spacing:.12em}
.path-picker select{display:block;width:100%;min-height:54px;padding:10px 48px 10px 14px;border:2px solid #79baff;border-radius:10px;background:#091722;color:#f2f7fb;font:700 18px system-ui;cursor:pointer}
.path-picker select:focus{outline:3px solid #63e0bb;outline-offset:3px}
.path-picker small{display:block;margin-top:9px;color:#a9bfd0;font-size:13px}
.selected-path{margin:0 24px 16px;padding:18px 20px;border:1px solid #294357;border-radius:12px;background:#0d1b27}
.selected-path h3{margin:0 0 8px;color:#eef5f9;font-size:19px}
.selected-path p{margin:0;color:#b9cbd7;line-height:1.55}
.path-legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}
.path-legend-item{display:flex;align-items:flex-start;gap:9px;flex:1 1 230px;padding:10px 12px;border:1px solid #294357;border-radius:9px;background:#112333;color:#dce8ef;font-size:13px;line-height:1.4}
.path-legend-swatch{flex:0 0 28px;height:0;margin-top:8px;border-top:3px solid currentColor}
.path-legend-swatch.dashed{border-top-style:dashed}
.road-territory{margin:14px 24px 16px;padding:18px 20px;border:1px solid #294357;border-radius:12px;background:#0b1924}
.road-territory h3{margin:0 0 6px;color:#eef5f9;font-size:18px}
.road-territory>p{margin:0 0 14px;color:#a9bfd0;font-size:13px;line-height:1.5}
.road-flow{display:grid;grid-template-columns:minmax(180px,1fr) 34px minmax(220px,1.25fr) 34px minmax(220px,1.25fr);align-items:stretch;gap:8px}
.road-node{padding:14px;border:1px solid #79baff;border-radius:10px;background:#112333;min-width:0}
.road-node small{display:block;margin-bottom:7px;color:#93a8b8;font-weight:800;letter-spacing:.06em}
.road-node strong{display:block;color:#eef5f9;line-height:1.4}
.road-node p{margin:8px 0 0;color:#c1d1dd;font-size:13px;line-height:1.5}
.road-node.work{border-color:#f5c96a}
.road-node.work.owner-open{border-color:#ff887e}
.road-node.target{border:2px dashed #63e0bb}
.road-arrow{position:relative;align-self:center;height:0;border-top:3px solid #79baff}
.road-arrow::after{content:"";position:absolute;right:-1px;top:-6px;border-top:5px solid transparent;border-bottom:5px solid transparent;border-left:8px solid #79baff}
.road-arrow.future{border-top:3px dashed #63e0bb}
.road-arrow.future::after{border-left-color:#63e0bb}
.road-legend{margin-top:12px;color:#a9bfd0;font-size:12px;line-height:1.5}
@media(max-width:850px){.road-flow{grid-template-columns:1fr}.road-arrow{justify-self:center;width:0;height:24px;border-top:0;border-left:3px solid #79baff}.road-arrow.future{border-left:3px dashed #63e0bb;border-top:0}.road-arrow::after{right:-5px;top:auto;bottom:-1px;transform:rotate(90deg)}}
</style>
<div class="path-picker"><label for="path-choice">ELIGE EL CAMINO QUE QUIERES SEGUIR</label><select id="path-choice" aria-describedby="path-picker-help"></select><small id="path-picker-help">Al cambiarlo se actualizan el recorrido, su explicación, su leyenda y las relaciones con sus fuentes.</small></div>
<div style="overflow:auto;padding:0 12px"><svg id="funnel" class="architecture-svg" viewBox="0 0 1500 1650" style="display:block;width:100%;min-width:1000px;height:auto;overflow:visible;font-family:system-ui" role="img" aria-label="Embudo de rutas de ejecución con retornos laterales"></svg></div>
<section class="road-territory" aria-live="polite" aria-atomic="true"><h3>Territorio del camino · avance y frontera de trabajo</h3><p>El tramo azul continuo representa relaciones observadas en el código; no afirma validación. Las ramas laterales son desvíos reales del flujo inspeccionado. La conexión verde discontinua señala trabajo y objetivo esperado; no representa una llamada implementada ni un cierre alcanzado.</p><div class="road-flow"><div class="road-node paved"><small>RECORRIDO TRAZADO EN CÓDIGO</small><strong id="road-paved-count"></strong><p id="road-branches"></p></div><span class="road-arrow" aria-hidden="true"></span><div class="road-node work" id="road-work-node"><small>AQUÍ EMPIEZA EL TRABAJO</small><strong id="road-work-start"></strong><p id="road-work-detail"></p></div><span class="road-arrow future" aria-hidden="true"></span><div class="road-node target"><small>ESTADO FINAL ESPERADO · OBJETIVO</small><strong id="road-target-title">Gobierno y verificación completos</strong><p id="road-target"></p></div></div><div class="road-legend">Azul continuo · relación rastreada en fuente. Desvío lateral · rama observada. Rojo · ownership por resolver, sin declarar infracción. Ámbar · frontera donde empieza trabajo por verificar. Verde discontinuo · continuidad propuesta hacia el objetivo, todavía no ejecutada.</div></section>
<section class="selected-path" id="selected-path" aria-live="polite" aria-atomic="true"><h3 id="path-title"></h3><p id="path-note"></p><div class="path-legend" id="path-legend" aria-label="Leyenda de estados de este camino"></div></section>
<div style="padding:20px;overflow:auto"><h3>Relaciones del recorrido · IDs y evidencia</h3><table id="path-table" style="width:100%;font-size:12px;border-collapse:collapse"></table></div>
<details style="padding:20px"><summary>Inventario completo de archivos y relaciones trazadas</summary><div id="file-index"></div><table id="all-edges" style="width:100%;font-size:11px"></table></details>
</section>
<script id="boundary-graph-data" type="application/json">DATA</script>
<script>
(()=>{const D=JSON.parse(document.getElementById('boundary-graph-data').textContent), N=Object.fromEntries(D.nodes.map(n=>[n.id,n]));
const svg=document.getElementById('funnel'),choice=document.getElementById('path-choice'),E=Object.fromEntries(D.edges.map(e=>[e.id,e]));
const link=s=>'../../'+s.path+'#L'+s.line_start;
function row(e){return '<tr><td style="padding:8px;border-bottom:1px solid #294357">'+e.id+'</td><td>'+e.type+'<br>'+e.status+'</td><td>'+N[e.from_node].path.split('/').pop()+' → '+N[e.to_node].path.split('/').pop()+'<br>'+(e.endpoint?e.endpoint.method+' '+e.endpoint.path+' → '+e.endpoint.handler_function+'<br>':'')+e.symbol+'<br>'+e.note+'</td><td>'+(e.source?'<a style="color:#63e0bb" href="'+link(e.source)+'">L'+e.source.line_start+' · '+e.source.sha256.slice(0,12)+'</a>':'Sin fuente runtime · propuesta')+'</td></tr>'}
for(const v of D.views){const o=document.createElement('option');o.value=v.id;o.textContent=v.label;choice.append(o)}
document.getElementById('all-edges').innerHTML=D.edges.map(row).join('');document.getElementById('file-index').innerHTML=D.nodes.map(n=>'<p><a style="color:#79baff" href="../../'+n.path+'">'+n.path+'</a> · SHA256 '+n.sha256+'</p>').join('');
document.getElementById('graph-count').textContent=D.nodes.length+' ARCHIVOS · '+D.graph.observed_relations+' OBSERVADAS + '+D.graph.hypotheses+' HIPÓTESIS';
function draw(){const v=D.views.find(v=>v.id===choice.value),colors={OBSERVED:'#79baff',OWNER_PENDING:'#ff887e',HYPOTHESIS:'#63e0bb'};svg.setAttribute('viewBox','0 0 1500 '+v.height);let s='<defs>'+Object.entries(colors).map(([id,c])=>'<marker id="m-'+id+'" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="'+c+'"/></marker>').join('')+'</defs><text x="730" y="32" text-anchor="middle" fill="#93a8b8" font-size="13">INGRESO LATERAL → EJE CENTRAL · RAMAS LOCALES SIN CRUCES</text>';
for(const l of v.links){const e=E[l.edge_id],c=colors[e.status],points=l.points,path=points.map((p,i)=>(i?'L':'M')+p.join(' ')).join(' '),p=points[0],q=points[1],vertical=p[0]===q[0];let tx=vertical?p[0]+12:(p[0]+q[0])/2,ty=vertical?(p[1]+q[1])/2:p[1]-10;s+=`<g data-edge-id="${e.id}"><title>${e.id} ${e.type} ${e.symbol} | ${e.status} | ${e.source?e.source.path+':'+e.source.line_start:'hypothesis'}</title><path d="${path}" fill="none" stroke="${c}" stroke-width="2" ${e.status==='HYPOTHESIS'?'stroke-dasharray="8 6"':''} marker-end="url(#m-${e.status})"/><text x="${tx}" y="${ty}" text-anchor="${vertical?'start':'middle'}" fill="${c}" font-size="11">${e.id} · ${e.type}</text></g>`}
for(const n of v.nodes){const file=N[n.file_id],same=v.nodes.filter(x=>x.file_id===n.file_id).length>1;s+=`<g class="node" data-node-id="${n.id}" style="display:inline;visibility:visible;opacity:1"><title>${file.path} | SHA256 ${file.sha256}</title><rect x="${n.x}" y="${n.y}" width="${n.width}" height="${n.height}" rx="12" style="display:inline;visibility:visible;fill:#112333;stroke:${n.file_id==='gateway'?'#63e0bb':'#79baff'};stroke-width:2"/><text x="${n.x+130}" y="${n.y+24}" text-anchor="middle" style="display:inline;visibility:visible;fill:#eef5f9;font-size:12px;font-weight:700">${file.path.split('/').pop()}</text><text x="${n.x+130}" y="${n.y+44}" text-anchor="middle" style="display:inline;visibility:visible;fill:#c1d1dd;font-size:10px">${same?'MISMO ARCHIVO · ':''}${n.phase}</text><text x="${n.x+130}" y="${n.y+64}" text-anchor="middle" style="display:inline;visibility:visible;fill:#63e0bb;font-size:10px">CAPA · ${n.layer}</text></g>`}
svg.innerHTML=s;const unique=new Set(v.nodes.map(n=>n.file_id)).size;document.getElementById('path-title').textContent='Camino seleccionado · '+v.label;document.getElementById('path-note').textContent=v.note+' · '+v.nodes.length+' instancias de archivo / '+unique+' archivos únicos visibles. Geometría del recorrido: 0 atravesamientos de nodos y 0 cruces entre flechas.';const routeEdges=v.links.map(l=>({link:l,edge:E[l.edge_id]})),traced=routeEdges.filter(x=>x.edge.source),branches=routeEdges.filter(x=>x.link.road_class==='SECONDARY'),pending=routeEdges.find(x=>x.edge.status==='OWNER_PENDING'),hypothesis=routeEdges.find(x=>x.edge.status==='HYPOTHESIS'),frontier=pending?'En '+pending.edge.from_node+' → '+pending.edge.to_node+' · '+pending.edge.id:hypothesis?'En '+hypothesis.edge.from_node+' · decisión de arquitectura abierta':'Después del último tramo rastreado · falta verificación fresca ligada al candidato';document.getElementById('road-paved-count').textContent=traced.length+' relaciones con fuente · '+v.nodes.length+' nodos/instancias trazados';document.getElementById('road-branches').textContent=branches.length?branches.length+' vías secundarias: '+branches.map(x=>x.edge.id+' '+x.edge.type).join(' · '):'Sin vías secundarias en el alcance de este camino.';document.getElementById('road-work-node').className='road-node work'+(pending?' owner-open':'');document.getElementById('road-work-start').textContent=frontier;document.getElementById('road-work-detail').textContent=pending?pending.edge.note:hypothesis?'La alternativa verde es propuesta; primero resolver el owner y aprobar el contrato.':'El mapa prueba que existe esta relación en el código; no acredita todavía pruebas actuales ni validación candidate-bound. '+v.work_start;document.getElementById('road-target').textContent=v.expected_terminal+' Este estado es objetivo, no estado observado.';const meanings={OBSERVED:'HECHO · relación observada en el código y enlazada con su archivo fuente.',OWNER_PENDING:'DUEÑO PENDIENTE · el acceso directo aparece en código; falta resolver quién debe gobernarlo. La infracción no está demostrada.',HYPOTHESIS:'HIPÓTESIS · conexión propuesta para discutir; no afirma que esté implementada ni aprobada.'};document.getElementById('path-legend').innerHTML=[...new Set(v.links.map(l=>E[l.edge_id].status))].map(status=>'<div class="path-legend-item" style="color:'+colors[status]+'"><span class="path-legend-swatch'+(status==='HYPOTHESIS'?' dashed':'')+'" aria-hidden="true"></span><span>'+meanings[status]+'</span></div>').join('');document.getElementById('path-table').innerHTML='<tr><th>ID</th><th>Tipo / estado</th><th>Relación y condición (eje, luego ramas)</th><th>Fuente</th></tr>'+v.links.map(l=>row(E[l.edge_id])).join('');}choice.onchange=draw;draw();})();
</script>
'''.replace('DATA',data)
 old=old[:start]+section+old[end:]
 # Remove misleading fresh-score assertions while retaining historical observations.
 old=old.replace('7 DOMINIOS BACKEND · 3/4','7 DOMINIOS BACKEND · 2/4 ORDINAL').replace('3/4 · 75%','2/4 · escala ordinal').replace('SCORES REALES DEL CHECKOUT','ESCALA ORDINAL · TRAZA LOCAL').replace('3/4','2/4').replace('3 · 75%','3 · evidencia fresca requerida').replace('2 · 50%','2 · código + contrato').replace('1 · 25%','1 · implementación').replace('0 · 0%','0 · ausente').replace('4 · 100%','4 · cierre candidato').replace('0/4 · 0%','0/4 · propuesta')
 old=old.replace('Hay código, contrato explícito y suite focal pasada en este checkout.','Hay código y contrato explícito. Las suites históricas carecen aquí de logs y fingerprint frescos.').replace('Pruebas focales de este pase','Pruebas históricas reportadas').replace('256 PASS','256 reportados').replace('Más 158 subtests. Cinco grupos:','158 subtests reportados; NOT_RUN en esta edición. Cinco grupos:').replace('strict-runtime: FAIL/OPEN.','strict-runtime: históricamente abierto; exit code CONFLICTED (1/2).').replace('suite focal pasa aquí','suite focal tiene evidencia fresca ligada al estado medido').replace('strict-classification</code>: PASS,','strict-classification</code>: PASS histórico reportado,').replace('strict-runtime</code>: FAIL','strict-runtime</code>: OPEN histórico reportado, exit code CONFLICTED (1/2)')
 old=old.replace('Las superficies del radar ahora son puntuaciones calculadas con la misma escala.','Las superficies ordenan dominios con una escala ordinal de evidencia; no expresan porcentajes de calidad, cobertura o madurez total.').replace('estas puntuaciones sí son cuantificadas y reproducibles con la rúbrica mostrada;','estas puntuaciones son ordinales; los recuentos de pruebas y sinks son históricos reportados, sin reejecución ni fingerprint actual;')
 # All backend domains are now 2; update radar polygon and point glyphs coherently.
 old=old.replace('M380 155 L518 212 L575 350 L518 488 L380 545 L242 488 L185 350 L288 258Z','M380 220 L472 258 L510 350 L472 442 L380 480 L288 442 L250 350 L288 258Z')
 old=old.replace('Siete dominios del backend puntúan 3 sobre 4','Siete dominios del backend puntúan 2 sobre 4 en escala ordinal').replace('superficie con evidencia 2/4','superficie código + contrato 2/4')
 old=old.replace('Lo que el score 3 afirma','Lo que el score 2 afirma').replace('Construido y probado en alcance focal','Código y contrato trazados').replace('y las suites listadas pasaron en este checkout.','y las suites listadas son resultados históricos reportados, sin verificación fresca.').replace('Route contract check: PASS con','Route contract check: PASS histórico reportado con').replace('Pruebas existentes ejecutadas:','Resultados históricos reportados, NOT_RUN en esta edición:')
 labels=['API','SESIÓN','CONTEXTO','PROVIDERS','AUTH + GATEWAY','EVIDENCIA','PIPELINE','UI / API','UI NUEVA']
 pts=[]; elements=[]
 for i,label in enumerate(labels):
  angle=-math.pi/2+i*2*math.pi/9;score=2 if i<8 else 0
  x=380+65*score*math.cos(angle);y=350+65*score*math.sin(angle);pts.append(f'{x:.1f},{y:.1f}')
  lx=380+285*math.cos(angle);ly=350+285*math.sin(angle)
  elements.append(f'<line x1="380" y1="350" x2="{lx:.1f}" y2="{ly:.1f}" stroke="#294357"/><circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#63e0bb"/><text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" fill="#e8f1f8" font-size="11">{label} · {score}/4</text>')
 radar='<svg class="radar" viewBox="0 0 780 700" role="img" aria-label="Escala ordinal por dominios; código y contrato 2/4, UI nueva 0/4">'+''.join(f'<circle cx="380" cy="350" r="{65*i}" fill="none" stroke="#294357"/>' for i in range(1,5))+'<polygon points="'+' '.join(pts)+'" fill="#63e0bb22" stroke="#63e0bb" stroke-width="2"/>'+''.join(elements)+'</svg>'
 old=re.sub(r'<svg class="radar".*?</svg>',radar,old,count=1,flags=re.S)
 old=re.sub(r'(histórico reportado\s*){2,}', 'histórico reportado ', old)
 HTML.write_text(old,encoding='utf-8')

def render(d):
 # Reuse the established graph renderer, then publish graph, radar and progress
 # as three linked pages sharing the same measured sidecar.
 _render_graph_markup(d)
 old=HTML.read_text(encoding='utf-8'); start=old.index('<section class="panel" aria-label="Arquitectura'); end=old.index('</script>',old.index('</script>',start)+len('</script>'))+len('</script>')
 graph=old[start:end]
 graph=graph.replace('Embudo de control · seguir un recorrido real','Archivos y llamadas · camino seleccionado')
 graph=graph.replace('Entradas laterales superiores convergen en control. Sólo los tramos realmente secuenciales descienden por el eje; lookup, preparación, registro y callbacks conservan su dirección. El pipeline corresponde a plan.execute.','Selecciona un camino para ver su explicación, estados y referencias al código fuente. Las flechas siguen llamadas observadas; las hipótesis se muestran con línea discontinua.')
 graph=graph.replace('style="width:100%;min-width:1000px;font-family:system-ui"','style="width:100%;min-width:900px;font-family:system-ui"')
 intro='<div class="map-copy"><h1>Mapa de arquitectura · seguir un camino real</h1><p>Las entradas de API llegan desde arriba y por los laterales. En el centro se ven las llamadas que siguen su secuencia; las ramas conservan la dirección que tienen en el código. Cada caja es un archivo y cada flecha enlaza con la línea correspondiente del código fuente. El <code>GovernedWorkPipeline</code> aparece en el camino de <code>plan.execute</code>; no representa un paso universal para todos los handlers.</p></div>'
 css=re.split(r'\s*body\{font-size:16px\}\.page\{max-width:1540px\}',re.search(r'<style>(.*?)</style>',old,re.S).group(1),maxsplit=1)[0]
 css+='''\nbody{font-size:16px}.page{max-width:1540px}.intro{max-width:1050px;font-size:19px;line-height:1.7;color:#d5e1e9}.nav{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0}.nav a{padding:11px 15px;border:1px solid #45657a;border-radius:10px;background:#102332;color:#e8f1f8;text-decoration:none;font-weight:750}.nav a:hover{border-color:#63e0bb;color:#63e0bb}.dashboard-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin:22px 0}.dashboard-card{padding:18px;border:1px solid #294357;border-radius:15px;background:#101e2b}.dashboard-card b{display:block;color:#9eb0bf;font-size:12px;letter-spacing:.08em;text-transform:uppercase}.dashboard-card strong{display:block;margin:7px 0;font-size:27px;color:#63e0bb}.dashboard-card p{margin:0;color:#bdcbd6;font-size:14px}.work-list{display:grid;gap:11px;counter-reset:work}.work-item{position:relative;padding:17px 19px 17px 58px;border:1px solid #294357;border-radius:13px;background:#101e2b}.work-item:before{counter-increment:work;content:counter(work);position:absolute;left:17px;top:15px;display:grid;place-items:center;width:28px;height:28px;border:1px solid #ffca70;color:#ffca70;border-radius:50%;font-weight:850}.work-item h3{margin:0 0 5px;font-size:17px}.work-item p{margin:0;color:#bdcbd6}.page-links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;margin:22px 0}.page-link{padding:19px;border:1px solid #35536a;border-radius:16px;background:linear-gradient(145deg,#112332,#09141f);color:inherit;text-decoration:none}.page-link h2{margin:0 0 7px}.page-link p{margin:0;color:#bdcbd6}.radar-page{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(310px,.8fr);gap:18px;align-items:center}.radar-domain-list{display:grid;gap:8px}.radar-domain{display:grid;grid-template-columns:minmax(150px,1fr) 110px 40px;gap:10px;align-items:center;padding:9px 11px;border:1px solid #294357;border-radius:10px;background:#0c1925}.radar-bar{height:9px;background:#203746;border-radius:99px;overflow:hidden}.radar-bar i{display:block;height:100%;background:#63e0bb;border-radius:99px}.radar-svg{width:100%;height:auto}.map-copy{padding:20px 24px;border-bottom:1px solid #294357;background:linear-gradient(100deg,#142d3b,#101e2b)}.map-copy h1{font-size:clamp(27px,3.5vw,42px);line-height:1.08;letter-spacing:-.025em;margin:0 0 9px}.map-copy p{font-size:17px;line-height:1.7;color:#d5e1e9;max-width:1120px;margin:0}.panel-head{align-items:start}.panel-head p{font-size:15px;line-height:1.65;color:#d5e1e9;max-width:1100px;margin:8px 0}.architecture-svg{min-width:900px}.path-picker{margin:14px 20px}.selected-path{margin-inline:20px}@media(max-width:980px){.dashboard-grid{grid-template-columns:repeat(2,1fr)}.radar-page{grid-template-columns:1fr}}@media(max-width:620px){.dashboard-grid,.page-links{grid-template-columns:1fr}.radar-domain{grid-template-columns:1fr 90px 38px}.map-copy{padding:16px}.map-copy p{font-size:16px}}\n'''
 nav='<nav class="nav" aria-label="Páginas del mapa"><a href="BACKEND_PROGRESS_20261006.html">⌂ Progreso</a><a href="BACKEND_BOUNDARY_MAP_20261006.html">⇢ Arquitectura</a><a href="BACKEND_MATURITY_RADAR_20261006.html">◉ Radar</a></nav>'
 def page(title,body):return '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+css+'</style></head><body><main class="page"><div class="top"><span class="brand">BAGO / Territorio backend</span><span>6 de octubre de 2026 · estado local y evidencia disponible</span></div>'+nav+body+'</main></body></html>'
 map_html=page('BAGO · Mapa de arquitectura backend',intro+graph+'<p class="intro" style="font-size:13px;margin:18px 8px;color:#93a8b8">Alcance: caminos seleccionados del backend. El inventario global de endpoints y sinks no está representado por completo aquí. El grafo no certifica que todos los efectos pasen por el Gateway.</p>')

 scores=d['scores'];center=(470,355);radius=235;points=[];axes=[];rings=[]
 for n in range(1,5):rings.append(f'<circle cx="{center[0]}" cy="{center[1]}" r="{radius*n/4:.1f}" fill="none" stroke="#294357"/>')
 for i,item in enumerate(scores):
  angle=-math.pi/2+i*2*math.pi/len(scores);value=int(item['score']);x=center[0]+radius*value/4*math.cos(angle);y=center[1]+radius*value/4*math.sin(angle);points.append(f'{x:.1f},{y:.1f}')
  x2=center[0]+radius*math.cos(angle);y2=center[1]+radius*math.sin(angle);axes.append(f'<line x1="{center[0]}" y1="{center[1]}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#294357"/><circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#63e0bb" stroke="#08111a" stroke-width="2"/>')
 radar_svg='<svg class="radar-svg" viewBox="0 0 940 710" role="img" aria-label="Radar ordinal generado de las nueve puntuaciones del artefacto de evidencia">'+''.join(rings)+''.join(axes)+'<polygon points="'+' '.join(points)+'" fill="#63e0bb28" stroke="#63e0bb" stroke-width="3"/></svg>'
 domain_rows=''.join('<div class="radar-domain"><span>'+item['domain']+'</span><span class="radar-bar" aria-label="'+str(item['score'])+' de 4"><i style="width:'+str(int(item['score'])*25)+'%"></i></span><b>'+str(item['score'])+'/4</b></div>' for item in scores)
 backend_scores=[int(x['score']) for x in scores if x['domain'] not in {'Existing frontend to API literal integration','New UI requested by the user'}];new_ui=next((int(x['score']) for x in scores if x['domain']=='New UI requested by the user'),None)
 radar_body='<h1>Radar · madurez evidencial por dominio</h1><p class="intro">Cada eje toma la puntuación del artefacto local de evidencia. El radio usa una escala ordinal de 0 a 4; no representa porcentaje, calidad total ni validación global. Las pruebas registradas no están ligadas a este candidato, así que no elevan los dominios a 3.</p><section class="panel"><div class="panel-head"><div><h2>Superficie actual según el artefacto</h2><p>Dominios backend en '+str(min(backend_scores))+'–'+str(max(backend_scores))+'/4; UI nueva '+str(new_ui)+'/4. Puntuaciones tomadas directamente del sidecar JSON.</p></div><span class="score">ESCALA 0–4 · ORDINAL</span></div><div class="radar-page">'+radar_svg+'<div class="radar-domain-list">'+domain_rows+'</div></div><div class="legend"><span>El anillo 1–4 indica nivel evidencial alcanzado.</span><span>Backend congelado: no afirmado.</span></div></section><section class="alert"><b>Estado de evidencia:</b> las suites listadas son históricas, sin logs ligados al fingerprint actual. El radar refleja el nivel conservador del sidecar: código + contrato donde está puntuado 2; la UI nueva todavía figura como 0. Ver <a href="evidence/backend-territory-maturity-20261006.json">artefacto de medición y procedencia</a>.</section>'
 radar_html=page('BAGO · Radar de madurez backend',radar_body)

 gates=d.get('effect_sink_gates',{});strict=gates.get('strict_runtime',{});route=d.get('route_contract',{});client=d.get('measured_client_contract_relation',{});nfiles=d.get('architecture_graph',{}).get('unique_files',0);observed=d.get('architecture_graph',{}).get('observed_relations',0)
 queue=[('01 · Refrescar la medición','Ejecutar el inventario global y las verificaciones focales sobre HEAD y fingerprint actuales. Sustituir recuentos heredados sólo con recibos enlazados al candidato.'),('02 · Cerrar ownership de sinks','Último registro: '+str(strict.get('runtime_unbound','sin dato'))+' runtime-unbound sobre '+str(strict.get('total_sinks','sin dato'))+'; strict-runtime sigue OPEN y el exit code está en conflicto. Trazar cada grupo hasta su owner antes de reparar.'),('03 · Revalidar la costura UI/API','El último extractor encontró '+str(client.get('exact_static_matches','?'))+'/'+str(client.get('static_route_denominator','?'))+' referencias literales exactas. Es una medida estática histórica; revisar rutas dinámicas y validar el contrato actual.'),('04 · Probar y congelar por evidencia','Repetir gates sobre candidato limpio, registrar recibos oficiales y obtener revisión independiente. Sólo entonces evaluar si un perímetro backend puede declararse congelado.'),('05 · Ampliar UI nueva por bloques','La puntuación guardada de UI nueva es '+str(new_ui)+'/4. Diseñar la primera pantalla sobre contratos comprobados y elevar el nivel sólo con implementación y evidencia fresca.')]
 work=''.join('<article class="work-item"><h3>'+title+'</h3><p>'+desc+'</p></article>' for title,desc in queue)
 home='<h1>Progreso del mapa de fronteras</h1><p class="intro">Este panel reúne el estado que puede sostener el artefacto actual y el trabajo necesario para afirmar que un perímetro backend está verificado y congelado. No convierte resultados de otro candidato en evidencia vigente.</p><div class="status">CANDIDATO LOCAL SUCIO · SIN RECIBO CANDIDATE-BOUND · BACKEND GLOBAL ABIERTO</div><section class="dashboard-grid"><article class="dashboard-card"><b>Mapa de arquitectura</b><strong>'+str(nfiles)+' archivos</strong><p>'+str(observed)+' relaciones observadas en caminos seleccionados. No es inventario global.</p></article><article class="dashboard-card"><b>Madurez evidencial backend</b><strong>'+str(min(backend_scores))+'/4 ordinal</strong><p>'+str(len(backend_scores))+' dominios backend en el sidecar entre '+str(min(backend_scores))+' y '+str(max(backend_scores))+'/4.</p></article><article class="dashboard-card"><b>Strict runtime</b><strong>OPEN</strong><p>'+str(strict.get('runtime_unbound','?'))+' runtime-unbound del último registro; no revalidado en esta edición.</p></article><article class="dashboard-card"><b>Recibo candidate-bound</b><strong>PENDIENTE</strong><p>No existe recibo del mapa ligado al HEAD y fingerprint de este checkout. Debe generarse sobre el candidato exacto.</p></article></section><section class="page-links"><a class="page-link" href="BACKEND_BOUNDARY_MAP_20261006.html"><h2>→ Mapa de arquitectura</h2><p>Archivos, dispatch, handlers, Gateway, pipeline, lecturas y caminos con líneas fuente.</p></a><a class="page-link" href="BACKEND_MATURITY_RADAR_20261006.html"><h2>◉ Radar de madurez</h2><p>Puntuación ordinal por dominio y evidencia que sustenta cada superficie.</p></a></section><section class="panel"><div class="panel-head"><div><h2>Trabajo pendiente para cerrar el perímetro</h2><p>Ordenado para que una afirmación de congelación se apoye en medición vigente y ownership demostrado.</p></div></div><div class="work-list" style="padding:16px 20px 22px">'+work+'</div></section><section class="alert"><b>Última medición disponible — histórica, no revalidada:</b> '+str(gates.get('strict_classification',{}).get('total_sinks','?'))+' sinks; '+str(strict.get('runtime_unbound','?'))+' runtime-unbound; strict-classification registró '+str(gates.get('strict_classification',{}).get('unclassified_scope','?'))+' sin clasificar. El resultado exacto de strict-runtime está conflictuado. Costura estática cliente/API: '+str(route.get('frontend_exact_literal_matches',client.get('exact_static_matches','?')))+'/'+str(route.get('static_routes',client.get('static_route_denominator','?')))+'; rutas construidas dinámicamente no medidas por ese recuento.</section><footer>Fuente: <a href="evidence/backend-territory-maturity-20261006.json">sidecar de evidencia</a>. El snapshot de medición proviene de '+str(d.get('candidate',{}).get('head','desconocido'))+' y fue capturado con dirty='+str(d.get('candidate',{}).get('worktree_dirty','desconocido'))+'; no es la identidad del candidato actual. No hay recibo candidate-bound actual de esta verificación. El gate de mapa no afirma cierre global del backend.</footer>'
 progress_html=page('BAGO · Progreso del mapa de fronteras',home)
 HTML.write_text(map_html,encoding='utf-8',newline='\n')
 (HTML.parent/'BACKEND_MATURITY_RADAR_20261006.html').write_text(radar_html,encoding='utf-8',newline='\n')
 (HTML.parent/'BACKEND_PROGRESS_20261006.html').write_text(progress_html,encoding='utf-8',newline='\n')

def check():
 d=json.loads(DATA.read_text(encoding='utf-8')); h=HTML.read_text(encoding='utf-8'); embedded=json.loads(re.search(r'<script id="boundary-graph-data" type="application/json">(.*?)</script>',h,re.S).group(1))
 radar_html=(HTML.parent/'BACKEND_MATURITY_RADAR_20261006.html').read_text(encoding='utf-8');progress_html=(HTML.parent/'BACKEND_PROGRESS_20261006.html').read_text(encoding='utf-8')
 assert 'BACKEND_PROGRESS_20261006.html' in h and 'BACKEND_MATURITY_RADAR_20261006.html' in h
 assert 'BACKEND_BOUNDARY_MAP_20261006.html' in radar_html and 'BACKEND_PROGRESS_20261006.html' in radar_html
 assert 'BACKEND_BOUNDARY_MAP_20261006.html' in progress_html and 'BACKEND_MATURITY_RADAR_20261006.html' in progress_html
 assert radar_html.count('<circle cx="470" cy="355"')==4
 assert all(str(x['score'])+'/4' in radar_html for x in d['scores'])
 assert 'runtime-unbound' in progress_html and 'trabajo' in progress_html.lower()
 assert 'CANDIDATO LOCAL SUCIO' in progress_html and 'No existe recibo del mapa ligado al HEAD y fingerprint de este checkout.' in progress_html
 assert 'BACKEND GLOBAL ABIERTO' in progress_html and 'no afirma cierre global del backend' in progress_html
 print('PASS: three linked pages; radar values sourced from sidecar; progress dashboard includes open work and historical evidence labels.')
 assert embedded['edges']==d['source_edges'] and embedded['nodes']==d['architecture_files'] and embedded['views']==d['architecture_views']
 ids={n['id'] for n in d['architecture_files']}; seen=set()
 for n in d['architecture_files']: assert digest(n['path'])==n['sha256'],n['path']
 for e in d['source_edges']:
  assert e['id'] not in seen;seen.add(e['id']);assert e['from_node'] in ids and e['to_node'] in ids
  assert e['type'] in {'TRANSPORT','ROUTE','LOOKUP','BIND','CONSTRUCT','AUTHORIZE','REGISTER','EXECUTE','CALLBACK','PREPARE'}
  assert e['status'] in {'OBSERVED','OWNER_PENDING','HYPOTHESIS'}
  if e['status']=='HYPOTHESIS':assert e['source'] is None;continue
  s=e['source'];assert digest(s['path'])==s['sha256'];lines=(ROOT/s['path']).read_text(encoding='utf-8').splitlines();assert 1<=s['line_start']<=s['line_end']<=len(lines);assert lines[s['line_start']-1].strip()==s['excerpt'];assert e['symbol']
 assert d['architecture_graph']['unique_files']==len(ids)
 assert d['architecture_graph']['observed_relations']==sum(e['status']!='HYPOTHESIS' for e in d['source_edges'])
 by={e['id']:e for e in d['source_edges']}
 for v in d['architecture_views']:
  endpoint=v['expected_endpoint']
  for l in v['links']:
   e=by[l['edge_id']]
   if e['type']=='ROUTE' and endpoint:
    assert e['endpoint']['method']==endpoint['method'],(v['id'],'HTTP_METHOD_MIX',e['id'])
    if e['endpoint']['path']!='*':assert e['endpoint']==endpoint,(v['id'],'ROUTE_MIX',e['id'])
   if endpoint and e['source'] and e['from_node'] in {'jobs','session','context','providers','evidence'}:
    source=e['source'];tree=ast.parse((ROOT/source['path']).read_text(encoding='utf-8'))
    enclosing=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.lineno<=source['line_start']<=n.end_lineno]
    assert enclosing,(v['id'],'CALLER_MISSING',e['id'])
    function=max(enclosing,key=lambda n:n.lineno).name
    assert function==endpoint['handler_function'] or function.startswith('_'),(v['id'],'HANDLER_ENDPOINT_MIX',e['id'],function,endpoint['handler_function'])
  boxes={n['id']:n for n in v['nodes']};adj={i:set() for i in boxes};segments=[]
  for l in v['links']:
   e=by[l['edge_id']];a,b=boxes[l['from_instance']],boxes[l['to_instance']]
   assert (a['file_id'],b['file_id'])==(e['from_node'],e['to_node'])
   adj[a['id']].add(b['id']);adj[b['id']].add(a['id'])
   for p,q in zip(l['points'],l['points'][1:]):
    assert p[0]==q[0] or p[1]==q[1]
    for n in boxes.values():
     x,y,w,t=n['x'],n['y'],n['width'],n['height']
     crosses=(p[0]==q[0] and x<p[0]<x+w and max(min(p[1],q[1]),y)<min(max(p[1],q[1]),y+t)) or (p[1]==q[1] and y<p[1]<y+t and max(min(p[0],q[0]),x)<min(max(p[0],q[0]),x+w))
     assert not crosses,(v['id'],'NODE_TRAVERSAL',l['edge_id'],n['id'])
    segments.append((l['edge_id'],p,q))
  pending=[next(iter(boxes))];connected=set()
  while pending:
   cur=pending.pop()
   if cur not in connected:connected.add(cur);pending.extend(adj[cur]-connected)
  assert len(connected)==len(boxes),(v['id'],'DISCONNECTED')
  intersections=0
  for i,(eid,p,q) in enumerate(segments):
   for fid,r,s in segments[i+1:]:
    if eid==fid:continue
    # Positive-length collinear overlap or perpendicular intersection, including endpoint touches.
    pv=p[0]==q[0];rv=r[0]==s[0]
    if pv==rv:
     hit=(p[0]==r[0] and max(min(p[1],q[1]),min(r[1],s[1]))<min(max(p[1],q[1]),max(r[1],s[1]))) if pv else (p[1]==r[1] and max(min(p[0],q[0]),min(r[0],s[0]))<min(max(p[0],q[0]),max(r[0],s[0])))
    else:
     vert0,vert1,horiz0,horiz1=(p,q,r,s) if pv else (r,s,p,q)
     hit=min(horiz0[0],horiz1[0])<=vert0[0]<=max(horiz0[0],horiz1[0]) and min(vert0[1],vert1[1])<=horiz0[1]<=max(vert0[1],vert1[1])
    intersections+=int(hit)
  assert intersections==0,(v['id'],'EDGE_INTERSECTIONS',intersections)
  print('PASS view',v['id'],': endpoint/method/AST caller consistent; connected;',len(v['nodes']),'instances; 0 node traversals; 0 edge intersections/overlaps')
 assert any(l['edge_id']=='E05' for l in d['architecture_views'][0]['links'])
 if shutil.which('node'):
  js=re.findall(r'<script>\s*(.*?)</script>',h,re.S)[0]
  stub='''const els={};function el(id){return els[id]||(els[id]={id,value:'',textContent:'',innerHTML:'',options:[],setAttribute(k,v){this[k]=v},append(o){this.options.push(o);if(!this.value)this.value=o.value}})};global.document={getElementById:el,createElement:()=>({})};el('boundary-graph-data').textContent=JSON.stringify('''+json.dumps(embedded)+''');'''
  tail="for(const o of el('path-choice').options){el('path-choice').value=o.value;el('path-choice').onchange();if(!el('funnel').innerHTML.includes('data-node-id'))throw Error(o.value)};console.log('PASS: inline JS smoke executed for all '+el('path-choice').options.length+' views using minimal DOM (supplemental check).');"
  result=subprocess.run(['node'],input=stub+js+tail,text=True,capture_output=True)
  assert result.returncode==0,result.stderr;print(result.stdout.strip())
 else:print('NOT_RUN inline JS execution: Node unavailable; geometry/data checks passed independently.')
 visual_script=ROOT/'scripts'/'verify_backend_boundary_visual.cjs'
 assert visual_script.is_file(),f'Visual browser verifier missing: {visual_script}'
 visual=subprocess.run(['node',str(visual_script),str(HTML)],cwd=ROOT/'backend',text=True,capture_output=True)
 assert visual.returncode==0,visual.stdout+'\n'+visual.stderr
 print(visual.stdout.strip())
 print('PASS: embedded inventory, unique IDs, source hashes, line excerpts, types, statuses and counts;',len(ids),'files;',len(seen),'relations. Chromium visual DOM/layout check executed.')

if __name__=='__main__':
 if '--check' in sys.argv:check()
 else:build();check()
