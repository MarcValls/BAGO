# BAGO v4.6.4 - Notas de Release

**Fecha de publicacion:** 2026-06-20

## Resumen

BAGO v4.6.4 consolida la version activa como fuente de verdad unica y elimina la dependencia de valores fijos en el runtime, el empaquetado y la verificacion de release.

## Cambios principales

- La version se lee desde `release_version.txt` y cae a `versions.json` si falta.
- El manager y el runtime ya no dependen de una version hardcoded para mostrar o resolver la release activa.
- Los empaquetadores fallan si faltan entradas obligatorias del bundle.
- La evidencia historica queda alineada con los manifiestos y checksums reales.
- Se mantienen las notas historicas de 4.6.3 como referencia, pero 4.6.4 pasa a ser la linea activa.

## Artefactos

- `BAGO-Installation-Manager-4.6.4-win-x64.exe`
- `bago-v4.6.4.zip`
- `bago-user-v4.6.4.zip`
- `bago-audit-v4.6.4.zip`

## Estado

- Publicacion coherente con la version activa.
- Drift de version reducido a datos historicos y notas de release antiguas.
