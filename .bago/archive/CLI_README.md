# 🎯 BAGO CLI v3.0 - Sistema Completo

**Versión:** 3.0  
**Estado:** ✅ Productivo  
**Última actualización:** 2026-04-28

---

## 📋 Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Características](#características)
3. [Inicio Rápido](#inicio-rápido)
4. [Componentes](#componentes)
5. [Flujos de Uso](#flujos-de-uso)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Resumen Ejecutivo

BAGO CLI v3.0 es una interfaz profesional para el **Code Quality Orchestrator**. Permite:

- ✅ Analizar código con 4 agents especializados
- ✅ Aplicar gobernanza mediante 16 roles distribuidos
- ✅ Gestionar agents y roles dinámicamente
- ✅ Ver historial de análisis
- ✅ Acceder a documentación integrada
- ✅ Ejecutar demos interactivas

**Arquitectura:**
```
USER → CLI v3.0 → Orchestrator → [Agents] → [Hallazgos]
                                            ↓
                                        [Roles] → [Verdicts]
```

---

## ✨ Características

### CLI Interactiva Profesional
- 🎨 Diseño con menú colorido y emojis
- 📱 Interfaz intuitiva y fácil de usar
- ⌨️ Navegación rápida con números
- 💾 Historial automático de análisis
- ⚙️ Configuración personalizable

### Gestión de Agents
- 📊 Listar 4 agents built-in
- ➕ Crear nuevos agents custom
- 📋 Ver agents registrados
- 🔄 Auto-descubrimiento dinámico

### Gestión de Roles
- 👑 Ver 16 roles en 4 familias
- 🏗️ Gobierno, Especialistas, Supervisión, Producción
- ➕ Crear nuevos roles
- 📊 Aplicar gobernanza en análisis

### Documentación Integrada
- 📚 Acceso directo a 6 documentos
- 📖 Guías de referencia rápida
- 🎓 Ejemplos completos
- 🔍 Troubleshooting

### Demo Interactiva
- 🎬 Un clic para ejecutar demo
- 📊 Análisis real de `typing-course`
- 📈 Ver verdicts en acción
- 💡 Aprender el flujo completo

---

## 🚀 Inicio Rápido

### Opción 1: CLI Interactiva (Recomendado)

```bash
cd C:\Marc_max_20gb\.bago
.\bago-cli.ps1
```

### Opción 2: CLI de Comandos

```bash
cd C:\Marc_max_20gb\.bago
.\bago.ps1 analyze ..\typing-course\src
```

### Opción 3: Menú Tradicional

```bash
cd C:\Marc_max_20gb\.bago
.\cli.ps1
```

---

## 🔧 Componentes

### PowerShell Scripts

| Archivo | Función | Versión |
|---------|---------|---------|
| `bago-cli.ps1` | ⭐ CLI Interactiva Profesional | v3.0 |
| `bago.ps1` | CLI Basada en Comandos | v2.0 |
| `cli.ps1` | Menú Interactivo Legacy | v2.0 |
| `code_quality_orchestrator.ps1` | Ejecuta 4 agents | v2.0 |
| `role_orchestrator.ps1` | Consulta roles | v2.0 |

### Python Factories

| Archivo | Función |
|---------|---------|
| `agents/agent_factory.py` | Factory para crear agents |
| `roles/role_factory.py` | Factory para crear roles |

### Documentación

| Archivo | Contenido |
|---------|----------|
| `CLI_QUICK_START.md` | 📖 Guía de inicio rápido |
| `EJEMPLO_INTERACCION_COMPLETA.md` | 📋 Ejemplo paso a paso |
| `DEMO_EJECUCION_REAL.md` | 🎬 Demo con outputs reales |
| `PHASE_4_5_GUIDE.md` | 📚 Guía completa de Phase 4-5 |
| `AGENT_FACTORY_DOCUMENTATION.md` | 🤖 Cómo crear agents |
| `ROLE_FACTORY_DOCUMENTATION.md` | 👑 Cómo crear roles |
| `VERIFICACION_COMPONENTES_Y_ESTADO.md` | ✅ Verificación de sistema |

---

## 🎮 Flujos de Uso

### Flujo 1: Análisis Básico

```
1. .\bago-cli.ps1
   ↓
2. Selecciona [1] Analyze Code
   ↓
3. Ingresa ruta: ..\typing-course\src
   ↓
4. Agents se ejecutan automáticamente
   ↓
5. Ver hallazgos y verdicts
   ↓
6. Presiona Enter para volver al menú
```

### Flujo 2: Crear Nuevo Agent

```
1. .\bago-cli.ps1
   ↓
2. Selecciona [4] Create Agent
   ↓
3. Ingresa: nombre, categoría, descripción
   ↓
4. Agent se registra en manifest.json
   ↓
5. Disponible en próximos análisis
```

### Flujo 3: Explorar Documentación

```
1. .\bago-cli.ps1
   ↓
2. Selecciona [8] Help & Docs
   ↓
3. Elige documento (1-6)
   ↓
4. Se abre en Notepad automáticamente
   ↓
5. Lee y aprende
```

### Flujo 4: Ver Historial

```
1. .\bago-cli.ps1
   ↓
2. Selecciona [6] Analysis History
   ↓
3. Ver todos los análisis realizados
   ↓
4. Timestamps y resultados
```

---

## 📊 Salida Típica de Análisis

```
═══════════════════════════════════════════════════════════════
  EJECUTANDO ANÁLISIS
═══════════════════════════════════════════════════════════════

Ruta: C:\Marc_max_20gb\typing-course\src

▶ Iniciando orchestrator...

BAGO Code Quality Orchestrator
Launching specialized agents...

  ✓ security_analyzer → 2 hallazgos
  ✓ logic_checker → 5 hallazgos
  ✓ smell_detector → 0 hallazgos
  ✓ duplication_finder → 5 hallazgos

Synthesis of Findings
============================================================
Total issues: 4 tipos diferentes
  CRITICAL: 0
  HIGH: 5 hallazgos
  MEDIUM: 5 hallazgos
  LOW: 2 hallazgos

BAGO Role Orchestrator - Governance Review
========================================

Consulting ROLE: REVISOR_SEGURIDAD
  Status: CONDITIONAL
  Reason: High severity issues must be addressed

Consulting ROLE: REVISOR_PERFORMANCE
  Status: CONDITIONAL
  Reason: Code duplication should be refactored

MAESTRO_BAGO Synthesis
=====================
Final Verdict: CONDITIONAL

Recommendations:
  • Security: High severity issues must be addressed before production
  • Performance: Code duplication should be refactored for performance

✓ Análisis completado
```

---

## 🎨 Paleta de Colores

La CLI usa colores semánticos:

| Color | Uso |
|-------|-----|
| 🔵 Cyan | Headers y secciones |
| 🟢 Green | Éxito y confirmación |
| 🟡 Yellow | Advertencias |
| 🔴 Red | Errores |
| ⚪ White | Texto normal |
| 🟣 Magenta | Prompts |
| ⚫ Gray | Información sutil |

---

## ⚙️ Configuración

### Deshabilitar Colores

```powershell
.\bago-cli.ps1 -NoColor
```

**Casos de uso:**
- Entornos sin soporte ANSI
- Redirección a archivos
- Integración CI/CD

### Modo Verbose

```powershell
.\bago-cli.ps1 -Verbose
```

**Output adicional:**
- Paths del sistema
- Información de carga
- Debug logs

---

## 🔍 Troubleshooting

### ❌ "Cannot find path"

**Causa:** Directorio no encontrado  
**Solución:**
```powershell
cd C:\Marc_max_20gb\.bago
```

### ❌ "Script cannot be loaded"

**Causa:** Política de ejecución restringida  
**Solución:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### ❌ "No colores en la salida"

**Causa:** Terminal no soporta ANSI  
**Solución:**
```powershell
.\bago-cli.ps1 -NoColor
```

### ❌ "Agents no se ejecutan"

**Causa:** PowerShell o archivos .ps1 no en PATH  
**Solución:**
```powershell
# Verifica que existen los scripts
ls .\agents\*.py
ls .\code_quality_orchestrator.ps1
```

---

## 📈 Estadísticas del Sistema

```
╔═══════════════════════════════════════════════════════════╗
║              BAGO SYSTEM STATISTICS                      ║
╚═══════════════════════════════════════════════════════════╝

COMPONENTS:
  CLI Scripts:        3 (bago-cli.ps1, bago.ps1, cli.ps1)
  Agents Built-in:    4 (security, logic, smell, duplication)
  Agents Custom:      2 (registered)
  Roles Total:        16 (4 families)
  Documentation:      190+ .md files

CAPABILITIES:
  Analysis Types:     4 simultaneous agents
  Verdict Types:      3 (READY, CONDITIONAL, NOT_READY)
  Severity Levels:    4 (CRITICAL, HIGH, MEDIUM, LOW)
  Role Families:      4 (Gobierno, Especialistas, Supervisión, Producción)

PERFORMANCE:
  Analysis Time:      ~2-5 seconds
  Memory Usage:       Minimal (PowerShell)
  Scalability:        Extensible via factories

VERSION: 3.0-stable
STATUS: Verificado para demo local v3.0
EVIDENCE: .bago/CLI_v3_ENTREGA_FINAL.md
```

---

## 📚 Documentación Referencias

Para aprender más:

1. **CLI_QUICK_START.md** - Inicio rápido (este archivo)
2. **EJEMPLO_INTERACCION_COMPLETA.md** - Ejemplo paso a paso
3. **DEMO_EJECUCION_REAL.md** - Demo con outputs reales
4. **PHASE_4_5_GUIDE.md** - Guía arquitectónica completa
5. **AGENT_FACTORY_DOCUMENTATION.md** - Crear agents
6. **ROLE_FACTORY_DOCUMENTATION.md** - Crear roles

Accesibles desde la CLI: Selecciona [8] Help & Docs

---

## 🎓 Ejemplo Completo

```powershell
# 1. Inicia CLI
PS C:\Marc_max_20gb\.bago> .\bago-cli.ps1

# 2. Selecciona [9] Run Demo
Selecciona opción: 9

# 3. Ve el análisis real
DEMO DE EJECUCIÓN

Ejecutando demo con typing-course/src...

BAGO Code Quality Orchestrator
Launching specialized agents...
  OK: security_analyzer (findings: 2)
  OK: logic_checker (findings: 5)
  ...

Final Verdict: CONDITIONAL

# 4. Vuelve al menú y explora
Presiona Enter para continuar

# 5. Selecciona [3] View Roles
Selecciona opción: 3

# 6. Ver todas las familias de roles
ROLES DISPONIBLES

📦 GOBIERNO
   • MAESTRO_BAGO
   • ORQUESTADOR_CENTRAL
...

# 7. Selecciona [8] Help & Docs
Selecciona opción: 8

# 8. Lee documentación integrada
Documentos Disponibles:
[1] Guía Rápida
[2] Ejemplo Interacción Completa
...
```

---

## 🚀 Próximas Fases

### Phase 6: CI/CD Integration
- GitHub Actions workflows
- GitLab CI pipelines
- Pre-commit hooks
- Automated verdicts

### Phase 7: Dashboard
- Real-time metrics
- Historical tracking
- Trend analysis
- Team insights

### Phase 8: IDE Integration
- VS Code extension
- WebStorm plugin
- Real-time analysis

---

## 📞 Soporte

**¿Preguntas?**
- Lee CLI_QUICK_START.md
- Selecciona [8] Help & Docs en la CLI
- Ejecuta [9] Run Demo para ver en acción

**¿Errores?**
- Revisa la sección Troubleshooting
- Verifica que PowerShell v5+ está instalado
- Confirma que BAGO Path es correcto

---

**BAGO CLI v3.0 - Listo para usar** ✅
