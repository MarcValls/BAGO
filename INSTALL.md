# BAGO — Instalación en 3 pasos (Windows)

> **TL;DR:** Copia, pega, ejecuta. Necesitas PowerShell y acceso a internet.

## Paso 1 — Descarga

Descarga o clona este repositorio:

```bash
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
```

O descarga el ZIP desde GitHub y descomprímelo.

## Paso 2 — Instala

Elige **uno** de estos dos perfiles:

### Con conocimiento sincronizado (recomendado)
Mantiene BAGO alineado con la memoria operativa remota.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-with-knowledge.ps1
```

### Solo runtime (mínimo)
Solo el motor, sin sincronización de memoria.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-without-knowledge.ps1
```

Ambos instalan en `C:\Program Files\BAGO` y actualizan tu `PATH`.

## Paso 3 — Verifica

Abre una **nueva** terminal (PowerShell o CMD) y ejecuta:

```powershell
bago validate
```

Si ves:

```
GO manifest
GO state
GO pack
```

La instalación está correcta.

---

## Primeros comandos

```powershell
bago hello       # guía de inicio interactiva
bago status      # estado del sistema
bago --help      # lista completa de comandos
```

## ¿Problemas?

- Si `bago` no se reconoce: cierra y abre la terminal, o ejecuta `refreshenv`
- Si la instalación falla: revisa que tengas permisos de administrador
- Para más detalle: `docs/INSTALL_DEEP.md`
