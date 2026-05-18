# 🎯 BAGO CLI v3.0 - Guía de Inicio Rápido

## ✨ Novedades CLI v3.0

### Mejoras Principales
- ✅ **Menú profesional** con iconos y colores
- ✅ **Gestión de agents** (crear, listar, eliminar)
- ✅ **Gestión de roles** (crear, listar, ver familias)
- ✅ **Historial de análisis** persistente
- ✅ **Configuración personalizable** (colores, verbose, auto-guardar)
- ✅ **Acceso rápido a documentación** integrado
- ✅ **Demo interactiva** con un clic

---

## 🚀 Inicio Rápido

### Opción 1: CLI Interactiva (Recomendado)

```powershell
cd C:\Marc_max_20gb\.bago
.\bago-cli.ps1
```

**Pantalla inicial:**
```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              🎯 BAGO CLI v3.0                            ║
║         Code Quality Orchestrator                        ║
║                                                           ║
║    Líder de Agentes | Gobernanza por Roles              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

MAIN MENU

  [1]  Analyze Code         Ejecutar análisis completo
  [2]  View Agents          Listar agents disponibles
  [3]  View Roles           Listar roles y familias
  [4]  Create Agent         Crear nuevo agent
  [5]  Create Role          Crear nuevo role
  [6]  Analysis History     Ver historial de análisis
  [7]  Settings             Configuración
  [8]  Help & Docs          Documentación
  [9]  Run Demo             Demo de ejecución
  [0]  Exit                 Salir

Selecciona opción:
```

---

## 📋 Menú Completo y Opciones

### [1] Analyze Code - Analizar Proyecto

```
┌─ Input
│  └─ Ingresa ruta del proyecto (ej: ..\typing-course\src)
│
├─ Ejecución
│  ├─ Ejecuta 4 agents (security, logic, smell, duplication)
│  ├─ Agrega hallazgos por severidad
│  ├─ Consulta 3 roles (gobernanza)
│  └─ Emite veredicto final
│
└─ Output
   ├─ Hallazgos detallados
   ├─ Veredictos de roles
   └─ Recomendaciones accionables
```

**Ejemplo:**
```
Ingresa ruta del proyecto (ej: ..\typing-course\src): ..\typing-course\src

▶ Iniciando orchestrator...

BAGO Code Quality Orchestrator
Launching specialized agents...
  OK: security_analyzer (findings: 2)
  OK: logic_checker (findings: 5)
  OK: smell_detector (findings: 0)
  OK: duplication_finder (findings: 5)

Total issues: 12
  HIGH: 5
  MEDIUM: 5
  LOW: 2

Final Verdict: CONDITIONAL
```

---

### [2] View Agents - Ver Agents Disponibles

```
AGENTS DISPONIBLES

BUILT-IN AGENTS (4)

[1] SECURITY_ANALYZER
    Categoría: Seguridad
    Detecta XSS, SQL injection, credenciales

[2] LOGIC_CHECKER
    Categoría: Lógica
    Verifica TODO, inconsistencias

[3] SMELL_DETECTOR
    Categoría: Calidad
    Detecta variables globales, complejidad

[4] DUPLICATION_FINDER
    Categoría: Duplicación
    Encuentra código duplicado

CUSTOM AGENTS (2)

[5] PERFORMANCE_CHECKER
    Categoría: performance
    Estado: pending
    Creado: 04/28/2026 05:04:43
```

---

### [3] View Roles - Ver Roles y Familias

```
ROLES DISPONIBLES

📦 GOBIERNO
   • MAESTRO_BAGO
   • ORQUESTADOR_CENTRAL

📦 ESPECIALISTAS
   • REVISOR_SEGURIDAD
   • REVISOR_PERFORMANCE
   • REVISOR_UX
   • INTEGRADOR_REPO

📦 SUPERVISIÓN
   • AUDITOR_CANONICO
   • CENTINELA_SINCERIDAD
   • VERTICE

📦 PRODUCCIÓN
   • ANALISTA
   • ARQUITECTO
   • GENERADOR
   • ORGANIZADOR
   • VALIDADOR

TOTAL: 16 roles en 4 familias
```

---

### [4] Create Agent - Crear Nuevo Agent

```
CREAR NUEVO AGENT

Nombre del agent: my_custom_analyzer
Categoría (custom/security/logic/performance): custom
Descripción: Analiza patrones personalizados

✓ Agent creado exitosamente: my_custom_analyzer
```

**Lo que pasa internamente:**
1. El agent se registra en `manifests/custom_agents.json`
2. El agent se descubre automáticamente en próximos análisis
3. Puedes validar con `role_factory.py create` si lo prefieres

---

### [5] Create Role - Crear Nuevo Role

```
CREAR NUEVO ROLE

Nombre del role: REVISOR_CALIDAD
Familia (GOBIERNO/ESPECIALISTAS/SUPERVISIÓN/PRODUCCIÓN): ESPECIALISTAS
Propósito: Revisar calidad general del código

✓ Role 'REVISOR_CALIDAD' creado en familia 'ESPECIALISTAS'
⚠ Nota: Se creó el role. Usa role_factory.py para validación completa.
```

---

### [6] Analysis History - Ver Historial

```
HISTORIAL DE ANÁLISIS

[2026-04-28 05:19:25]
  Proyecto: C:\Marc_max_20gb\typing-course\src
  Estado: Completed

[2026-04-28 05:18:50]
  Proyecto: C:\Marc_max_20gb\bago
  Estado: Completed
```

---

### [7] Settings - Configuración

```
CONFIGURACIÓN

Configuración Actual:

  Color Habilitado: True
  Modo Verbose: False
  Auto-Guardar: True
  Máximo Historial: 10

[1] Alternar colores
[2] Alternar verbose
[3] Alternar auto-guardar
[0] Volver

Selecciona:
```

**Opciones:**
- **Colores:** Desactivar para entornos sin soporte de colores ANSI
- **Verbose:** Mostrar información de depuración
- **Auto-Guardar:** Guardar análisis en historial automáticamente

---

### [8] Help & Docs - Documentación

```
AYUDA Y DOCUMENTACIÓN

Documentos Disponibles:

[1] Guía Rápida
[2] Ejemplo Interacción Completa
[3] Demo Ejecución Real
[4] Documentación Agents
[5] Documentación Roles
[6] Verificación de Componentes
[0] Volver

Selecciona documento:
```

**Abre automáticamente en Notepad:**
- `PHASE_4_5_GUIDE.md` - Guía completa de Phase 4-5
- `EJEMPLO_INTERACCION_COMPLETA.md` - Ejemplo paso a paso
- `DEMO_EJECUCION_REAL.md` - Demostración real
- `AGENT_FACTORY_DOCUMENTATION.md` - Cómo crear agents
- `ROLE_FACTORY_DOCUMENTATION.md` - Cómo crear roles
- `VERIFICACION_COMPONENTES_Y_ESTADO.md` - Estado del sistema

---

### [9] Run Demo - Demo de Ejecución

```
DEMO DE EJECUCIÓN

Ejecutando demo con typing-course/src...

BAGO Code Quality Orchestrator
Launching specialized agents...
  OK: security_analyzer (findings: 2)
  OK: logic_checker (findings: 5)
  OK: smell_detector (findings: 0)
  OK: duplication_finder (findings: 5)

... (output completo) ...

Final Verdict: CONDITIONAL
```

---

## 🎮 Controles y Navegación

### Teclado
- **Números** [0-9]: Seleccionar opciones
- **Enter**: Confirmar selección
- **Ctrl+C**: Salir en cualquier momento

### Colores (Semantic)
- 🔵 **Cyan** = Headers y secciones principales
- 🟢 **Green** = Éxito y operaciones completadas
- 🟡 **Yellow** = Advertencias
- 🔴 **Red** = Errores y salida
- ⚪ **White** = Texto normal
- 🟣 **Magenta** = Prompts de entrada
- ⚫ **Gray** = Texto sutil/secundario

---

## 🔧 Línea de Comandos (CLI Alternativa)

Si prefieres la CLI basada en comandos (sin menú interactivo):

```powershell
# Ver ayuda
.\bago.ps1 help

# Analizar proyecto
.\bago.ps1 analyze ..\typing-course\src

# Listar agents
.\bago.ps1 list-agents

# Listar roles
.\bago.ps1 list-roles

# Crear nuevo agent
.\bago.ps1 new-agent "mi_agent" -Category "custom"

# Eliminar agent
.\bago.ps1 remove-agent "mi_agent"
```

---

## 📊 Flujo Típico de Uso

```
1. Ejecutar CLI
   ↓
2. Seleccionar [1] Analyze Code
   ↓
3. Ingresar ruta del proyecto
   ↓
4. Ver hallazgos y verdicts
   ↓
5. Opcionalmente:
   - Ver [2] Agents
   - Ver [3] Roles
   - Ver [6] History
   - Leer [8] Docs
   ↓
6. Corregir código según recomendaciones
   ↓
7. Re-analizar [1] Analyze Code
   ↓
8. Verificar que verdict mejoró
```

---

## 🎓 Ejemplos Completos

### Ejemplo 1: Primer Análisis

```
$ .\bago-cli.ps1
[Menu aparece]

Selecciona opción: 1

Ingresa ruta del proyecto: ..\typing-course\src

▶ Iniciando orchestrator...

[Agents se ejecutan...]

BAGO VERDICT: CONDITIONAL
• Security: High severity issues must be addressed
• Performance: Code duplication should be refactored

✓ Análisis completado
```

### Ejemplo 2: Crear Nuevo Agent

```
Selecciona opción: 4

CREAR NUEVO AGENT

Nombre del agent: cache_validator
Categoría: performance
Descripción: Valida estrategias de caché

✓ Agent creado exitosamente: cache_validator
```

### Ejemplo 3: Ver Roles

```
Selecciona opción: 3

📦 GOBIERNO
   • MAESTRO_BAGO
   • ORQUESTADOR_CENTRAL

📦 ESPECIALISTAS
   • REVISOR_SEGURIDAD
   • REVISOR_PERFORMANCE
   ...

TOTAL: 16 roles en 4 familias
```

---

## ⚙️ Configuración Avanzada

### Deshabilitar Colores

```powershell
.\bago-cli.ps1 -NoColor
```

Útil para:
- Entornos sin soporte ANSI
- Logs en archivos
- Integración CI/CD

### Modo Verbose

```powershell
.\bago-cli.ps1 -Verbose
```

Output:
```
Verbose Mode Enabled
BAGO Path: C:\Marc_max_20gb\.bago
[CLI inicia con debug info]
```

---

## 📞 Soporte y Troubleshooting

### ¿La CLI no inicia?
```powershell
# Verifica que PowerShell puede ejecutar scripts
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Intenta de nuevo
.\bago-cli.ps1
```

### ¿Los colores no aparecen?
```powershell
# Ejecuta sin colores
.\bago-cli.ps1 -NoColor
```

### ¿Quiero ver logs detallados?
```powershell
# Ejecuta en modo verbose
.\bago-cli.ps1 -Verbose
```

---

## 🚀 Próximos Pasos

1. **Primero:** Ejecuta `.\bago-cli.ps1`
2. **Segundo:** Selecciona [9] Run Demo para ver un análisis de ejemplo
3. **Tercero:** Selecciona [8] Help & Docs para leer la documentación
4. **Cuarto:** Selecciona [1] Analyze Code con tu proyecto

---

**BAGO CLI v3.0 - Listo para uso productivo** ✅
