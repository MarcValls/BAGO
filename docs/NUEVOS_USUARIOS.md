# BAGO — Guía para Nuevos Usuarios

> **Tiempo estimado de lectura:** 15 minutos  
> **Resultado:** Entenderás qué es BAGO, para qué sirve, y habrás completado tu primera sesión real.

---

## ¿Qué es BAGO?

BAGO es una **capa operacional persistente** entre tú y tu agente de IA.

Tu agente de IA (GitHub Copilot, Claude, GPT) es potente pero **amnésico**: cada sesión empieza de cero. No recuerda qué decidiste ayer, qué errores cometiste la semana pasada, ni qué dejaste pendiente.

BAGO resuelve eso. Es la memoria que el agente no tiene.

```
Sin BAGO:   Tú → [agente IA amnésico] → código/docs
Con BAGO:   Tú → [BAGO + agente] → sesión estructurada, trazable, continua
```

### Lo que BAGO hace por ti

| Problema sin BAGO | Solución con BAGO |
|-------------------|-------------------|
| "El agente no recuerda lo que hicimos ayer" | `bago status` — muestra el contexto activo |
| "No sé por dónde retomar" | `bago hello` — te dice exactamente el siguiente paso |
| "Perdimos una decisión importante" | `bago cosecha` — captura decisiones al cerrar sesión |
| "El agente se va por las ramas" | `bago flow start` — sesión con objetivo único y foco |
| "No sé si el sistema está bien" | `bago health` — puntuación de salud 0-100 |

---

## Para quién es BAGO

✅ **Desarrolladores** que usan agentes IA y quieren sesiones con memoria y estructura  
✅ **Proyectos creativos** (narrativa, videojuegos, diseño) que requieren coherencia a largo plazo  
✅ **Cualquier dominio técnico** — BAGO no es exclusivo de código (contabilidad, producción musical, TPV)  
✅ **Trabajo en solitario** que quiere la disciplina de un equipo  

❌ No es una herramienta de gestión de proyectos tipo Jira  
❌ No es un IDE ni un editor  
❌ No requiere conexión a internet ni API keys  

---

## Instalación (5 minutos)

**Requisitos:** Python 3.9 o superior. Sin dependencias externas.

```bash
# Opción A — desde el pendrive (si tienes el dispositivo BAGO)
bash /Volumes/BAGO/start.sh

# Opción B — desde GitHub
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
pip install -e .
```

Verifica que funciona:

```bash
bago hello
```

Deberías ver el panel de bienvenida con tu estado actual. Si ves `initializing`, es correcto — es una instalación nueva sin historial todavía.

---

## Los 5 comandos que necesitas saber

No hay que aprender 54 comandos. Con estos 5 cubres el 80% del uso diario:

### `bago hello`
**Cuándo:** Al empezar cualquier sesión. Tu punto de entrada.

```bash
bago hello
```

Te muestra: salud del sistema, flujo activo, tarea actual, ideas disponibles, y el **próximo paso sugerido**.

```
bago hello --quick    # versión resumida (1 línea)
bago hello --tour     # recorrido interactivo paso a paso
```

---

### `bago ideas`
**Cuándo:** No sabes por dónde empezar o quieres que el sistema te diga qué conviene hacer.

```bash
bago ideas
```

BAGO analiza el contexto actual y te propone las 5-20 ideas más relevantes, priorizadas. No necesitas pensar qué tocar — el sistema lo sabe.

---

### `bago flow start`
**Cuándo:** Vas a trabajar en algo concreto. Abre una sesión con objetivo único.

```bash
bago flow start
# Te pregunta: ¿cuál es el objetivo de esta sesión?
# Escribe algo concreto: "implementar login con JWT"
```

Esto activa el **modo foco**: BAGO registra tu objetivo, el tiempo, y el contexto. El agente de IA sabrá exactamente en qué estáis trabajando.

---

### `bago status`
**Cuándo:** Quieres saber en qué punto está el sistema ahora mismo.

```bash
bago status
```

Muestra: flujo activo, tarea en curso, últimas decisiones, salud, y próximo paso pendiente.

---

### `bago task --done`
**Cuándo:** Terminas una sesión de trabajo.

```bash
bago task --done
```

Cierra la tarea activa, registra lo que se hizo, captura decisiones, y deja el sistema listo para la próxima sesión. **Nunca salgas sin ejecutar este comando** — es lo que da continuidad.

---

## Tu primera sesión — paso a paso

### Sesión de 20 minutos para entender BAGO desde dentro

```bash
# 1. Inicia BAGO y mira el estado
bago hello

# 2. Pide ideas — qué conviene hacer
bago ideas

# 3. Acepta la primera idea (o define tú el objetivo)
bago flow start
# Escribe: "explorar BAGO por primera vez"

# 4. Trabaja — haz algo concreto:
#    - Abre un proyecto tuyo existente
#    - Haz un bago health para ver la salud
#    - Lee el status
bago health
bago status

# 5. Al terminar, cierra bien
bago task --done
# Escribe qué aprendiste / qué decidiste
```

Al completar estos pasos, BAGO ya tiene memoria de tu primera sesión. La próxima vez que abras `bago hello`, verá que trabajaste antes.

---

## Errores frecuentes de usuarios nuevos

Estos son los errores más comunes. Conocerlos te ahorra horas.

---

### ❌ Error 1 — Cerrar sin `bago task --done`

**Qué pasa:** Sales de la terminal sin cerrar la tarea.  
**Consecuencia:** La sesión queda "abierta" — BAGO pierde el contexto de lo que hiciste.  
**Solución:** Siempre termina con `bago task --done`. Si olvidaste hacerlo, ejecuta `bago task --done` al empezar la siguiente sesión.

---

### ❌ Error 2 — Abrir varias sesiones sin cerrar las anteriores

**Qué pasa:** Abres un flujo, no lo cierras, abres otro.  
**Consecuencia:** El sistema acumula flujos "zombis" — el health score baja.  
**Solución:** `bago status` para ver flujos abiertos. `bago task --done` para cerrar el activo.

---

### ❌ Error 3 — Esperar que el agente "lea" BAGO solo

**Qué pasa:** Abres el agente de IA sin indicarle que use BAGO.  
**Consecuencia:** El agente ignora el contexto BAGO — trabaja como si no existiera.  
**Solución:** Al abrir una sesión con tu agente, dile explícitamente:  
```
"Lee .bago/state/global_state.json y continúa desde donde lo dejamos"
```

---

### ❌ Error 4 — Confundir `bago health` con métricas de código

**Qué pasa:** Esperas que `bago health` analice la calidad de tu código.  
**Qué mide en realidad:** La salud del **framework BAGO** en tu sesión — disciplina de workflow, capturas de decisiones, estado stale.  
**Para analizar tu código:** usa `bago audit` o `bago sincerity`.

---

### ❌ Error 5 — Abrir sesiones sin objetivo claro

**Qué pasa:** Ejecutas `bago flow start` y escribes algo vago: "trabajar en el proyecto".  
**Consecuencia:** El agente no tiene foco, la sesión deriva.  
**Solución:** El objetivo debe ser **específico y verificable**:
```
❌ "trabajar en el proyecto"
✅ "implementar el formulario de login con validación de email"
✅ "corregir el bug del timeout en la API de pagos"
✅ "escribir los tests del módulo de autenticación"
```

---

### ❌ Error 6 — Instalar BAGO y no usarlo durante semanas

**Qué pasa:** Instalas, pruebas una vez, y lo dejas.  
**Consecuencia:** BAGO sin uso no genera valor — su potencia viene de la acumulación de sesiones.  
**Solución:** Comprométete a 5 sesiones consecutivas. A partir de la 5ª empiezas a ver el beneficio de la continuidad.

---

## Conceptos clave (glosario mínimo)

| Término | Qué significa |
|---------|--------------|
| **Flujo** | Una sesión de trabajo con objetivo definido (equivale a un sprint mini) |
| **Tarea activa** | El objetivo específico de la sesión actual |
| **Cosecha** | Proceso de capturar aprendizajes y decisiones al cerrar sesión |
| **Health score** | Puntuación 0-100 de la salud del sistema BAGO en tu proyecto |
| **global_state.json** | El "cerebro" de BAGO — registra todo el contexto activo |
| **Trampa semántica** | Cuando el sistema reporta éxito sin haberlo verificado realmente |
| **W2** | Workflow de implementación controlada — el más usado en producción |
| **W7** | Workflow de foco de sesión — para tareas con objetivo único |

---

## Siguiente paso

Una vez completada tu primera sesión:

1. **[SECUENCIAS.md](SECUENCIAS.md)** — recetas de comandos para situaciones concretas  
2. **[GETTING_STARTED.md](GETTING_STARTED.md)** — instalación completa y configuración  
3. **[COMMANDS.md](COMMANDS.md)** — referencia de los 54 comandos cuando los necesites  

---

## ¿Algo no funciona?

```bash
bago health          # diagnóstico general
bago doctor          # diagnóstico con sugerencias de reparación
bago doctor --fix    # autofix para problemas comunes
bago validate        # verifica la integridad del pack
```

Si el problema persiste: [github.com/MarcValls/BAGO/issues](https://github.com/MarcValls/BAGO/issues)

---

*BAGO v3.3.0 · Guía para nuevos usuarios · 2026-05-08*  
*Basada en: framework_traps.md, bago_universe.md, sequences_catalog.md, april_2026_arc.md*
