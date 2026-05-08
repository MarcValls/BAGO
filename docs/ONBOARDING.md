# BAGO — Guía de Onboarding

> De cero a tu primera sesión estructurada en menos de 10 minutos.

---

## ¿Para quién es esta guía?

- Desarrolladores que trabajan con agentes IA (GitHub Copilot, Claude, GPT) y quieren que las sesiones tengan memoria y estructura.
- Equipos que pierden contexto entre sesiones o entre miembros del equipo.
- Cualquiera que haya dicho "el agente no sabe lo que hicimos ayer".

---

## Paso 1 — Instalar BAGO

**Requisitos:** Python 3.9 o superior. Sin dependencias externas.

```bash
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
pip install -e .
```

Verifica la instalación:

```bash
bago validate
# Salida esperada:
# GO manifest
# GO state
# GO pack

bago health
# En instalación limpia: initializing ⚪ (normal — sin historial todavía)
```

> El estado `initializing` es correcto en una instalación nueva. El health score sube con el uso real.

---

## Paso 2 — Entender los 5 comandos esenciales

No necesitas aprender 54 comandos de golpe. Estos 5 cubren el 80% del día a día:

| Comando | Cuándo usarlo |
|---------|--------------|
| `bago health` | Al empezar cualquier sesión — saber el estado del sistema |
| `bago status` | Ver qué flujo está activo, qué tarea está pendiente |
| `bago session open` | Abrir una sesión nueva con contexto estructurado |
| `bago validate` | Después de cualquier cambio — verificar integridad |
| `bago session close` | Al terminar — registrar qué se hizo y dejar estado listo |

---

## Paso 3 — Tu primera sesión

### 3.1 Abre la sesión

```bash
bago session open
```

BAGO cargará el contexto existente (o te guiará para crear uno si es tu primera vez).

### 3.2 Elige un workflow para la sesión

```bash
bago workflow
```

Selector interactivo. Para la mayoría de casos de desarrollo cotidiano:

| Workflow | Cuándo elegirlo |
|----------|----------------|
| `W2 · Controlled Implementation` | Implementar una feature nueva |
| `W3 · Sensitive Refactor` | Refactorizar código crítico |
| `W4 · Multi-cause Debug` | Investigar un bug complejo |
| `W6 · Applied Ideation` | Explorar y priorizar ideas |
| `W0 · Free Session` | Exploración sin estructura |

### 3.3 Trabaja con tu agente IA

Con la sesión abierta y el workflow activo, tu agente IA (Copilot, Claude, etc.) puede leer el estado BAGO y saber exactamente:
- En qué proyecto y fase estás
- Qué decisiones ya están tomadas (y no hay que revisar)
- Qué está pendiente
- Con qué protocolo hay que trabajar

### 3.4 Cierra la sesión correctamente

```bash
bago session close
```

Genera el informe de cierre: qué se hizo, qué se decidió, qué sigue.

---

## Conceptos clave

### Estado persistente (`.bago/state/`)

Todo lo que importa entre sesiones vive aquí:

```
.bago/state/
  global_state.json     ← sesión activa, salud, inventario
  sessions/             ← registro de cada sesión
  changes/BAGO-CHG-*.json ← artefactos de cambio (inmutables)
  evidences/            ← evidencia adjunta a cada cambio
```

No toques estos ficheros manualmente. BAGO los gestiona.

### Frozen decisions

Las decisiones arquitectónicas que no deben cuestionarse en cada sesión. Una vez registradas, el agente no las reabre.

```bash
# Para ver las decisiones actuales:
bago status
```

### Health score

Un número entre 0 y 100 que refleja el estado real del sistema:

```
health = integridad × 0.25
       + uso de workflows × 0.20
       + decisiones capturadas × 0.20
       + tareas sin stale × 0.15
       + inventario consistente × 0.20
```

Un score por debajo de 60 indica problemas acumulados que conviene revisar.

### BAGO-CHG

Cada cambio significativo genera un artefacto `BAGO-CHG-NNN.json` inmutable con:
- Qué se cambió
- Por qué
- Evidencia adjunta

Esto crea un historial auditado que ni el agente ni el desarrollador pueden borrar accidentalmente.

---

## Perfiles de usuario

### Desarrollador individual

Flujo típico:
```bash
bago health             # ¿cómo está el sistema?
bago status             # ¿qué tengo pendiente?
bago session open       # abrir sesión
bago workflow           # elegir protocolo
# ... trabajar ...
bago validate           # verificar integridad
bago session close      # cerrar y registrar
```

### Equipo pequeño (2–5 personas)

Añadir:
```bash
bago project link       # vincular el proyecto al framework
bago project learn      # compartir aprendizajes entre sesiones
bago audit full         # auditar qué hizo quién
```

### Proyectos con múltiples agentes IA

```bash
bago cabinet --yes      # orquestación multi-agente paralela
bago audit push         # gate antes de subir cambios
```

---

## Errores comunes en los primeros días

**"El health score no sube"**  
Normal. Necesita historial de sesiones reales. Abre y cierra sesiones con `bago session open` / `bago session close` y el score irá subiendo.

**"No sé qué workflow elegir"**  
Usa `W0 · Free Session` para explorar. Cuando identifiques qué tipo de tarea es, cierra y reabre con el workflow correcto.

**"El agente ignora el estado BAGO"**  
Asegúrate de que el agente tiene acceso al fichero `.bago/state/global_state.json`. Algunos setups de Copilot/Claude requieren que se lo indiques explícitamente en el prompt inicial.

**"validate falla con GO pero errors en state"**  
Ejecuta `bago audit heal` para autodetectar y reparar problemas comunes.

---

## Referencia rápida

```bash
# Diagnóstico
bago health             # score 0–100
bago status             # estado actual
bago validate           # integridad del sistema

# Sesión
bago session open       # abrir
bago session close      # cerrar
bago session harvest    # cosechar artefactos

# Trabajo
bago task               # tarea activa W2
bago workflow           # selector de workflow
bago ideas              # ideas priorizadas

# Calidad
bago audit scan         # escaneo de calidad de código
bago audit commit       # evaluación pre-commit
bago secrets            # escaneo de credenciales expuestas
```

Para la referencia completa de todos los comandos: [`COMMANDS.md`](COMMANDS.md)

---

*BAGO v3.3.0 · Para más información: github.com/MarcValls/BAGO*
