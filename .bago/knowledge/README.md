# BAGO Knowledge

Memoria operativa sincronizable del BAGO local.

Este directorio es la capa de conocimiento que puede reflejarse 1:1 con
`MarcValls/bago-knowledge` usando la misma estructura de archivos.

## Layout canónico

- `manifest.json` como índice y contrato.
- `topics/` como superficie canónica de memoria del framework.
- `examples/` para planes, prompts y casos reproducibles.
- `projects/` para conocimiento de proyectos personales activos:
  - `bianca/` — Juego BIANCA (engine, FX, sprites, audio)
  - `casino/` — Casino Telegram Mini App (slots, TON, RTP)
  - `music/` — Producción musical (Ableton, synths, secuencias)
- `sessions/` para arcs de sesión, historiales e informes mensuales.
- `simulations/` para visualizaciones HTML y referencias interactivas.
- `schemas/` para validación de contratos.
- `assets/` para diagramas ligeros y mapas.

## Regla de trabajo

- `MD` para conocimiento humano.
- `JSON` para contrato e índice.
- `YAML` para planes y ejemplos.
- `SVG` para diagramas.

## Regla de compatibilidad

Todo lo que vaya a sincronizarse con GitHub debe vivir en rutas estables y
canónicas. El contenido legacy puede quedarse como referencia, pero la edición
activa debe apuntar a `topics/`, `examples/`, `projects/`, `sessions/`, `simulations/`, `schemas/` y `assets/`.

## Publicación

El contrato de publicación de BAGO vive como conocimiento operativo en:

- `topics/publication-contract.md`
- `examples/publication_profiles.yml`

La regla es simple: el runtime base no cambia entre perfiles; solo cambia si la
memoria sincronizable `knowledge/` se monta o no en la instalación limpia.

## Motor limpio

El motor instalado debe poder regenerarse sin tocar el workspace de desarrollo:

- `bago dev refresh-engine` reconstruye `C:\Program Files\BAGO`
- el motor se valida al final del refresh
- la fuente de verdad sigue siendo el workspace fuente, no el runtime instalado
