# MCP · BAGO

Este directorio (`\.bago\mcp\`) contiene la configuración y el servidor MCP (Model Context Protocol) de BAGO.

## Archivos

| Archivo | Propósito |
|---------|-----------|
| `mcp_config.json` | Configuración del servidor MCP |
| `bago_mcp_server.py` | Implementación del servidor MCP |
| `run_bago_mcp.cmd` | Script de arranque del servidor |
| `agent_tool_matrix.json` | Matriz de compatibilidad agente-herramienta |
| `toolbox_catalog.json` | Catálogo de toolboxes disponibles |

## Regla

El servidor MCP expone las herramientas BAGO a clientes MCP-compatibles. No modifica el estado del framework directamente; delega a `bago_core/cli.py`.
