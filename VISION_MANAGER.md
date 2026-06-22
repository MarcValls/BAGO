# Visión: BAGO Control Plane / Manager

> Versión de visión textual para el nuevo Manager de BAGO.  
> El chat sigue siendo la pieza central; el Manager es su panel de instrumentos.

---

## 1. Filosofía general

- **Plano de control único.** Una sola ventana/módulo desde el que gobernar instalaciones, piezas, conexiones, releases y trazabilidad de BAGO.
- **El chat como centro operativo.** El Manager no sustituye al chat; lo equipa. Desde el chat se abre el Manager en contexto; desde el Manager se lanzan acciones que generan mensajes o tareas en el chat activo.
- **Local-first, offline-capable.** Funciona con datos locales/caché. Cuando hay backend (`bago node status --json`, API local, Electron), se sincroniza.
- **Sesión/instalación como unidad de trabajo.** Todo gira en torno a "qué instalación estás tocando" y "qué piezas tiene conectadas".
- **Acción reversible y auditada.** Cada `attach`, `detach`, `switch`, `release` o cambio de política genera una entrada en el ledger con evidencia.

---

## 2. Arquitectura visual

### Layout base

```
┌─────────────────┬────────────────────────────────────────────┐
│  BAGO Control   │  Topbar: vista + search + acciones         │
│  Plane          ├────────────────────────────────────────────┤
│                 │                                            │
│  [Navegación]   │  VISTA ACTIVA                              │
│                 │  (dashboard / instalaciones / patchbay...) │
│  [Estado local] │                                            │
│                 │                                            │
└─────────────────┴────────────────────────────────────────────┘
```

- **Sidebar izquierda** (sticky, ~280-300 px, glassmorphism): marca, navegación principal, footer de salud local.
- **Área principal**: topbar fija + scroll interno de la vista activa.
- **Paleta**: fondo `#050813`, paneles `#0f172a`, brand `#7c8cff`, cyan `#22d3ee`, ok `#34d399`, warn `#fbbf24`, danger `#fb7185`.

### Navegación principal (rooms)

1. **Dashboard** — resumen operativo.
2. **Instalaciones** — inventario y estado de installs.
3. **Patchbay** — matriz de conexiones instalación ↔ pieza.
4. **Nodos** — grafo topológico completo.
5. **Piezas** — PieceStore/catalogado.
6. **Releases** — canales, bundles, jobs.
7. **Auditoría** — ledger y evidence.
8. **Salud** — probes, supervisor, runtime.
9. **Volver al Chat** — enlace de escape al chat central.

---

## 3. Módulos detallados

### 3.1 Dashboard

Propósito: saber el estado de BAGO de un vistazo.

- **KPIs en cards** (4 stats): Instalaciones, Piezas, Release actual, Auditoría.
- **Instalaciones prioritarias**: listado con tabs (Todas / Connected / Shadow / Beta / Locked). Click abre detalle y grafo rápido.
- **Grafo rápido mini**: instalación seleccionada en el centro con sus piezas/connector principales.
- **Releases disponibles + Auditoría reciente** en dos columnas inferiores.

### 3.2 Instalaciones

Propósito: gestionar cada copia física/lógica de BAGO.

Cada instalación muestra:
- **ID**, **path**, **versión**, **modo** (stable / beta / shadow / local).
- **Estado**: connected, disconnected, locked, read-only, writable overlay.
- **Badges**: supervisor vivo/muerto, tag, perfil.
- **Acciones por fila**:
  - `Conectar/Desconectar`
  - `Switch release`
  - `Copiar estado`
  - `Abrir en terminal`
  - `Eliminar` (con confirmación y evidencia)

Tabs: Todas / Stable / Beta / Disconnected / Local only.

**Detalle lateral** al seleccionar:
- KV: path, versión, modo, supervisor, último sync, política activa.
- Grafo de piezas conectadas.
- Acciones rápidas: reload, detach all, open folder, copy state.

### 3.3 Patchbay

Propósito: decidir **qué pieza está conectada a qué instalación y en qué modo**.

Vista: **matriz**.

- Filas = instalaciones.
- Columnas = piezas (tools, agents, skills, knowledge, repos).
- Celda = estado de conexión:
  - **connected** (verde): pieza activa, escribe/lee.
  - **shadow** (amarillo): visible pero no afecta, modo simulado.
  - **read-only** (cyan): solo lectura.
  - **locked** (rojo): bloqueada, no se puede modificar.
  - **detached / empty** (gris): no conectada.

Interacciones:
- Click en celda abre **picker de modo** (`connected`, `shadow`, `read-only`, `locked`, `detach`).
- Doble click o botón derecho: menú contextual con acciones (`attach`, `detach`, `set policy`, `view evidence`).
- Filtros: por tipo de pieza, por modo, por instalación, por búsqueda.
- **Acciones masivas**: seleccionar varias celdas y aplicar modo a todas.

### 3.4 Nodos

Propósito: ver la topología completa de BAGO.

- **Grafo interactivo** SVG/Canvas:
  - Nodos: instalaciones (core), tools, agents, skills, repos, knowledge stores.
  - Aristas: conexiones con color según modo (`connected`, `shadow`, `locked`).
- **Tabs**: Overview / Matrix / Pieces / Connectors / Evidence.
- Al hacer click en un nodo, abre panel de detalle.
- Botón “Abrir en pestaña” para grafo grande.

### 3.5 Piezas

Propósito: inventario de todo lo que BAGO puede usar.

- Listado con: id, tipo, scope, versión, hash, store path.
- Badges de tipo: `tool`, `agent`, `skill`, `knowledge`, `repo`, `connector`.
- Acciones: `attach to install`, `detach`, `update`, `view source`, `delete`.
- Filtros por tipo y scope.

### 3.6 Releases

Propósito: gestionar versiones y despliegues.

- Canales: **stable**, **beta**, **legacy**.
- Cada release card: versión, notas, bundle ZIP, checksum SHA256, manager `.exe`.
- Badges: `Stable`, `Beta`, `Legacy`, `con warnings`.
- Acciones: `instalar`, `crear instalación aparte`, `rollback`, `ver contrato`.
- **Jobs de release**: estado de operaciones de release en curso.

### 3.7 Auditoría

Propósito: trazabilidad completa.

- **Ledger cronológico**: timestamp, acción, detalle, instalación, pieza, usuario/sesión.
- Acciones típicas: `attach`, `detach`, `install`, `uninstall`, `switch`, `sync`, `claim validated`.
- Filtros por instalación, por pieza, por tipo de acción.
- Cada entrada puede expandirse para ver evidence/claims asociados.

### 3.8 Salud

Propósito: diagnóstico operativo.

- Estado del supervisor, probes, compatibilidad, modo runtime.
- KPIs: instalaciones OK, piezas OK, conectores OK, claims passed/failed.
- Botón de refresh y exportar diagnóstico.

---

## 4. Modelo mental de datos

- **Installation**: una copia de BAGO en disco (path, version, mode, supervisor, tag).
- **Piece**: un componente reusable (tool, agent, skill, knowledge, repo).
- **Connector**: la relación entre una Installation y una Piece, con un modo.
- **Patch/Matrix**: la vista tabular de todos los connectors.
- **Release**: una versión descargable con su bundle y checksum.
- **Claim/Evidence**: aserciones verificables sobre el estado.
- **Ledger**: registro inmutable de acciones.

---

## 5. Flujos de interacción importantes

### Añadir una pieza a una instalación

1. Usuario va a **Patchbay**.
2. Encuentra la celda instalación × pieza.
3. Click → picker → selecciona `connected`.
4. UI muestra spinner, luego celda verde.
5. Se genera entrada en **Auditoría** y, si aplica, evidence en **Nodos/Evidence**.

### Cambiar de release

1. Usuario va a **Releases** o a detalle de **Instalación**.
2. Selecciona release objetivo.
3. Acción `Install` o `Install aparte`.
4. Si es aparte, se crea nueva instalación en modo beta/shadow.
5. Se registra en auditoría.

### Desde el Chat al Manager

- En el chat, un mensaje puede incluir un botón/contexto: “Abrir en gestor → inst-X / pieza-Y”.
- El Manager recibe contexto y abre directamente la vista/filtro correspondiente.

---

## 6. Decisiones de diseño recomendadas

1. **Un Manager, no muchos.** Reunir Control, Patchbay, Instalaciones, Nodos, Piezas, Releases y Auditoría en un mismo plano de control.
2. **Patchbay como vista estrella.** Es la más útil: todo el gobierno de BAGO pasa por decidir quién está conectado a qué y en qué modo.
3. **Matriz primero, grafo después.** El grafo es útil para explorar, pero el día a día se hace en la matriz.
4. **Cada acción genera evidence.** No solo logs; cada cambio de conexión/release debe poder dejar un claim verificable.
5. **Responsive hasta tablet.** En móvil, convertir sidebar en rail de iconos y matriz en lista por instalación.
6. **Tecnología:** React + Vite (como `ui-react`), con un backend API local (`bago node status --json`) y Electron para acceso a disco.

---

## 7. Estructura de carpetas sugerida

```
ui-control-plane/
├── src/
│   ├── App.jsx                 # shell + routing de vistas
│   ├── api.js                  # bago node status, releases, ledger
│   ├── hooks/
│   │   ├── useNodeStatus.js
│   │   ├── usePatchMatrix.js
│   │   ├── useInstallations.js
│   │   ├── usePieces.js
│   │   └── useReleases.js
│   ├── views/
│   │   ├── Dashboard.jsx
│   │   ├── Installations.jsx
│   │   ├── Patchbay.jsx
│   │   ├── Nodes.jsx
│   │   ├── Pieces.jsx
│   │   ├── Releases.jsx
│   │   └── Audit.jsx
│   ├── components/
│   │   ├── Sidebar.jsx
│   │   ├── Topbar.jsx
│   │   ├── KPIStat.jsx
│   │   ├── InstallCard.jsx
│   │   ├── MatrixCell.jsx
│   │   ├── NodeGraph.jsx
│   │   ├── PieceBadge.jsx
│   │   └── AuditEntry.jsx
│   └── styles.css
```

---

*Documento generado para la iteración de diseño del Manager de BAGO.*
