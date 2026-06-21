# BAGO v4.6.2 - Notas de Release

**Fecha de release:** 2026-06-17

## Resumen

BAGO v4.6.2 consolida el manager en servicios separados, endurece el flujo de instalación y deja la línea de publicación preparada para crecer sin seguir inflando `main.cjs`.

## Cambios principales

- `electron/main.cjs` queda como bootstrap y wiring, con IPC, ventana y entorno movidos a servicios propios.
- El manager expone mejor las dependencias de arranque y el onboarding de providers desde el inicio.
- El catálogo de releases y el instalador siguen bloqueando versiones futuras.
- La versión canónica y la documentación de producto avanzan a 4.6.2.

## Artefactos

| Artefacto | SHA256 |
|---|---|
| BAGO-Installation-Manager-4.6.2-win-x64.exe | 97b0b2ab880741e4e8cd27356f4e1176e51e6fd37b4bbaa0dc52f8d7f6bf0df7 |
| bago-v4.6.2.zip | eae27daebc1f8143032535eec3bd86be1633a13a33884ced0307b270d3b46d49 |

## Pendiente

- Firma Authenticode del EXE, si el canal público la exige.
