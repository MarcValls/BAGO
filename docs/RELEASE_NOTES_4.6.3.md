# BAGO v4.6.3 - Notas de Release

**Fecha de publicación:** 2026-06-18

## Resumen

BAGO v4.6.3 publica la línea de release actual con el manager alineado y los bundles de usuario y auditoría separados.
El ZIP oficial fue regenerado tras cerrar el lockfile npm y las vulnerabilidades de `form-data` y `undici`.
Los hashes finales se publican como sidecars externos para evitar autorreferencias circulares dentro de los paquetes.

## Cambios principales

- La versión canónica permanece en 4.6.3 en el árbol de producto.
- El manager y sus metadatos visibles quedan alineados con la nueva línea.
- El runtime, el supervisor, el orquestador y las sesiones nuevas declaran 4.6.3.
- El supervisor y los jobs Windows evitan abrir ventanas PowerShell no solicitadas.
- El verifier de release está activo para 4.6.3.
- La documentación de usuario y la política pública quedan sincronizadas con la release publicada.
- Se separan dos paquetes:
  - bundle de usuario: `bago-user-v4.6.3.zip`
  - bundle de auditoría: `bago-audit-v4.6.3.zip`

## Artefactos publicados

| Artefacto | Integridad |
|---|---|
| BAGO-Installation-Manager-4.6.3-win-x64.exe | `BAGO-Installation-Manager-4.6.3-win-x64.exe.sha256` y `latest.yml` |
| bago-v4.6.3.zip | `bago-v4.6.3.zip.sha256`, `bago-v4.6.3.zip.manifest.json` y `bago-v4.6.3.zip.report.md` |
| bago-user-v4.6.3.zip | `bago-user-v4.6.3.zip.sha256`, `bago-user-v4.6.3.zip.manifest.json` y `bago-user-v4.6.3.zip.report.md` |
| bago-audit-v4.6.3.zip | `.sha256`, `.manifest.json`, `.snapshot.json` y `.report.md` externos |
| bago-release-assets-v4.6.3.zip | `.sha256` y `.manifest.json` externos |

## Estado

- Release publicada con checksums y manifiestos.
- Bundle de usuario publicado.
- Bundle de auditoría externa publicado.
- Gate real de release validable con `BAGO_RELEASE_ASSETS`.
