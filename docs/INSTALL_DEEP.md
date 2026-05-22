# BAGO Framework — Instalación avanzada y contratos

Este documento detalla la arquitectura de instalación, los contratos de runtime
y las decisiones de diseño. Para una guía rápida de 3 pasos, ver `../INSTALL.md`.

## Contrato de runtime

El árbol instalado se divide en:

- `C:\Program Files\BAGO\.bago` — runtime framework y estado mutable
- `C:\Program Files\BAGO\.bago\knowledge` — memoria sincronizable (solo perfil with-knowledge)
- `C:\Program Files\BAGO\{bago,bago.ps1,bago.cmd,bago_core,...}` — bootstrap y entrypoints
- `C:\ProgramData\BAGO\user` — estado de usuario (fuera del árbol de instalación)

La frontera keep/prune se define en `docs/RUNTIME_CONTRACT.md`.

## Perfiles de publicación

| Perfil | Incluye knowledge | Uso |
|--------|-------------------|-----|
| with-knowledge | Sí | Desarrollo, sincronización con bago-knowledge |
| without-knowledge | No | Producción, runtime mínimo |

## Desarrollo vs runtime

El motor instalado es **inmutable**. Los cambios de desarrollo van en un workspace
aparte. Ver `docs/ENGINE_CONTRACT.md`.

## Refresco del motor

```powershell
bago dev refresh-engine
```

Reconstruye `C:\Program Files\BAGO` desde el contrato limpio, preservando el perfil.
