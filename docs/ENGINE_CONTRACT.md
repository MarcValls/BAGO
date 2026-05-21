# BAGO Engine Contract

> Objetivo: mantener el motor de BAGO limpio, reproducible y reconstruible
> durante el desarrollo.

## Roles

- `C:\Users\AMTEC_Terminal_1º\BAGO` o el repo fuente equivalente es el
  workspace de desarrollo.
- `C:\Program Files\BAGO` es el engine instalado y limpio.
- `C:\ProgramData\BAGO\user` es el estado mutable.
- `C:\Program Files\BAGO\.bago\knowledge` es la memoria sincronizable cuando el
  perfil de publicación la incluye.

## Regla

El motor no se edita a mano. Se reconstruye desde el workspace mediante el
instalador limpio y luego se valida.

## Comando canónico

```powershell
bago dev refresh-engine
```

Variantes:

```powershell
bago dev refresh-engine --with-knowledge
bago dev refresh-engine --without-knowledge
```

## Comportamiento

- Reinstala el engine limpio desde `install.ps1`.
- Mantiene el perfil publicado salvo override explícito.
- Valida el engine instalado al final.
- Si el engine se puede borrar y reconstruir sin perder datos, el contrato está
  cumpliéndose.

## Lo que no debe pasar

- Editar archivos del engine a mano como flujo normal de desarrollo.
- Mezclar código de desarrollo con `C:\Program Files\BAGO`.
- Usar el engine como workspace mutable.

## Relación con otros contratos

- `docs/RUNTIME_CONTRACT.md` define qué entra en una instalación limpia.
- `docs/PUBLISH_CONTRACT.md` define los perfiles con y sin knowledge.
- `docs/runtime_contract.json` es la política que consume el instalador.

