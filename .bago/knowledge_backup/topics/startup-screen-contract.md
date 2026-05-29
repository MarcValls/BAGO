# Contrato Operativo — Pantalla de Inicio BAGO (Banner / Splash)

## 1. Alcance

Este contrato define el comportamiento, contenido mínimo y garantías de la **pantalla de inicio** de BAGO CLI, mostrada al ejecutar `bago launch` o `bago status` en modo interactivo.

## 2. Activación

| Evento | Pantalla |
|--------|----------|
| `bago launch` | Splash interactivo + selector de provider |
| `bago launch --provider <name>` | Banner reducido + arranque directo |
| `bago status` (TTY) | Banner compacto + resumen de estado |
| `bago banner` | Solo banner ASCII sin estado |
| `bago banner --mini` | Logo mínimo, 5 líneas |
| `bago banner --plain` | Sin colores ANSI |

## 3. Contenido Mínimo Obligatorio

La pantalla de inicio **siempre** debe mostrar:

1. **Logotipo ASCII** — identidad visual BAGO (mínimo 5 líneas, máximo 40).
2. **Versión del pack** — leída de `global_state.json` (`bago_version`).
3. **Modo de operación** — CREATE / CHAT / FRAMEWORK (si devmode).
4. **Proyectos recientes** — hasta 5 proyectos de `recent_projects.json`.
5. **Acciones rápidas** — comandos sugeridos según contexto.
6. **Modo de instalación** — `installed` / `portable` / `project`.
7. **Provider activo** — detectado o forzado por flag.
8. **Estado de salud** — color: 🟢 OK / 🟡 WARN / 🔴 KO / ⚪ inicializando.
9. **Fuente de verdad** — ruta absoluta del `.bago` activo (una sola línea).

## 4. Comportamiento

- **UTF-8 forzado**: `PYTHONIOENCODING=utf-8` y `PYTHONUTF8=1` antes de cualquier impresión.
- **Windows VT**: Si `sys.platform == "win32"`, activar `ENABLE_VIRTUAL_TERMINAL_PROCESSING` vía `ctypes`.
- **Fallback sin color**: Si `--plain`, TTY no disponible, o VT falla, usar salida ASCII plana.
- **Timeout implícito**: El splash no debe bloquear más de 3 segundos esperando detección de provider.
- **No interactivo**: Si `stdout` no es TTY, suprimir animaciones y usar formato línea a línea.
- **Navegación interactiva**: El menú de inicio (`bago_start_menu.py`) debe ser navegable con:
  - **Flechas ↑↓** para mover la selección.
  - **Números 1-9** para saltar directamente a una opción.
  - **Enter** para ejecutar la opción seleccionada.
  - **q / Esc** para salir.

## 5. Scripts Responsables

| Script | Rol |
|--------|-----|
| `.bago/tools/bago_banner.py` | Banner ASCII puro, estado del pack, colores ANSI. Fallback ligero. |
| `.bago/tools/bago_splash.py` | Pantalla gráfica enriquecida (Rich). Muestra logo, modo, proyectos recientes, acciones rápidas, neural fabric y comandos. |
| `.bago/tools/bago_chat.py` | Orquesta el arranque del chat: banner → REPL. |
| `.bago/tools/bago_start.py` | Arranque interactivo completo con presencia visual (MAESTRO, AUDITOR, ORQUESTADOR). |
| `.bago/tools/bago_start_menu.py` | **Menú de inicio interactivo con curses.** Navegable con flechas (↑↓) y números (1-9). Muestra logo, versión, modo de instalación, provider, estado de salud, fuente de verdad, modos de operación, proyectos recientes y acciones rápidas. Entrada por defecto cuando `bago` se ejecuta sin argumentos. |

## 6. Contrato de Salida

| Código | Significado |
|--------|-------------|
| `0` | Banner mostrado correctamente, sistema listo. |
| `1` | Error crítico: estado corrupto, `global_state.json` ilegible. |
| `2` | Provider forzado no disponible (ej. Ollama no responde). |
| `130` | Usuario interrumpió con Ctrl-C durante el splash. |

## 7. Métricas de Verificación

- `bago validate` debe pasar después de cualquier cambio en los scripts de banner/splash.
- `bago test` debe incluir al menos un test de render del banner sin excepciones.
- No debe haber caracteres de control (bell, escape no-ANSI) en salida `--plain`.

## 8. Ejemplo de Salida Esperada (TTY)

```
Fuente de verdad: C:\bago_true\.bago (INSTALADO)
  Provider detectado: copilot

  ____    _    ____   ___
 |  _ \  / \  / ___| / _ \
 | |_) |/ _ \| |  _ | | | |
 |  _ </ ___ \ |_| || |_| |
 |____/_/   \_\____| \___/

                    BAGO 3.5.0b1  ·  USER mode  ·  INSTALLED
                      Provider: copilot  ·  Estado: 🟢 OK
                          Fuente: C:\bago_true\.bago

    ── MODO DE OPERACIÓN ──
     ▶  1. 💬  Modo CHAT
        Interfaz conversacional con BAGO
        2. 🛠️  Modo CREATE
    ── ACCIONES RÁPIDAS ──
        3. ➕  Nuevo proyecto

  ↑↓ navegar  ·  1-9 seleccionar directo  ·  Enter ejecutar  ·  q salir
```

## 9. Cambios al Contrato

Cualquier modificación a este contrato requiere:
1. Actualizar este archivo.
2. Ejecutar `bago validate`.
3. Registrar en CHANGELOG.md bajo la versión activa.

---
*Contrato de pantalla de inicio · BAGO 3.5.0b1 · 2026-05-27*
