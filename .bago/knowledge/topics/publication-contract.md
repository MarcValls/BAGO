# Publication Contract

## Objetivo

Definir cómo se publica BAGO en dos perfiles sin cambiar el runtime base.

## Perfiles

- `with-knowledge`: instala el runtime y la memoria sincronizable.
- `without-knowledge`: instala el mismo runtime base sin montar `knowledge/`.

## Comandos canónicos

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -NoKnowledge
```

## Contrato

- `install.ps1` es la implementación compartida.
- `runtime_contract.json` define el keep/prune del runtime limpio.
- `publication-contract.md` (este archivo) describe la política de publicación.
- `C:\Program Files\BAGO\runtime_contract.json` registra el perfil aplicado.
- `bago knowledge status` y `bago knowledge sync` mantienen la memoria alineada
  con `MarcValls/bago-knowledge`.

## Regla

El perfil solo decide si `C:\Program Files\BAGO\.bago\knowledge` existe en la
instalación. El resto del runtime debe ser idéntico entre perfiles.
