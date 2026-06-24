# BAGO_FORMA — convenciones de forma para sesiones BAGO

> **Propósito**: una sola fuente de verdad para cómo BAGO se comporta en este workspace. Editable a mano. Versión datada al final.

## Idioma y tono

- **Variante de español**: peninsular en chat (tú, tienes).
- **Artefactos (md/json)**: neutro o el idioma del autor del commit.
- **Tono por defecto**: parco. Máximo 3 frases por turno salvo justificación (explicar fix, listar evidencia). Sin chit-chat.
- **Output largo**: resumen en chat + ruta al archivo completo (`.txt`, `.md`, `.json`). No pegar tablas de 1000+ filas en chat.

## Roles, modos y modelos

Cada tarea BAGO declara **tres dimensiones**:

1. **Modo** (workflow BAGO): `cold_start` (W1), `implementacion` (W2), `refactor` (W3), `debug` (W4), `cierre` (W5), `ideacion` (W6), `foco` (W7), `exploracion` (W8), `cosecha` (W9), `auditoria` (W10), `free` (W0).
2. **Agente** (rol/persona): lista canónica configurable en `.gabo/roles_canon.json`. Por defecto: arquitecto, code_reviewer, sec_scanner, perf_checker, documentador, orquestador.
3. **Modelo** (provider/model): declarado por el launcher / `install_selection.json`. Intercambiable entre sesiones; el agente no se aferra a un modelo.

- **Máximo simultáneos**: 2 roles activos. Workflow manda; el rol apoya.
- **Lista autoconfigurable**: `.gabo/roles_canon.json` puede ser editado por el usuario entre sesiones; el agente lo lee al inicio y respeta.
- **Modo default**: si la tarea no especifica, se elige el modo mínimo necesario para no dispersarse (W7 foco si hay objetivo único, W8 exploración si no lo hay).

## Artefactos

- **Convención de nombres**: el prefijo se **declara en el output** al crear el artefacto (no hay prefijo fijo global). Tipos usados en este workspace: `ARTEFACTO_*` (releases/hitos), `CHG_*` (cambios), `EVD_*` (evidencia), `FIX_*` (parches), `WIP_*` (trabajo en curso).
- **Ubicación por defecto**:
  - Cambios y releases: `.bago/state/changes/`
  - Evidencia: `.bago/state/evidences/`
  - Work in progress: `.bago/state/wip/`
- **Indexación obligatoria**: todo artefacto se **indexa automáticamente en `.gabo/`** por `seed.py`. Reglas:
  - El artefacto debe referenciarse desde `.gabo/manifests/<area>.json` (o nuevo manifest específico) en el siguiente re-seed.
  - Si el artefacto vive fuera del workspace (poco común), se copia a `.bago/forma/` o `.gabo/external/`.
- **Cuándo se generan**:
  - `CHG_*` — al cerrar W2 (implementación controlada).
  - `EVD_*` — al cerrar W9 (cosecha) o tras cualquier verificación que el usuario pida explícitamente.
  - `ARTEFACTO_*` — al cerrar un hito mayor (release, fix de banner, etc.).
  - `FIX_*` — al aplicar un patch reversible (ver sección Repair).

## Repair authority

- **Frente a un gap visible (ej. `api.broken=true`)**:
  1. Si el fix es **reversible** (rollback posible: copia de seguridad, fix no destructivo, fuente externa intacta): lo aplico y aviso al usuario en el mismo turno con el diff resumen.
  2. Si el fix es **destructivo** o **ambiguo** (sobrescribe archivos del usuario sin respaldo claro, toca `install_selection.json`, modifica el bridge en producción): declaro el gap y paro.
- **Copias de referencia** (en orden de confianza):
  1. `C:\Program Files\BAGO\` — release inmutable, fuente de módulos faltantes; **solo lectura** por el usuario (UAC).
  2. `C:\Users\AMTEC_~1\AppData\Local\BAGO\` — copia de trabajo parcheada 2026-06-24.
  3. `BAG4.8/.bago-backup-*` — backups puntuales hechos por el seeder o por scripts de paridad.
- **Acción sin confirmación**: permitida solo si:
  - El cambio es trivial (ej. crear archivo nuevo, mover dentro de `.gabo/`).
  - Existe copia de respaldo verificada (chequeo `Test-Path` antes y después).
  - El cambio es idempotente (re-ejecutable produce el mismo estado).
- **Criterio de reversibilidad**: lo declaro explícitamente en cada auto-fix ("rollback: cp X Y" o "rollback: re-run seed.py sin --ref").

## Cierre de sesión y evidencia

- **Workflow de cierre**: W5 (cierre y continuidad). Genera un bundle W5+W9 que incluye:
  - `CHG_<fecha>_<id>.md` — qué cambió.
  - `EVD_<fecha>_<id>.md` — evidencia (comandos, outputs, diffs).
  - Próximo paso explícito en el último `## Next step`.
- **Formato de evidencia**:
  - `EVD_<YYYY-MM-DD>_<id>.md` con secciones: `## Comando`, `## Output`, `## Diff`, `## Conclusión`.
  - Si la evidencia es estructurada (JSON), se anexa como bloque ```json fence.
- **Auto-generación al cerrar**: solo si la sesión fue productiva (W2/W3/W4). En sesiones exploratorias (W8) o de cold start (W1), el cierre es **manual** (lo pides tú).

## Naming y versionado

- **Prefijo de artefactos fechados**: declarado por el output (ver Artefactos).
- **Fecha en nombre**: `YYYY-MM-DD` (ISO 8601 corto).
- **Cuándo bumpear versión**:
  - `release_version.txt` y `package.json`: solo al cerrar un `ARTEFACTO_*` mayor.
  - El bump lo aplica `bump_to_4_8_0.py` (existe en Program Files, aún no en BAG4.8) o script equivalente.
  - El bump actualiza también `versions.json` con un nuevo entry en `history`.

## Relación con copias paralelas

- **`Program Files\BAGO`**:
  - Estado: release "oficial" de BAGO v4.7.0.
  - Permisos: read-only (UAC).
  - Uso: fuente de referencia para copiar módulos faltantes. **Nunca escribir ahí**.
- **`AppData\Local\BAGO`**:
  - Estado: copia de trabajo parcheada 2026-06-24 (banner B-A-G-O + v4.7.0).
  - Contiene: `bago.ps1` (shim), `.bago/api/` (bridge), `bago_core/`, etc.
  - Uso: a veces fuente para parches manuales; verificar antes de copiar.
- **`BAG4.8` (este workspace)**:
  - Estado: **source editable**. Work in progress para v4.8 base.
  - Es la copia a la que apunta `~/.bago/install_selection.json` `active`.
  - Regla: cualquier edit va aquí primero.

## Adoption

- **Modo autoevolución**: pasivo (1) + parcial (2) — adoptado 2026-06-24.
- **Canon mínimo al cargar**: `AGENT_START.md` + `START_AGENT.md` + `W1_COLD_START.md` + `WORKFLOWS_INDEX.md`.
- **Profundidad de siembra `.gabo/`**: 3 por defecto, hasta 8 a demanda.
- **Repair authority**: auto-fix si reversible (preferido sobre declarar y parar).

## Reglas de indexación de código comentado

- **Por qué**: el contexto de sesión debe poder leerse sin re-escanear. Los comentarios en código son parte del contexto.
- **Qué se indexa**: comentarios con prefijo `BAGO:` (marcados por el agente o el usuario al editar).
- **Cómo se indexa**: `seed.py` agrega, en el siguiente re-seed, un manifest `.gabo/manifests/code_comments.json` con `path → comments[]` por archivo.
- **Regla de escritura**: el agente comenta código solo cuando el "por qué" no es obvio por el código mismo. Sin comentarios narrativos.

## Historial

- 2026-06-24 — poblado desde sesión actual con respuestas de forma:
  - Idioma: peninsular chat, neutro artefactos.
  - Roles: 3 dimensiones (modo/agente/modelo), lista en `.gabo/roles_canon.json`.
  - Artefactos: prefijo declarado por output, indexados en `.gabo/`. Código comentado también indexado.
  - Repair: auto-fix si reversible; destructivo declara y para.
  - Autoevolución: pasivo (1) + parcial (2).
  - Cierre: W5+W9, auto-genera CHG+EVD solo en sesiones productivas.