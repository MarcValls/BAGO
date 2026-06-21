# BAGO v4.6.1 — Notas de Release

**Fecha de release:** 2026-06-12

## Resumen

BAGO v4.6.1 corrige la línea de distribución y el flujo de entrada del chat. El paquete oficial ya incluye `package-lock.json`, el gate de release valida esa presencia y la CLI acepta bloques pegados como una sola entrada.

## Cambios principales

- ZIP de distribución alineado con la release 4.6.1.
- `package-lock.json` incluido en el bundle oficial.
- `scripts/verify_release_461.py` valida el bundle actual y la cobertura del manifiesto.
- La CLI de chat trata el pegado multilinea como un único mensaje.
- Corrección de compatibilidad de `install-v4.ps1` con Windows PowerShell 5.1.

## Artefactos

| Artefacto | SHA256 |
|---|---|
| BAGO-Installation-Manager-4.6.1-win-x64.exe | f56448f53fc4b4e6f9ba73e8c216d635e75ed3a303b69936363050422e8f1570 |
| bago-v4.6.1.zip | 3264905e274442c47c4753a27ffe4d1b8ad55904c8000f76dab47ebdf0dfda0f |

## Pendiente

- Firma Authenticode del EXE, si el canal público la exige.
