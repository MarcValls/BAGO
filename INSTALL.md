# Guía de instalación · BAGO v3.1

> Tiempo estimado: **5 minutos**. Dependencia base: Python 3.9+.

---

## Requisitos

| Requisito | Versión mínima | Comprobación |
|---|---|---|
| Python | 3.9 | `python3 --version` |
| Git | 2.30 | `git --version` |
| Terminal con UTF-8 | cualquiera | — |
| Truecolor (opcional) | iTerm2, Windows Terminal | Para el gradiente del logo |

BAGO usa **solo la librería estándar de Python** en runtime.
La forma recomendada de instalación para desarrollo es:

```bash
pip install -e .
```

Cuando haya releases publicados, también se podrá usar:

```bash
pip install bago
```

---

## 1. Clonar el repositorio

```bash
git clone https://github.com/MarcValls/bago-framework.git
cd bago-framework
```

---

## 2. Verificar la instalación

```bash
python3 bago validate
```

Salida esperada en instalación limpia:
```
GO manifest
GO state
GO pack
```

Si ves `KO` en alguna línea, ejecuta `python3 bago doctor` para diagnóstico automático.

---

## 3. Ver el estado inicial

```bash
python3 bago health
```

En instalación nueva verás `initializing ⚪` — **es correcto**. El health score sube con el uso real del sistema.

---

## 4. Instalar el alias `bago` (recomendado)

### macOS / Linux

```bash
echo 'alias bago="python3 /ruta/completa/a/bago-framework/bago"' >> ~/.zshrc
source ~/.zshrc
```

O usa el Makefile incluido:

```bash
make install
```

Tras instalar el alias puedes escribir `bago health` directamente.

### Windows (PowerShell)

```powershell
# En tu perfil de PowerShell ($PROFILE):
function bago { python3 C:\ruta\a\bago-framework\bago @args }
```

---

## 5. Activar el hook de pre-push (recomendado)

El hook mantiene el README siempre actualizado y bloquea pushes con estado inválido:

```bash
cp .bago/tools/pre_push_guard.py .git/hooks/pre-push
# o bien:
python3 bago setup
```

---

## 6. Primer uso

```bash
# Ver el banner y estado del sistema
bago banner

# Ver ideas priorizadas para empezar a trabajar
bago ideas

# Abrir una sesión con tu agente de IA
# → Pasa .bago/AGENT_START.md como contexto al agente
```

---

## 7. Integración con agentes de IA

Añade `AGENTS.md` en la raíz de tu repo para que GitHub Copilot, Claude o GPT
arranquen BAGO automáticamente:

```markdown
Lee .bago/AGENT_START.md antes de hacer nada.
```

Un `AGENTS.md` de ejemplo está incluido en este repositorio.

---

## 8. Comandos de verificación post-instalación

```bash
bago validate     # integridad del sistema (debe ser GO)
bago health       # score de salud (0–100)
bago audit        # auditoría completa
bago help         # lista los 83 comandos disponibles
```

---

## Estructura del repositorio

```
bago-framework/
├── bago                    ← Launcher principal (punto de entrada)
├── .bago/
│   ├── core/               ← Motores: dispatcher, context, autonomy, learner
│   ├── tools/              ← 83 herramientas CLI registradas
│   ├── state/              ← Estado persistente (global_state.json, etc.)
│   ├── knowledge/          ← Base de conocimiento auto-generada
│   ├── roles/              ← 14 roles + manifest.json
│   ├── docs/               ← Documentación interna del framework
│   └── pack.json           ← Manifiesto central del sistema
├── README.md
├── QUICKSTART.md           ← Manual de usuario detallado
├── CONTRIBUTING.md
└── CHANGELOG.md
```

---

## Solución de problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `bago validate` → `KO pack` | pack.json corrupto | `python3 bago doctor` |
| Logo sin colores | Terminal sin truecolor | Usa iTerm2 / Windows Terminal; o `bago banner --plain` |
| `bago autonomous` → `lock exists` | Loop ya en ejecución | `rm .bago/state/autonomous.lock` |
| `bago health` → `initializing` | Sin historial aún | Normal en instalación nueva — usar el sistema lo resuelve |
| Hook de pre-push bloqueando | Estado inválido | Corrige con `bago doctor`, luego empuja |

---

*BAGO v3.1 · Autonomy release · Mayo 2026*
*83 comandos CLI · 14 roles · 17 workflows · 100/100 health*
