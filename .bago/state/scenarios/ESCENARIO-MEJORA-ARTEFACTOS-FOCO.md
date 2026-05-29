# ESCENARIO-001: Mejora de Artefactos con Foco

> Estado: ACTIVO  
> Creado: 2026-05-27  
> Última actualización: 2026-05-27

## 1. Propósito

Este escenario gobierna las sesiones productivas de mejora continua del framework BAGO.  
Cuando está activo en `global_state.json → active_scenarios`, **toda sesión productiva debe pasar el preflight antes de arrancar** y usar obligatoriamente el workflow **W7_FOCO_SESION**.

## 2. Reglas Obligatorias

1. **Preflight obligatorio:** ejecutar `bago preflight` antes de cualquier sesión productiva.
2. **Workflow obligatorio:** usar `W7_FOCO_SESION` en lugar de arranques improvisados.
3. **No mezclar bootstrap con ejecución principal:** el bootstrap es solo para instalación/reparación.
4. **Activación de roles controlada:** no activar todos los roles por defecto; usar el router de roles.

## 3. Activación / Desactivación

- Activar: añadir `"ESCENARIO-001"` a `state/global_state.json → active_scenarios`.
- Desactivar: quitar `"ESCENARIO-001"` de `active_scenarios` y registrar evaluación en `state/evidences/`.

## 4. Medición

- Tasa de sesiones con preflight PASS vs total.
- Artefactos modificados por sesión con foco vs sin foco.
- Tiempo medio de cierre de checklist v2.

## 5. Referencias

- `workflows/W7_FOCO_SESION.md` — workflow obligatorio
- `AGENT_START.md` — reglas de arranque del agente
- `tools/preflight.py` — motor de preflight checks
