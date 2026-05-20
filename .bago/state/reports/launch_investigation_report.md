# BAGO launch — Investigación Exhaustiva v3.5

## Fecha
2026-05-20

## Entorno
- Windows 10
- Python 3.14.5
- BAGO v3.4.6 (repo local)

## Objetivo
Investigar a fondo el comando `bago launch` como si fuese un usuario real, probando flujos, edge cases y documentando bugs.

---

## Arquitectura del comando

`bago launch` está registrado en `bago_core/launcher.py` (`COMMANDS` dict) y apunta a:
```
.bago/tools/bago_chat.py
```

Flujo de ejecución:
1. `launcher.py` → `_dispatch("launch", [])`
2. `bago_chat.py` → `main()`
3. `resolve_session(args)` → detecta provider/modelo
4. `run_startup_tasks(session)` → health scan + HW probe + banner
5. `build_prompt_session()` → REPL (prompt_toolkit o básico)
6. `run_repl(session, pt)` → bucle interactivo

---

## Escenarios probados

### S1: Arranque básico (`bago launch` → `/exit`)
**Resultado:** OK
- Banner aparece (después del parche, solo 1 vez)
- Se detecta provider `ollama-local`
- Se muestra prompt `[BAGO|AUTO] >`
- `/exit` termina el REPL
- rc=0

**Antes del parche:** Banner doble (líneas 96 y 109 de `boot.py`)
**Después del parche:** Banner único con health scan rápido

### S2: Comandos `!` (sistema BAGO desde el chat)
**Resultado:** Parcial
- `!version` → funciona, devuelve `GO version_truth`
- `!validate` → funciona pero tarda (health_score subprocess)
- Problema original: `subprocess.run` con `capture_output=True` bloqueaba el REPL
- Parche aplicado: streaming con `Popen` + threads + timeout 60s + Ctrl+C handling

### S3: Menú `/`
**Resultado:** OK (con prompt_toolkit instalado)
- `/` abre menú navegable con flechas
- Tiene grupo "Sistema BAGO" con 15 comandos `!`
- Items: `!validate`, `!health`, `!audit`, `!version`, `!autonomous`, `!git-dirty`, `!test`, `!encoding`, `!census`, `!map`, `!prompt-router`, `!role-spiral`, `!model-gate`, `!token-analytics`, `!api-only`

### S4: Sin prompt_toolkit
**Resultado:** Degradación aceptable
- Mensaje: `prompt_toolkit no disponible en esta consola (NoConsoleScreenBufferError); usando REPL básico.`
- El menú `/` sigue funcionando pero sin autocompletado ni historial persistente
- UX reducida pero funcional

### S5: Estado corrupto / sin providers
**Resultado:** Manejado
- Si no hay providers activos, `resolve_session` muestra panel amarillo con instrucciones
- No crashea, permite `/login` para configurar

### S6: Modo `--api`
**Resultado:** No probado en profundidad
- Flag `--api` arranca servidor API en puerto 11435
- Código presente en `bago_chat.py` líneas 28-40
- No se verificó interacción real con el servidor

---

## Bugs identificados y estado

| # | Bug | Archivo | Estado |
|---|-----|---------|--------|
| 1 | Banner doble al arrancar | `boot.py:96,109` | **FIXED** |
| 2 | Comandos `!` bloqueaban REPL (capture_output) | `cmd.py:631-646` | **FIXED** |
| 3 | Sin menú `\` (solicitado por usuario) | — | **NOT IMPLEMENTED** |
| 4 | `bago launch` no tiene `--help` propio | `bago_chat.py` | **DOCUMENTED** |
| 5 | Timeout fijo 120s en `!` commands | `cmd.py:640` | **FIXED** (60s + streaming) |

---

## Parches aplicados

### P1: Eliminar banner doble
**Archivo:** `.bago/tools/bago/chat/boot.py`
**Cambio:** Reemplazar `banner(session)` inmediato + `banner(session, health=_health)` por lógica condicional:
- Intenta obtener health en 0.5s
- Si está disponible, imprime banner con health
- Si no, imprime banner simple y continúa

### P2: Streaming de comandos `!`
**Archivo:** `.bago/tools/bago/cmd.py`
**Cambio:** Reemplazar `subprocess.run(capture_output=True)` por `subprocess.Popen` con threads que streaman stdout/stderr en tiempo real, permitiendo al usuario ver progreso y cancelar con Ctrl+C.

---

## Recomendaciones

1. **Instalar prompt_toolkit** para mejor UX (autocompletado, historial, menús navegables)
2. **Usar Windows Terminal** en lugar de CMD clásico para soporte VT/Unicode completo
3. **Documentar** que `!` commands tienen timeout de 60s y pueden interrumpirse
4. **Considerar** añadir menú `\` como alias de `/` si el usuario lo solicita
5. **Añadir** `--help` a `bago_chat.py` para describir flags `--provider`, `--model`, `--task`, `--api`

---

## Veredicto

`bago launch` es funcional como punto de entrada interactivo de BAGO. Tras los parches:
- No hay banner doble
- Los comandos `!` no bloquean el REPL
- El menú `/` da acceso a todo el sistema
- La degradación sin prompt_toolkit es aceptable

**Estado: OPERATIVO con parches aplicados**
