# COMPARATIVA DE EVOLUCION: bago-framework vs BAGO

> Generado el 2026-05-20 desde analisis del repo local y API de GitHub

---

## 1. IDENTIDAD DE LOS REPOS

| Caracteristica | bago-framework (antiguo) | BAGO (actual) |
|----------------|--------------------------|---------------|
| URL | github.com/MarcValls/bago-framework | github.com/MarcValls/BAGO |
| Estado | Archivado / legacy | Activo / en desarrollo |
| Descripcion | BAGO Framework v2.5 - AI session governance | (sin descripcion en GitHub) |
| Ultimo commit | 2026-05-06 | 2026-05-19 |
| Tags | 3 | 9 |
| Releases publicadas | 0 | 4 (v3.4.2 a v3.4.5) |
| README size | 9,503 bytes | 15,614 bytes |
| Version declarada | 3.1 | 3.4.5 |

---

## 2. METRICAS DE ESCALA

| Metrica | bago-framework | BAGO | Cambio |
|---------|----------------|------|--------|
| Total archivos | 499 | ~936 | +87% |
| Archivos Python (.py) | 191 | 464 | +143% |
| Archivos Markdown (.md) | 222 | 300 | +35% |
| Archivos JSON (.json) | 38 | 177 | +366% |
| Tamano total | 5.7 MB | ~18+ MB | +215% |
| Tools en .bago/tools | 198 | 395 | +99% |
| Workflows documentados | 27 | 14 | -48% |
| Docs de agentes (.md) | 18 | (en .bago/agents/) | consolidado |
| Docs de roles (.md) | 25 | (en .bago/agents/) | consolidado |
| Docs en docs/ | 2 | 27 | +1250% |

---

## 3. CLI Y COMANDOS

| Aspecto | bago-framework | BAGO |
|---------|----------------|------|
| Comandos totales | 83 (segun README) | 160 |
| Comandos core | ~13 | 39 |
| Comandos experimental | no documentados | 80 |
| Comandos dangerous | no documentados | 8 |
| Comandos legacy | no documentados | 28 |
| Modulos unicos | ~80+ | 149 |

**Evolucion de comandos por version:**

| Version | Comandos | Tools | Docs | Workflows | Eficiencia |
|---------|----------|-------|------|-----------|------------|
| 2.3-clean (baseline) | 10 | 19 | 68 | 12 | 78.6 |
| 2.4-v2rc | 10 | 27 | 73 | 12 | 89.3 |
| 2.5-stable | 35 | 111 | 77 | 20 | 100.0 |
| 2.6-taxonomy | 51 | 177 | 278 | 8 | 100.0 |
| 3.1 (bago-framework) | 83 | 203 | -- | 17 | -- |
| 3.4.5 (BAGO actual) | 160 | 395+ | 300 | 14 | 100.0 |

**Crecimiento 2.3 -> 3.4.5:** x16 comandos · x21 tools · x4.4 docs

---

## 4. TAXONOMIA Y ARQUITECTURA

### bago-framework (v2.5 -> v3.1)
- Estructura: todo dentro de .bago/
- Agentes definidos como archivos .md individuales
- Roles definidos como archivos .md individuales
- Workflows: 27 archivos .md dispersos
- No habia releases ni empaquetado ZIP
- Makefile basico (validate, pack, install, clean)

### BAGO (v3.4.5)
- Estructura: separacion clara docs/, .bago/, tests/, bago_core/
- Agentes consolidados en .bago/agents/ (12 agentes)
- Roles con codigo embebido indexado (.embed.json)
- Workflows operacionales: W0-W10 + maestro
- Releases GitHub con ZIP distribuible
- Pipeline CI con 8 gates (badge activo)
- Entrypoint empaquetado: bago_core/ (modo repo + modo wheel)
- Sistema de capas (layers): motor, memoria, consumo, generacion, dominio, infraestructura, calidad

---

## 5. CONOCIMIENTO ACUMULADO (solo en BAGO actual)

### Documentacion nueva que no existia en bago-framework
- docs/EVOLUCION.md - 15 trampas confirmadas + propuestas v4.0
- docs/PITCH.md - propuesta de valor con metricas reales
- docs/ARCHITECTURE.md - arquitectura del framework
- docs/API_CONTRACT.md - contrato API publico
- docs/KERNEL_LOCKDOWN.md - politica de kernel
- docs/CONTRACTS.md - contratos de cambio
- docs/SLASH_MENU.md - menu slash del chat
- CHANGELOG.md - historial completo de releases

### Agentes del sistema (12 en .bago/agents/)
1. ADAPTADOR_PROYECTO
2. ANALISTA_Contexto
3. ARQUITECTO_Soluciones
4. CENTINELA_SINCERIDAD
5. COPILOT_ALIADO_BAGO
6. GENERADOR_Contenido
7. GUIA_VERTICE
8. INICIADOR_MAESTRO
9. MAESTRO_BAGO
10. ORGANIZADOR_Entregables

### Workflows operacionales (W0-W10)
- W0_FREE_SESSION - exploracion libre
- W1_COLD_START - bootstrap de proyecto
- W2_IMPLEMENTACION_CONTROLADA - feature delivery
- W3_REFACTOR_SENSIBLE - cambios de alto riesgo
- W4_DEBUG_MULTICAUSA - investigacion de bugs
- W5_CIERRE_Y_CONTINUIDAD - cierre + handoff
- W6_IDEACION_APLICADA - innovacion
- W7_FOCO_SESION - sesiones scopeadas
- W8_EXPLORACION - research
- W9_COSECHA - harvest de artefactos
- W10_AUDITORIA_SINCERIDAD - deteccion de claims falsos

### Features nuevas (v3.4.x)
| Version | Feature clave |
|---------|--------------|
| 3.4.1 | Contrato de instalacion limpia, encoding guard, validadores sinceros |
| 3.4.2 | Roles con codigo embebido indexado, Spiral Prompt Builder, Artefact Repository |
| 3.4.3 | Prompt Router con metricas de senal WiFi (2.4g/5g, canales, Hz) |
| 3.4.4 | Token Brake (freno de tokens para providers API, copilot disabled) |
| 3.4.5 | Token Analytics (desglose por proveedor/modelo, tokens derrochados) |

---

## 6. PROYECTOS CONSTRUIDOS CON BAGO

Proyectos reales documentados en README del repo actual:

| Proyecto | Descripcion |
|----------|-------------|
| ISO_GAME | Juego isometrico en Python - pathfinding, pygame, autotile |
| BAGO_MUSIC_PIPELINE | Transposicion de partituras PDF/MIDI/MusicXML |
| BAGO_TELEGRAM_BOT | Bot Telegram full-feature con MiniApp, WhatsApp, NFT |
| BAGO_SPRITE_STUDIO | Generador procedural de sprites para juegos (HF/Codex) |
| BAGO_WALLET_TRACKER | Portfolio crypto read-only + TON airdrop scanner |
| BAGO_NEURAL_FABRIC | Motor de orquestacion dinamica SENSE/PLAN/ACT/... |
| BAGO_WINDOWS_AUTOMATION | Automatizacion Win32 - mouse, UAC, Task Scheduler |
| BIANCA_THE_GAME | Narrativa grafica - 47 FX, AudioManager, mundos literarios |

---

## 7. SABERES QUE SE PERDIERON / MIGRARON

### Del antiguo (bago-framework) que ya no esta en BAGO
- CLI_INDEX.md, CLI_QUICK_START.md, CLI_README.md (reemplazados por docs/COMMANDS.md)
- TABLET_* documentacion (despliegue tablet - no parece relevante ahora)
- AGENT_FACTORY_DOCUMENTATION.md, ROLE_FACTORY_DOCUMENTATION.md (consolidado en agentes con .embed.json)
- Varios archivos de DEMO_* verificacion

### Del antiguo que SI sobrevive en BAGO
- .bago/AGENT_START.md (actualizado)
- .bago/BOOTSTRAP.md (actualizado)
- Makefile (ampliado)
- Concepto de pack.json (evolucionado)
- Workflows W0-W9 (refinados)

---

## 8. DIFERENCIAS CLAVE DE DISENO

| Aspecto | bago-framework | BAGO |
|---------|----------------|------|
| Instalacion | Clonacion manual + alias | ZIP distribuible + install.sh/.cmd + pip wheel |
| Estado | Plantilla hardcodeada | global_state.clean.json + inyeccion dinamica |
| Validacion | grep optimista (falso OK) | Codigo de salida real, fallo cerrado |
| Encoding | Mojibake permitido | encoding_guard.py bloqueante |
| Copilot | Login habilitado | Login deshabilitado por defecto (token brake) |
| Version | Hardcodeada en varios sitios | Inyectada desde pack.json |
| Tests | print OK; exit(0) | Subprocess real + AST + pytest |
| Documentacion | 77 archivos inflados | 300 archivos con sinceridad audit |

---

*Reporte generado automaticamente desde analisis de repos GitHub y local*
*Fuentes: API GitHub, docs/EVOLUCION.md, docs/PITCH.md, CHANGELOG.md, tool_registry.py*
