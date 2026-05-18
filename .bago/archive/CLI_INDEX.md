# 🎯 BAGO CLI - Índice de Referencia Rápida

**Versión:** 3.0  
**Status:** ✅ Productivo  
**Última actualización:** 2026-04-28 05:22:10

---

## 📍 Ubicación Rápida

| Necesidad | Documento | Link |
|-----------|-----------|------|
| 🚀 Empezar YA | CLI_QUICK_START.md | [Ir](./CLI_QUICK_START.md) |
| 📖 Leer el README | CLI_README.md | [Ir](./CLI_README.md) |
| 🔗 Integración completa | CLI_v3_INTEGRACION_COMPLETA.md | [Ir](./CLI_v3_INTEGRACION_COMPLETA.md) |
| 📋 Este índice | CLI_INDEX.md | Aquí |

---

## 🎮 Archivo Principal

```
bago-cli.ps1 (15.0 KB)
├─ Menú interactivo profesional v3.0
├─ 9 opciones principales
├─ Gestión completa de agents y roles
├─ Historial automático
├─ Configuración personalizable
├─ Documentación integrada
└─ ✅ RECOMENDADO - Usar este
```

**Cómo ejecutar:**
```powershell
cd C:\Marc_max_20gb\.bago
.\bago-cli.ps1
```

---

## 🎯 Menú de Opciones

```
[1] Analyze Code
    └─ Ejecutar análisis de proyecto
       Input: Ruta del proyecto
       Output: Hallazgos, severidad, verdicts

[2] View Agents
    └─ Listar agents disponibles
       Muestra: 4 built-in + custom
       Información: Nombre, categoría, descripción

[3] View Roles
    └─ Ver roles en 4 familias
       Muestra: 16 roles totales
       Familias: Gobierno, Especialistas, Supervisión, Producción

[4] Create Agent
    └─ Crear nuevo agent custom
       Input: Nombre, categoría, descripción
       Resultado: Registrado en manifests/custom_agents.json

[5] Create Role
    └─ Crear nuevo role
       Input: Nombre, familia, propósito
       Nota: Validar con role_factory.py

[6] Analysis History
    └─ Ver historial de análisis
       Muestra: Timestamp, proyecto, estado
       Máximo: 10 análisis

[7] Settings
    └─ Configuración personalizada
       Opciones: Colores, Verbose, Auto-guardar
       Alcance: Sesión actual

[8] Help & Docs
    └─ Acceder a documentación integrada
       Documentos: 6 guías y referencias
       Abre: Automáticamente en Notepad

[9] Run Demo
    └─ Ejecutar análisis de demo
       Proyecto: typing-course/src
       Muestra: Agents, hallazgos, verdicts
       Educativo: Aprende el flujo

[0] Exit
    └─ Salir de la CLI
```

---

## 🔧 Línea de Comandos (Alternativa)

Si prefieres no usar el menú:

```powershell
# CLI basada en comandos (bago.ps1)
.\bago.ps1 help
.\bago.ps1 analyze ..\typing-course\src
.\bago.ps1 list-agents
.\bago.ps1 list-roles
.\bago.ps1 new-agent "nombre" -Category "custom"
.\bago.ps1 remove-agent "nombre"
```

---

## 📊 Flujos de Uso Recomendados

### Flujo A: Análisis Rápido (5 min)
```
1. .\bago-cli.ps1
2. [1] Analyze Code
3. Ingresar ruta
4. Ver resultados
5. [0] Exit
```

### Flujo B: Aprendizaje (20 min)
```
1. .\bago-cli.ps1
2. [9] Run Demo (ver en acción)
3. [2] View Agents (entender especialistas)
4. [3] View Roles (entender gobernanza)
5. [8] Help & Docs (leer documentación)
6. [1] Analyze Code (usar)
7. [0] Exit
```

### Flujo C: Desarrollo Iterativo (30+ min)
```
1. .\bago-cli.ps1
2. [1] Analyze Code → proyecto
3. Ver hallazgos (NOT_READY)
4. [0] Exit (editar código)
5. .\bago-cli.ps1
6. [6] Analysis History (ver previos)
7. [1] Analyze Code → proyecto (re-analizar)
8. Ver hallazgos mejorados (CONDITIONAL)
9. Iterar hasta READY
```

### Flujo D: Extensión (10 min)
```
1. .\bago-cli.ps1
2. [4] Create Agent (crear custom agent)
3. [1] Analyze Code (probar)
4. Agent se usa automáticamente
5. Ver en acción
6. [0] Exit
```

---

## 📚 Documentación Disponible

### Integrada en CLI (Opción [8])

| # | Documento | Tamaño | Contenido |
|---|-----------|--------|----------|
| 1 | PHASE_4_5_GUIDE.md | 10.3 KB | Guía arquitectónica completa |
| 2 | EJEMPLO_INTERACCION_COMPLETA.md | 17.1 KB | Ejemplo paso a paso |
| 3 | DEMO_EJECUCION_REAL.md | 10.3 KB | Demo con outputs reales |
| 4 | AGENT_FACTORY_DOCUMENTATION.md | 14.0 KB | Cómo crear agents |
| 5 | ROLE_FACTORY_DOCUMENTATION.md | 10.4 KB | Cómo crear roles |
| 6 | VERIFICACION_COMPONENTES_Y_ESTADO.md | 8.7 KB | Verificación del sistema |

### CLI-Específicos

| Documento | Tamaño | Propósito |
|-----------|--------|----------|
| CLI_QUICK_START.md | 9.98 KB | Inicio rápido |
| CLI_README.md | 10.36 KB | README completo |
| CLI_v3_INTEGRACION_COMPLETA.md | 12.9 KB | Integración detallada |
| CLI_INDEX.md | Este archivo | Índice y referencia |

---

## ⚙️ Configuración

### Arranque Estándar
```powershell
.\bago-cli.ps1
```

### Sin Colores (CI/CD)
```powershell
.\bago-cli.ps1 -NoColor
```

### Modo Verbose (Debug)
```powershell
.\bago-cli.ps1 -Verbose
```

### Ambos
```powershell
.\bago-cli.ps1 -NoColor -Verbose
```

---

## 🎨 Paleta de Colores

```
Cyan     → Headers, títulos principales
Green    → Éxito, confirmación
Yellow   → Advertencias, recomendaciones
Red      → Errores, salida
White    → Texto normal
Magenta  → Prompts de entrada
Gray     → Información sutil
```

---

## 🔍 Troubleshooting Rápido

| Problema | Solución |
|----------|----------|
| "Script cannot be loaded" | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| "File not found" | `cd C:\Marc_max_20gb\.bago` |
| "No colors" | `.\bago-cli.ps1 -NoColor` |
| "Agents not running" | `ls agents\*.py` (verificar existen) |
| "PowerShell old" | Upgrade a PowerShell 5.0+ |

---

## 🚀 Próximos Pasos

### Ahora
- [ ] Ejecutar `.\bago-cli.ps1`
- [ ] Ver [9] Run Demo
- [ ] Explorar menú

### Hoy
- [ ] Analizar tu proyecto [1]
- [ ] Crear custom agent [4]
- [ ] Leer documentación [8]

### Esta semana
- [ ] Integrar en CI/CD
- [ ] Setup pre-commit hooks
- [ ] Crear roles custom

### Este mes
- [ ] Dashboard de métricas
- [ ] IDE integration
- [ ] Historical tracking

---

## 📞 Referencia Rápida

```
START:         cd C:\Marc_max_20gb\.bago && .\bago-cli.ps1
DEMO:          Opción [9] en el menú
ANALYZE:       Opción [1] en el menú
AGENTS:        Opción [2] en el menú
ROLES:         Opción [3] en el menú
CREATE AGENT:  Opción [4] en el menú
CREATE ROLE:   Opción [5] en el menú
HISTORY:       Opción [6] en el menú
SETTINGS:      Opción [7] en el menú
DOCS:          Opción [8] en el menú
EXIT:          Opción [0] en el menú
```

---

## ✅ Checklist de Éxito

- [ ] bago-cli.ps1 existe
- [ ] Menú colorido se muestra
- [ ] Números 0-9 responden
- [ ] [1] Analyze funciona
- [ ] [2] Agents se listan (4)
- [ ] [3] Roles se listan (16)
- [ ] [9] Demo funciona
- [ ] [8] Docs abre archivos
- [ ] [4] Create Agent funciona
- [ ] Colores se ven bien (o -NoColor desactiva)

Si todo ✅ → **BAGO CLI v3.0 está operativo**

---

## 📊 Estadísticas

```
Archivos PowerShell:     4 (1 new v3.0, 3 legacy)
Documentación:           10 (6 integradas + 4 CLI)
Agents disponibles:      4 built-in + extensible
Roles disponibles:       16 en 4 familias
Opciones menú:           9 + exit
Configuraciones:         3 (color, verbose, auto-guardar)
Documentos en CLI:       6 (accesibles desde [8])

Version:                 3.0-stable
Status:                  Verificado para demo local v3.0
Evidence:                .bago/CLI_v3_ENTREGA_FINAL.md
```

---

## 🎓 Recursos Externos

### Documentación General
- `README.md` - Proyecto general
- `WORKSPACE.md` - Workspace setup

### BAGO Específico
- `DOCUMENTATION_INDEX.md` - Índice general
- `PHASE_4_5_GUIDE.md` - Architecture

### CLI Específico
- `CLI_QUICK_START.md` - Quick start
- `CLI_README.md` - Full reference
- `CLI_v3_INTEGRACION_COMPLETA.md` - Integration details
- `CLI_INDEX.md` - Este archivo

---

## 🎯 Inicio Rápido de 30 Segundos

```powershell
# 1. Navega a BAGO
cd C:\Marc_max_20gb\.bago

# 2. Inicia CLI
.\bago-cli.ps1

# 3. Selecciona opción
Selecciona opción: 9

# 4. ¡Ve en acción!
[Demo se ejecuta]

# 5. Explora
Selecciona opción: 2
Presiona Enter
Selecciona opción: 3

# 6. Cierra
Selecciona opción: 0
```

---

**BAGO CLI v3.0 - Índice de Referencia**  
**Última actualización:** 2026-04-28 05:22:10  
**Status:** ✅ COMPLETO Y OPERATIVO
