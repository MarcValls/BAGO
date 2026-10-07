# BAGO UI v2.4

Hotfix sobre FRONTENDV2.zip.

Cambios:
- Corregido typecheck del nuevo ContextMenu: `onInspect` acepta `SelectionRecord`, `MouseEvent` y el nivel legacy `summary/detail/raw` sin romper posición.
- Eliminado componente muerto `SelectionInspector.tsx`.
- Limpieza de CSS huérfana: selectores `has-inspector`, `.selection-inspector`, `.inspector-*` y variable `--inspector-bottom-height`.
- Workspace: click normal abre/togglea; click derecho abre menú contextual con metadata (`data-inspect`).
- Corregidos duplicados JSX en Workspace (`onClick` duplicado y botón `Añadir fuente` duplicado).

Validación local:
- `npm run build`: OK
- `npx tsc --noEmit`: OK
- `npm audit`: falla por deuda heredada Vite/esbuild; no se aplica `--force`.
