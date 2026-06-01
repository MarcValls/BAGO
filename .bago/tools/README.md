# BAGO 4.1.5 — Herramientas portadas (`.bago/tools/`)

Utilidades **standalone** recuperadas de BAGO 3.x y adaptadas a 4.1.5.
Son scripts ejecutables directamente (no están cableados al `ToolRegistry`
del runtime, por lo que no afectan a los contratos del chat).

## Disponibles

### `bago_security_audit.py` — Auditoría forense de seguridad
Escanea el repo (o una ruta) buscando tokens/credenciales expuestos y revisa
configuración de git y ficheros de secretos.

```bash
python .bago/tools/bago_security_audit.py                 # escanea el repo
python .bago/tools/bago_security_audit.py --home          # también el HOME
python .bago/tools/bago_security_audit.py --output report.json
```

Adaptaciones respecto a la versión 3.x:
- Raíz parametrizable (`--root`), por defecto la raíz del repo (antes escaneaba
  todo el HOME y `E:/bago_fw` hardcodeado).
- Sin identidades git hardcodeadas (la 3.x reescribía nombre/email del usuario).
- Salida ASCII-safe (sin emojis) para consolas Windows.
- Filtros anti falso-positivo: descarta placeholders de documentación y solo
  marca como "secreto rastreado por git" ficheros de datos (`.json`/`.env`/…),
  no código fuente (p. ej. `credential_manager.py`).

Verificado: 100/100 contra el repo limpio; detecta tokens plantados (test positivo).

## Roadmap (piezas 3.x pendientes de portar — ver `plan.md`)
El resto de las ~546 herramientas 3.x están preservadas en
`~/.bago/legacy-pieces/bago_true-3.x/.bago/tools/`. Muchas dependen del
ecosistema 3.x (`bago_utils`, `tool_registry`, `bago.ollama_runtime`,
`harmony_gate`, `numpy`, `rich`) y requieren portado individual.
