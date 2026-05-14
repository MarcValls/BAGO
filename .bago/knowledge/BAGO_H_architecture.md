# BAGO_H — Arquitectura Portable & Instalada

## Jerarquía de Fuentes de Verdad

### 1. Dispositivo Extraíble (Pendrive) — Modo PORTABLE
```
D:\BAGO\              ← raíz portable (o E:\, F:\, cualquier letra)
├── .bago\            ← configuración portable
│   ├── knowledge\    ← aprendizajes locales del usuario
│   ├── state\         ← estado de sesión portable
│   └── mcp\           ← MCP portable
├── bago.cmd          ← launcher Windows
├── bago.sh           ← launcher Unix
└── models\            ← modelos locales descargados
    └── qwen25-coder\ ← 4.5GB
```
**Regla:** Si BAGO se inicia desde un dispositivo extraíble, el `.bago`
del pendrive es la fuente de verdad. No escribe en el PC.

### 2. PC Instalado — Modo FULL_LLM
```
C:\Users\{user}\BAGO\        ← o C:\Program Files\BAGO\
├── .bago\                     ← configuración full
│   ├── knowledge\             ← 37+ archivos indexados
│   ├── state\                  ← estado persistente
│   ├── tools\                  ← scripts del framework
│   └── models\                 ← catálogo de modelos disponibles
├── bago.cmd                    ← launcher global (PATH)
├── bago.ps1                    ← PowerShell launcher
└── bin\                        ← binarios (Ollama, etc.)
```
**Regla:** Si BAGO está instalado en el PC, el `.bago` del PC es la
fuente de verdad. Puede usar modelos locales, cloud, y copilot.

### 3. Ambos Presentes — Modo SYNC
```
PC:  C:\Users\Marc\BAGO\.bago\      ← fuente de verdad PRIMARY
USB: D:\BAGO\.bago\                 ← fuente de verdad SECONDARY
```
**Regla:** Si ambos existen:
- El PC es PRIMARY (full capacidades)
- El USB es MIRROR (sincroniza knowledge + state)
- BAGO avisa: "Fuente de verdad: C:\... (PC). USB como backup activo."

## Algoritmo de Detección (bago_locate.py)

```python
def locate_bago() -> Path:
    """
    1. ¿Desde dónde se ejecutó el script? (argv[0])
    2. ¿Hay un .bago en el mismo directorio? → PORTABLE
    3. ¿Hay un .bago en %USERPROFILE%\BAGO? → INSTALLED
    4. ¿Hay ambos? → PC es PRIMARY, USB notifica como SECONDARY
    5. ¿Ninguno? → Modo PRIMERA_VEZ: preguntar al usuario
    """
```

## Comandos del Launcher

### `BAGO launch [modelo]`
```bash
BAGO launch                    ← modelo por defecto (qwen25-coder)
BAGO launch codex              ← lanza Codex CLI con config BAGO
BAGO launch copilot            ← lanza GitHub Copilot CLI
BAGO launch kimi               ← lanza Ollama cloud con Kimi
BAGO launch gpt-5.5            ← lanza Codex con GPT-5.5
```

### `BAGO install [modelo|herramienta]`
```bash
BAGO install qwen25-coder      ← descarga modelo Ollama local
BAGO install codex             ← instala Codex CLI
BAGO install copilot           ← instala gh copilot
BAGO install BAGO_H.1          ← futuro: modelo propio
```

### `BAGO status`
```bash
Fuente de verdad:  C:\Users\Marc\BAGO\.bago\  (PC INSTALADO)
Modelos locales:    qwen25-coder (4.5GB), llama32 (1.9GB)
Modelos cloud:      kimi-k2-1t, devstral-2, deepseek-v3
Agentes disponibles: MAESTRO, ANALISTA, ARQUITECTO, CENTINELA...
Conexión GitHub:    conectado (MarcValls/BAGO)
USB detectado:      D:\BAGO\  (sincronizado)
```

## Flujo de Instalación

### Primera vez (desde pendrive)
```
1. Usuario inserta USB
2. Ejecuta D:\BAGO\bago.cmd
3. BAGO detecta: "Modo PORTABLE. ¿Instalar en PC para full LLM?"
4. Si sí: copia .bago a %USERPROFILE%\BAGO\, añade PATH
5. Si no: sigue en modo portable, USB es fuente de verdad
```

### Primera vez (desde web/GitHub)
```
1. git clone https://github.com/MarcValls/BAGO.git
2. cd BAGO; .\install.cmd
3. Pregunta: directorio de instalación (default: %USERPROFILE%\BAGO)
4. Descarga modelos por defecto (qwen25-coder)
5. Configura PATH: bago.cmd disponible globalmente
```

## Sincronización USB ↔ PC

### Qué sincroniza:
- `.bago/knowledge/`      ← aprendizajes del usuario
- `.bago/state/`          ← estado de sesiones, historial
- `.bago/registry.json`   ── progresos y metadatos

### Qué NO sincroniza:
- `bin/`                  ← binarios dependen de arquitectura
- `models/`               ← modelos son grandes (4-20GB cada uno)

### Frecuencia:
- Al cerrar sesión: "¿Sincronizar cambios con USB?"
- Manual: `BAGO sync --to-usb` o `BAGO sync --from-usb`

## Repositorio Git del Usuario

### `BAGO repo init`
```bash
BAGO repo init                    ← crea repo local, conecta a GitHub
BAGO repo init --private         ← repo privado
BAGO repo sync                   ← sube progresos
```

### Estructura del repo del usuario:
```
{user-repo}/
├── README.md                     ← auto-generado con estado
├── .bago/                         ← symlink a la fuente de verdad
├── projects/                      ← proyectos del usuario
├── progress/                      ← informes de aprendizaje
│   └── 2026-05-14_session.md
└── .github/
    └── workflows/
        └── bago-sync.yml          ← CI: sube aprendizajes automáticamente
```

## Informes de Aprendizaje → BAGO Central

### `BAGO contribute`
```bash
BAGO contribute                  ← prepara informe de aprendizajes
# Pregunta:
# - ¿Qué aprendiste hoy?
# - ¿Qué modelo usaste?
# - ¿Qué función de BAGO mejorarías?
# Genera: .bago/state/contribution_2026-05-14.md
# Sube a: https://github.com/MarcValls/BAGO/issues/new
```

### Recompensa:
- Cada contribución añade puntos al perfil del usuario
- Acceso prioritario a BAGO_H.1 cuando esté disponible
- Mención en CHANGELOG.md

## BAGO_H.1 — Modelo Futuro

### Especificación objetivo:
- Tamaño: 1-3B parámetros (corre en CPU/4GB RAM)
- Especialización: routing de tareas, clasificación de intents
- Entrenamiento: fine-tuning sobre historial de decisiones de BAGO
- Licencia: Apache 2.0 (open source)

### `BAGO install BAGO_H.1`
```
1. Descarga weights desde huggingface.co/BAGO/BAGO_H.1
2. Convierte a GGUF (cuantización 4-bit)
3. Registra en model_providers.json
4. Establece como default para clasificación local
```

## Jerarquía Visual

```
                    ┌─────────────────────┐
                    │   USUARIO           │
                    │   (prompt, tarea)   │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌─────────┐    ┌──────────┐    ┌──────────┐
        │PENDRIVE │    │ PC FULL  │    │  CLOUD   │
        │.bago    │◄──►│ .bago    │    │  API     │
        │PORTABLE │    │ INSTALLED│    │          │
        └────┬────┘    └────┬─────┘    └────┬─────┘
             │              │               │
             └──────────────┼───────────────┘
                            │
                    ┌───────▼────────┐
                    │ BAGO_locate.py  │
                    │ Fuente Verdad:  │
                    │ C:\... (PC)     │
                    └───────┬────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
        ┌─────────┐ ┌─────────┐ ┌─────────┐
        │Router   │ │Agentes  │ │Modelos  │
        │Dinámico │ │BAGO     │ │(local/ │
        │         │ │         │ │ cloud)  │
        └────┬────┘ └────┬────┘ └────┬────┘
             │           │           │
             └───────────┼───────────┘
                         │
              ┌──────────▼──────────┐
              │     SALIDA          │
              │  archivos + docs    │
              │  + partituras       │
              │  + aprendizaje      │
              │  + continuidad      │
              └─────────────────────┘
```

## Fecha
2026-05-14 — Arquitectura v1.0
