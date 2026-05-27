# 🚀 INICIO RÁPIDO BAGO PORTABLE

BAGO ahora es **completamente portable**. Puedes arrancarlo desde cualquier letra de unidad (Windows) o punto de montaje (Mac/Linux).

---

## 🖥️ Windows (otro PC, usuario nuevo)

1. Inserta el pendrive
2. Abre **PowerShell** o **CMD**
3. Navega al pendrive (la letra puede ser E:, F:, G:, etc.)

```powershell
F:
cd F:\bago_fw
```

4. **Inicia BAGO:**

```powershell
.\bago.cmd status
```

Si por algún motivo ve errores de ruta (muy raro), ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\make-portable.ps1
```

5. **Entra al chat:**

```powershell
.\bago.cmd launch
```

**Resultado esperado:**
```
Fuente de verdad: F:\bago_fw\.bago (INSTALADO)
  BAGO Framework v2026.05
  Balanceado · Adaptativo · Generativo · Organizativo
```

---

## 🍎 macOS (otro Mac, usuario nuevo)

1. Inserta el pendrive
2. Abre **Terminal** (Cmd + Espacio → "Terminal")
3. Navega al pendrive:

```bash
cd /Volumes/BAGO_USB/bago_fw
```

4. (Primera vez) Da permisos de ejecución:

```bash
chmod +x bago.sh
```

5. **Inicia BAGO:**

```bash
./bago.sh status
```

6. **Entra al chat:**

```bash
./bago.sh launch
```

**Resultado esperado:**
```
Fuente de verdad: /Volumes/BAGO_USB/bago_fw/.bago (PENDRIVE)
  BAGO Framework v2026.05
  Balanceado · Adaptativo · Generativo · Organizativo
```

### Requisitos en Mac
- **Python 3** (viene preinstalado en macOS)
- **Git** (viene preinstalado en macOS)
- **rsync** (viene preinstalado en macOS)
- **Ollama** (si quieres modelos locales; instálalo desde ollama.com)
- Credenciales para Copilot/Codex/Claude en tu entorno (`~/.env` o variables de entorno)

---

## 🐧 Linux

Igual que macOS. El pendrive se montará probablemente en `/media/$USER/BAGO_USB` o `/mnt`.

```bash
cd /media/tu-usuario/BAGO_USB/bago_fw
chmod +x bago.sh
./bago.sh status
```

---

## 📁 Archivos clave del sistema portable

| Archivo | Propósito |
|---------|-----------|
| `bago.cmd` | Launcher Windows (wrapper de bago.ps1) |
| `bago.ps1` | Launcher PowerShell principal |
| `bago.sh` | Launcher macOS/Linux |
| `make-portable.ps1` | Reescribe rutas si cambia la letra de unidad |
| `runtime_contract.json` | Contrato de instalación con rutas dinámicas |
| `.bago/` | Directorio runtime (tools, workflows, estado) |

---

## 🆘 Si algo falla

1. Ejecuta `make-portable.ps1` (Windows) o verifica que estás en la carpeta correcta (Mac)
2. Revisa que `.bago/` existe al lado de `bago.cmd` / `bago.sh`
3. Consulta `AGENTS.md` para instrucciones del agente BAGO
