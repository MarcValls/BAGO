# W0 · SESIÓN LIBRE (sin estructura BAGO)

## id

`w0_free_session`

---

**Código:** W0_FREE_SESSION  
**Propósito:** Marcador de workflow para sesiones en modo `.bago/off`. Representa trabajo libre sin preflight, sin pre-declaración de artefactos y sin restricción de roles.  
**Cuándo usarlo:** Exclusivamente en el contexto del **ESCENARIO-002** (competición on vs off). No usar en sesiones productivas normales.

---

## Protocolo .bago/off

Una sesión `.bago/off` sigue estas reglas:

1. **Sin preflight** — no ejecutar `session_preflight.py`
2. **Sin `artifacts_planned`** — no declarar artefactos antes de empezar
3. **Sin restricción de roles** — activar los que surjan durante la sesión
4. **Objetivo libre** — puede redefinirse durante la sesión
5. **Cierre igual** — sí se crea el JSON de sesión + CHG + EVD al cerrar

El campo `bago_mode` del JSON de sesión debe ser `"off"`.

---

## Propósito en el ESCENARIO-002

Las sesiones W0 son el **grupo de control** del experimento.  
Su producción se compara contra el grupo W7 (`.bago/on`) para medir el delta.

Ver `state/scenarios/ESCENARIO-COMPETICION-BAGO.md` para el protocolo completo.
