from __future__ import annotations
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from .config import Settings
from .repository import MemoryRepository

S=Settings.from_env(); R=MemoryRepository(S); R.initialize()
I=("Memoria local cerrada y auditable. Consulta get_context al iniciar tareas. Prioriza estado y memorias confirmadas. "
   "No conviertas inferencias en canon. Para escribir: memory_propose, aprobación explícita y memory_commit. "
   "Depreca en lugar de borrar. No solicites rutas externas ni ejecutes comandos.")
mcp=FastMCP("IA Memoria Local",instructions=I,host=S.host,port=S.port,json_response=True)
RO=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False)
WA=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=False,openWorldHint=False)
WS=ToolAnnotations(readOnlyHint=False,destructiveHint=True,idempotentHint=False,openWorldHint=False)

@mcp.tool(annotations=RO)
def system_status()->dict: """Comprueba raíz, índice y contadores."""; return R.system_status()
@mcp.tool(annotations=RO)
def list_projects()->list[dict]: """Lista proyectos."""; return R.list_projects()
@mcp.tool(annotations=RO)
def get_project_state(project_id:str)->dict: """Recupera estado, memorias, conflictos y enlaces."""; return R.get_project_state(project_id)
@mcp.tool(annotations=RO)
def get_context(project_id:str,query:str,limit:int=8)->dict: """Construye contexto mínimo para una tarea."""; return R.get_context(project_id,query,limit)
@mcp.tool(annotations=RO)
def memory_search(query:str,project_id:str='',limit:int=10,include_inferred:bool=False)->dict: """Busca documentos y memorias."""; return R.search(query,project_id,limit,include_inferred)
@mcp.tool(annotations=RO)
def memory_read(relative_path:str,start_line:int=1,max_lines:int=200)->dict: """Lee un archivo textual dentro de la raíz."""; return R.read_file(relative_path,start_line,max_lines)
@mcp.tool(annotations=RO)
def list_pending_proposals(project_id:str='')->list[dict]: """Lista propuestas pendientes."""; return R.list_pending_proposals(project_id)
@mcp.tool(annotations=WA)
def create_project(project_id:str,title:str,purpose:str)->dict: """Crea un proyecto gobernado."""; return R.create_project(project_id,title,purpose)
@mcp.tool(annotations=WA)
def memory_propose(project_id:str,statement:str,category:str,source_reference:str,proposed_class:str='MEM_INFERRED',scope:str='project',authority_level:int=50,confidence:float=.75)->dict:
    """Registra una memoria candidata sin activarla."""; return R.propose_memory(project_id,statement,category,source_reference,proposed_class,scope,authority_level,confidence)
@mcp.tool(annotations=WA)
def memory_commit(proposal_id:str,approved_by:str,final_class:str='MEM_CONFIRMED',supersedes:str='',contradicts:str='')->dict:
    """Confirma una propuesta aprobada."""; return R.commit_memory(proposal_id,approved_by,final_class,supersedes,contradicts)
@mcp.tool(annotations=WS)
def memory_deprecate(memory_id:str,reason:str,superseded_by:str='')->dict: """Retira vigencia sin borrar historia."""; return R.deprecate_memory(memory_id,reason,superseded_by)
@mcp.tool(annotations=WA)
def create_project_link(source_project:str,target_project:str,concept:str,authority:str,source_reference:str,conditions:str='')->dict:
    """Crea un enlace explícito entre proyectos."""; return R.create_link(source_project,target_project,concept,authority,source_reference,conditions)
@mcp.tool(annotations=WA)
def record_event(project_id:str,event_type:str,summary:str,evidence:str='')->dict: """Registra acción, fallo, verificación o cierre."""; return R.record_event(project_id,event_type,summary,evidence)
@mcp.tool(annotations=WA)
def reindex_documents()->dict: """Reconstruye el índice documental."""; return R.reindex()

def main()->None: mcp.run(transport=S.transport)
if __name__=='__main__': main()
