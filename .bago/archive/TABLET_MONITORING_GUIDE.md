# 📱 BAGO Agent Monitor - Implementación en Tablet via ADB

**Versión:** 1.0  
**Plataforma:** Windows PC + Android Tablet  
**Fecha:** 2026-04-28

---

## 🎯 Descripción General

Sistema de monitorización en tiempo real que permite ver el estado de los agentes BAGO desde una **tablet Android** conectada vía **ADB (Android Debug Bridge)**.

### Arquitectura

```
Windows PC (BAGO)          Android Tablet
┌──────────────────┐       ┌─────────────────┐
│ BAGO Framework   │       │  Web Browser    │
│ ├─ 4 Agents      │◄──►   │  (Chrome/Firefox)
│ ├─ Monitor API   │       │  Dashboard HTML │
│ └─ REST HTTP     │  USB  │  (Responsive)   │
└──────────────────┘       └─────────────────┘
     Port 8080                 ADB Forward
```

---

## 📋 Requisitos Previos

### En Windows PC

```
✅ BAGO Framework completo (ya instalado)
✅ PowerShell 5.0+
✅ Android SDK / ADB instalado
   - C:\Android\platform-tools\adb.exe
   - O en PATH del sistema
```

### En Tablet Android

```
✅ Android 8.0+ (API 26+)
✅ USB Debugging habilitado
✅ Conexión USB al PC
✅ Chrome, Firefox o navegador moderno
```

---

## 🔧 Setup en Windows PC

### Paso 1: Verificar ADB

```powershell
# Ubicar ADB
where adb

# Si no está en PATH, agregarlo:
$env:Path += ";C:\Android\platform-tools"

# Verificar disponibilidad
adb version

# Output esperado:
# Android Debug Bridge version x.x.x
```

### Paso 2: Iniciar Monitor Service

```powershell
cd C:\Marc_max_20gb\.bago

# Opción 1: Con puerto por defecto (8080)
.\agents-monitor-service.ps1

# Opción 2: Con puerto personalizado
.\agents-monitor-service.ps1 -Port 9090

# Output esperado:
# BAGO Agent Monitor Service
# =========================
# Port: 8080
# Interval: 5s
# Access dashboard at: http://localhost:8080
```

### Paso 3: Verificar en PC

```
Abre navegador: http://localhost:8080

Verás el dashboard con:
✓ Estado de agentes
✓ Métricas del sistema
✓ Historial de análisis
```

---

## 📱 Setup en Tablet Android

### Paso 1: Habilitar USB Debugging

```
Android Settings
├─ About Phone/Tablet
├─ Build Number (7 toques)
├─ Developer Options (aparece)
├─ USB Debugging: ON
└─ USB Connection: Allow
```

### Paso 2: Conectar Tablet al PC

```powershell
# En PowerShell (con adb en PATH):

# Conectar
adb connect tablet_ip:5555
# O si está por USB:
adb devices

# Verificar conexión
adb devices
# Output:
# List of attached devices
# XXXXXXXX       device
```

### Paso 3: Configurar Port Forward (ADB)

```powershell
# Redirigir puerto 8080 del PC al tablet
adb reverse tcp:8080 tcp:8080

# Verificar
adb reverse --list
# Output:
# tcp:8080 tcp:8080
```

### Paso 4: Abrir Dashboard en Tablet

```
Chrome/Firefox en Tablet
└─ URL: http://localhost:8080
   O: 127.0.0.1:8080

Resultado:
✓ Dashboard funcional en la prueba local documentada
✓ Actualizaciones en tiempo real
✓ Interfaz táctil responsive
```

---

## 📊 Dashboard - Características

### Panel de Control Principal

```
┌─────────────────────────────────────────────────┐
│  🎯 BAGO Agent Monitor                          │
│  Sistema en línea | Actualizado: 14:23:45      │
├─────────────────────────────────────────────────┤
│  📊 Estado General   │  🤖 Agentes    │ 💻 Sist │
│  ┌─────────────────┐ │ ┌────────────┐ │┌─────┐ │
│  │ Análisis: 42    │ │ │Security... │ ││CPU: │ │
│  │ Hallazgos: 128  │ │ │Logic...    │ ││45%  │ │
│  │ Activos: 1      │ │ │Smell...    │ │├─────┤ │
│  └─────────────────┘ │ │Duplicat... │ ││RAM:  │ │
│                      │ └────────────┘ ││2.1GB│ │
│  📋 Historial       │                 │└─────┘ │
│  ├─ 14:23 Security... (2 hallazgos)   │        │
│  ├─ 14:22 Logic... (5 hallazgos)      │        │
│  ├─ 14:21 Smell... (0 hallazgos)      │        │
│  └─ [Actualizar Ahora]                │        │
└─────────────────────────────────────────────────┘
```

### Secciones

#### 1. Estado General
```
- Total de análisis ejecutados
- Total de hallazgos detectados
- Agentes activos en este momento
```

#### 2. Agentes
```
Para cada agent muestra:
- Nombre del agent
- Estado actual (IDLE, RUNNING, FAILED)
- Contador de ejecuciones
- Contador de éxitos
```

#### 3. Métricas del Sistema
```
- CPU Usage (%)
- Memory Usage (GB)
- Disk Usage (GB)
```

#### 4. Historial Reciente
```
Últimos 10 eventos:
- Timestamp
- Agent que ejecutó
- Status
- Número de hallazgos
```

---

## 🔄 Flujo de Funcionamiento

### Escenario Típico

```
1. PC: Iniciar Monitor Service
   ↓
   .\agents-monitor-service.ps1
   
2. Tablet: Conectar via USB y habilitar forwarding
   ↓
   adb reverse tcp:8080 tcp:8080
   
3. Tablet: Abrir Chrome en http://localhost:8080
   ↓
   Dashboard aparece
   
4. PC: BAGO ejecuta análisis
   ↓
   Agents: security, logic, smell, duplication
   
5. Monitor: Registra ejecución
   ↓
   Actualiza estado de agents
   
6. Tablet: Dashboard actualiza cada 5 segundos
   ↓
   Ve en tiempo real el progreso
   
7. Usuario: Monitoriza desde la tablet
   ↓
   Tap en "Actualizar Ahora" para refresh manual
```

---

## 📡 API REST Endpoints

El monitor expone estos endpoints automáticamente:

### `/api/agents`
```
GET http://localhost:8080/api/agents

Response:
[
  {
    "Name": "security_analyzer",
    "Status": "idle",
    "ExecutionsCount": 15,
    "SuccessCount": 14,
    "AvgExecutionTime": 2500,
    "RecentFindings": [...]
  },
  ...
]
```

### `/api/status`
```
GET http://localhost:8080/api/status

Response:
{
  "IsRunning": true,
  "Uptime": "00:45:30.1234567",
  "TotalAnalyses": 42,
  "TotalFindings": 128,
  "ActiveAgents": 1,
  "IdleAgents": 3,
  "Timestamp": "2026-04-28T14:23:45"
}
```

### `/api/metrics`
```
GET http://localhost:8080/api/metrics

Response:
{
  "CPUUsage": 45,
  "MemoryUsage": 2.1,
  "DiskUsage": 456.8,
  "Timestamp": "2026-04-28T14:23:45"
}
```

### `/api/history`
```
GET http://localhost:8080/api/history

Response:
[
  {
    "Agent": "security_analyzer",
    "Status": "idle",
    "Timestamp": "2026-04-28T14:23:40",
    "Duration": 2500,
    "FindingsCount": 2,
    "Success": true
  },
  ...
]
```

### `/dashboard`
```
GET http://localhost:8080/dashboard
GET http://localhost:8080/

Response:
HTML5 responsive dashboard (web app)
```

---

## 🎮 Uso Interactivo en Tablet

### Interacciones Disponibles

```
✓ Tap en [Actualizar Ahora]
  └─ Refresh manual del dashboard

✓ Scroll en Historial
  └─ Ver eventos anteriores

✓ Landscape/Portrait
  └─ Interfaz se adapta automáticamente

✓ Color del estado del agent
  ├─ Verde (IDLE) - Listo
  ├─ Azul (RUNNING) - Ejecutándose
  └─ Rojo (FAILED) - Error
```

### Casos de Uso

#### Caso 1: Monitoreo Pasivo
```
1. Tablet en stand/soporte
2. Dashboard visible en tiempo real
3. Ver análisis en progreso mientras trabajas
```

#### Caso 2: Monitoreo Activo
```
1. Tablet en mano
2. Tap [Actualizar Ahora] cuando quieras
3. Ver métricas en tiempo real
4. Foto/captura de pantalla para reportes
```

#### Caso 3: Demostración
```
1. Ejecutar BAGO análisis en PC
2. Mostrar dashboard en tablet a stakeholders
3. Demostrar agentes en acción
4. Mostrar hallazgos en tiempo real
```

---

## 🐛 Troubleshooting

### ❌ "adb: command not found"

```
Solución:
1. Descargar Android SDK Platform Tools
   https://developer.android.com/studio/releases/platform-tools

2. Extraer a C:\Android\platform-tools

3. Agregar a PATH:
   $env:Path += ";C:\Android\platform-tools"

4. Reiniciar PowerShell

5. Verificar:
   adb version
```

### ❌ "Tablet no aparece en adb devices"

```
Verificar:
1. USB Debugging habilitado en tablet
   Settings → Developer Options → USB Debugging ON

2. Cable USB conectado (no solo cargador)

3. Permitir acceso en tablet
   "Allow USB debugging from this computer?" → OK

4. Reconectar:
   adb reconnect device
```

### ❌ "Port 8080 already in use"

```
Solución:
1. Usar puerto diferente:
   .\agents-monitor-service.ps1 -Port 9090

2. O matar proceso en puerto:
   netstat -ano | findstr :8080
   taskkill /PID <PID> /F
```

### ❌ "Dashboard no carga en tablet"

```
Verificar:
1. Monitor service activo en PC:
   netstat -ano | findstr :8080
   
2. Port forwarding configurado:
   adb reverse --list
   
3. URL correcta en tablet:
   http://localhost:8080 (si adb reverse activo)
   O: http://<PC_IP>:8080 (si en red local)
```

### ❌ "Datos no actualizan en tiempo real"

```
Solución:
1. Verificar conexión USB
2. Reiniciar Monitor service
3. Tap [Actualizar Ahora] en tablet
4. Verificar API:
   Abre http://localhost:8080/api/status en PC
```

---

## 📱 Dispositivos Recomendados

### Tablets Soportadas

```
✓ iPad (iOS 12+) - vía navegador
✓ Samsung Galaxy Tab (Android 8+)
✓ Lenovo Tab (Android 8+)
✓ Amazon Fire Tablets (Fire OS 5+)
✓ Cualquier tablet con navegador moderno
```

### Requisitos Mínimos

```
📱 Pantalla: 7" - 13"
📱 RAM: 2GB mínimo (4GB recomendado)
📱 Android: 8.0+ (12+ recomendado)
📱 Conexión: USB 2.0+
📱 Navegador: Chrome 80+ o Firefox 78+
```

---

## 🔐 Seguridad

### En Red Local

```
✅ Si tablet y PC en misma red LAN:
   URL en tablet: http://<PC_IP>:8080

✓ Conexión es HTTP local (no requiere HTTPS)
✓ Solo accesible desde red local
```

### Via ADB

```
✅ ADB forwarding más seguro que red local
   adb reverse tcp:8080 tcp:8080

✓ Solo en PC conectado vía USB
✓ No expone a internet
✓ Requiere habilitación USB Debugging
```

### Recomendaciones

```
1. No exponer Puerto 8080 a internet
2. Usar ADB reverse en lugar de red abierta
3. Solo permitir en red local corporativa
4. Deshabilitar USB Debugging cuando no esté en uso
```

---

## 📊 Ejemplo de Salida Completa

### En PC - PowerShell

```
PS C:\Marc_max_20gb\.bago> .\agents-monitor-service.ps1

BAGO Agent Monitor Service
=========================
Port: 8080
Interval: 5s
Access dashboard at: http://localhost:8080

Monitor API listening on http://localhost:8080

[Ejecutando monitorización...]
```

### En Tablet - Dashboard

```
🎯 BAGO Agent Monitor
Sistema en línea | Actualizado: 14:23:45

📊 Estado General    🤖 Agentes          💻 Sistema
┌──────────────────┐ ┌────────────────┐ ┌──────────┐
│ Análisis: 42     │ │ SECURITY_ANALY │ │ CPU: 45% │
│ Hallazgos: 128   │ │ IDLE (15 exec) │ │ RAM: 2.1 │
│ Activos: 1       │ │ LOGIC_CHECKER  │ │ Disk: 456│
└──────────────────┘ │ IDLE (14 exec) │ └──────────┘
                     │ SMELL_DETECTOR │
📋 Historial        │ IDLE (0 exec)  │
14:23 SECURITY (2)  │ DUPLICAT...    │
14:22 LOGIC (5)     │ RUNNING...     │
14:21 SMELL (0)     │ (1/4 active)   │
[Actualizar Ahora]  └────────────────┘
```

---

## 🚀 Próximos Pasos

### Inmediatos
1. ✅ Iniciar Monitor Service
2. ✅ Conectar tablet vía ADB
3. ✅ Abrir dashboard en tablet
4. ✅ Ver monitorización en tiempo real

### Corto Plazo
1. Crear alertas personalizadas
2. Exportar reportes desde tablet
3. Notificaciones push en tablet
4. Integración con Slack/Teams

### Largo Plazo
1. App nativa Android
2. Histórico persistente (base de datos)
3. Comparativas de análisis
4. Dashboard multi-dispositivo

---

## 📚 Referencia Rápida

```
INICIAR:           .\agents-monitor-service.ps1
ACCEDER:           http://localhost:8080
CONECTAR TABLET:   adb reverse tcp:8080 tcp:8080
VERIFICAR ADB:     adb devices
PUERTO CUSTOM:     .\agents-monitor-service.ps1 -Port 9090
VERBOSE:           .\agents-monitor-service.ps1 -Verbose
API AGENTS:        http://localhost:8080/api/agents
API STATUS:        http://localhost:8080/api/status
API METRICS:       http://localhost:8080/api/metrics
API HISTORY:       http://localhost:8080/api/history
PARAR:             Ctrl+C en PowerShell
```

---

**BAGO Agent Monitor - Monitorización desde Tablet Android** ✅
