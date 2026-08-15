# Mapa de estilos y navegación de la UI canónica

La interfaz activa es `frontend/src/app/ControlPlane.tsx` + `frontend/src/features/sections.tsx`.
Cada destino ocupa la superficie principal; los drawers quedan reservados para selección/inspección o autenticación.

| Pantalla | Entrada | Estilo principal | Acción primaria |
|---|---|---|---|
| Inicio | Ctrl+1 | `components/009-home.css`, `015-chat-panel-base.css` | Iniciar o continuar conversación |
| Chat | Ctrl+2 | `012-chat.css`, `015-chat-panel-base.css` | Enviar mensaje / cambiar modelo |
| Workspace | Ctrl+3 | `080-workspace-explorer-children.css`, `081-workspace-inspector-empty-state.css` | Elegir, explorar y editar archivos |
| Contexto | Ctrl+4 | `086-contexto-cinco-areas-editables-sepa.css`, `054-contexto-de-trabajo-superficie-nuev.css` | Preparar y certificar contexto |
| Pipeline | Ctrl+5 | `030-pipeline.css`, `087-pipeline-una-superficie-de-decision.css`, `100-pipeline-laboratory.css` | Crear y ejecutar planes |
| Evidencia | Ctrl+6 | `032-evidence.css`, `069-changes.css`, `071-output.css` | Revisar claims, recibos y resultados |
| Operaciones | Ctrl+7 | `034-system.css`, `042-system-tabs.css`, `044-provider-list.css` | Configurar runtime, router y proveedores |
| Agentes | Ctrl+8 | `101-full-destinations.css` + estilos del editor | Editar, guardar, probar y eliminar agentes |
| Intérprete | Ctrl+9 | `101-full-destinations.css` + estilos de interpretación | Interpretar una entrada y cancelar ejecuciones |
| Capacidades | Ctrl+Shift+C | `029-grafo-anatomia-de-capacidades-proye.css`, `capability-redesign.css` | Consultar contratos y paquetes |
| Herramientas | Ctrl+Shift+T | `101-full-destinations.css`, `tools-panel.css` | Consultar catálogo y ejecutar comandos |

## Reglas de composición

- El sidebar contiene una única entrada por destino.
- `Pipeline` y `Agentes` ya no se repiten en la botonera inferior del sidebar.
- `Capacidades`, `Agentes`, `Intérprete` y `Herramientas` son destinos completos, no sidebars informativos.
- El inspector/drawer solo aparece para una selección concreta y siempre tiene una acción de cierre.
- Los tokens globales viven en `styles/tokens.css`; las reglas de layout común viven en `styles/components/003-app-shell.css` y `004-section-3.css`.
