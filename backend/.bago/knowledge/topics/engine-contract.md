# Engine Contract

## Objetivo

Mantener el motor de BAGO limpio durante el desarrollo.

## Regla

El motor instalado es un artefacto regenerable, no el workspace de desarrollo.

## Comando canónico

```powershell
bago dev refresh-engine
```

Variantes:

```powershell
bago dev refresh-engine --with-knowledge
bago dev refresh-engine --without-knowledge
```

## Comportamiento esperado

- reconstruye `C:\Program Files\BAGO` desde `install.ps1`
- conserva el perfil de publicación salvo override explícito
- valida el motor instalado al final
- deja el runtime limpio y reproducible

## Relación con otros contratos

- `runtime_contract.json` define qué entra en la instalación limpia.
- `publication-contract.md` define los perfiles con y sin knowledge.
- `publication-contract` define la misma política en formato knowledge.

