# Primeros pasos con BAGO v3.3.0

Esta guía te lleva desde la instalación hasta tu primera sesión de trabajo real.

---

## Requisitos previos

- **Python 3.9+** (solo stdlib estándar — sin dependencias externas)
- **Git** (opcional, pero recomendado)
- Un agente de IA: GitHub Copilot CLI, Claude Code, o cualquier LLM con acceso a archivos

---

## Instalación

### Opción A — Desde el pendrive BAGO (recomendada si tienes el dispositivo)

```bash
bash /Volumes/BAGO/start.sh
# O bien doble-click en /Volumes/BAGO/INICIAR_BAGO.command
```

### Opción B — Desde GitHub

```bash
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
pip install -e .          # instala el script de consola 'bago'
```

---

## Paso 1 — Verificar la instalación

```bash
bago validate
```

Salida esperada:
```
GO manifest
GO state
GO pack
```

Si ves `KO`, ejecuta `bago health` para diagnóstico.

---

## Paso 2 — Comprobar la salud del sistema

```bash
bago health
```

BAGO mide 5 dimensiones de salud:

| Dimensión | Qué mide |
|-----------|---------|
| Integridad | Consistencia entre `pack.json` y el validador |
| Disciplina workflow | Uso de workflows por sesión |
| Captura de decisiones | Media de decisiones registradas por sesión |
| Estado stale | Sin tareas o estado obsoleto |
| Consistencia inventario | El inventario declarado coincide con la realidad |

Una instalación nueva muestra `initializing`. Tras algunas sesiones verás `87/100 🟢`.

---

## Paso 3 — Ver las ideas disponibles

```bash
bago ideas
```

Muestra las mejoras e iniciativas priorizadas disponibles para tu sesión. Es el punto de partida más productivo si no tienes un objetivo predefinido.

---

## Paso 4 — Iniciar el agente de IA con contexto BAGO

Abre `.bago/AGENT_START.md` — es el punto de entrada para cualquier agente de IA. Proporciona:
- El workflow activo
- La tarea y estado del sprint actuales
- Los protocolos operacionales

**Prompt para tu agente de IA:**
```
Lee .bago/AGENT_START.md primero, luego ayúdame a implementar [feature].
```

---

## Paso 5 — Elegir un workflow

```bash
bago workflow
```

O elige manualmente según el tipo de tarea:

| Si quieres... | Usa |
|---------------|-----|
| Explorar libremente (sin estructura) | `W0 · Sesión libre` |
| Empezar un proyecto nuevo | `W1 · Boot frío` |
| Implementar una feature | `W2 · Implementación controlada` |
| Refactorizar código existente | `W3 · Refactor sensible` |
| Depurar un problema complejo | `W4 · Debug multicausa` |
| Cerrar una sesión correctamente | `W5 · Cierre y continuidad` |
| Generar nuevas ideas | `W6 · Ideación aplicada` |
| Mantener foco en un solo objetivo | `W7 · Foco de sesión` |
| Explorar algo nuevo | `W8 · Exploración` |
| Capturar artefactos / decisiones | `W9 · Cosecha` |
| Auditar afirmaciones sin evidencia | `W10 · Auditoría de sinceridad` |

---

## Paso 6 — Trabajar con disciplina BAGO

Durante una sesión:

1. **Inicio**: `bago hello` → muestra contexto y siguiente paso sugerido
2. **Trabajo**: El agente registra decisiones y artefactos en `.bago/state/`
3. **Control**: `bago health` → comprobación del sistema a mitad de sesión
4. **Ideas**: `bago ideas` → mejoras priorizadas para implementar

---

## Paso 7 — Cerrar la sesión correctamente

```bash
# Capturar decisiones y artefactos
bago cosecha

# Auditoría completa de la sesión
bago audit --json

# Validar que todo es consistente
bago validate
```

---

## Paso 8 — Seguimiento del trabajo

Después de varias sesiones:

```bash
bago audit          # revisar el histórico de sesiones
bago map            # mapa del workspace
bago status         # estado del flujo activo
```

---

## Patrones de uso frecuentes

### Rutina diaria

```bash
bago hello              # arranque — estado + siguiente paso
bago ideas              # elegir el foco del día
# ... trabajar con el agente de IA ...
bago cosecha            # cierre — capturar decisiones
bago validate           # verificación final
```

### Cuando algo va mal

```bash
bago health             # diagnóstico general
bago doctor             # diagnóstico con sugerencias
bago doctor --fix       # autofix para problemas comunes
bago sincerity          # detecta divergencia doc ↔ comportamiento real
```

### Antes de un commit o release

```bash
bago consistency        # guard anti-deriva
bago validate           # integridad del pack
bago sincerity          # ninguna afirmación sin evidencia
bago health             # score final
```

---

## Estructura de archivos

```
.bago/
├── AGENT_START.md          ← Punto de entrada para el agente IA
├── pack.json               ← Manifiesto del sistema
├── state/                  ← Estado en tiempo de ejecución (gitignored)
│   ├── global_state.json   ← Estado actual del sistema
│   ├── sessions/           ← Registros de sesión
│   ├── changes/            ← Artefactos BAGO-CHG
│   └── evidences/          ← Archivos de evidencia
├── state.example/          ← Plantillas de instalación limpia (versionadas)
├── tools/                  ← Utilidades Python (54 tools en v3.3.0)
├── workflows/              ← Protocolos operacionales W0–W10
└── core/                   ← Bucle autónomo + motor core
```

---

## Resolución de problemas

**`KO version mismatch`**: La versión en `pack.json` y `bago_version` en `global_state.json` deben coincidir.

**`Health: initializing`**: Normal en una instalación nueva. Tras la primera sesión completa transiciona a `stable`.

**`Stale task detected`**: Hay una tarea en `pending_w2_task.json` con más de 3 días de antigüedad. Limpia con `bago task --clear`.

**Agente de IA ignora BAGO**: Indica explícitamente al agente: `"Lee .bago/state/global_state.json y continúa desde donde lo dejamos"`.

---

*Más documentación en `docs/` — ver `ARQUITECTURA.md`, `COMMANDS.md` y `SECUENCIAS.md` como referencia.*

*BAGO v3.3.0 · Mayo 2026 · github.com/MarcValls/BAGO*
