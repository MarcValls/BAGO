# tools/sprints/

Scripts históricos de sprints previos de BAGO, agrupados aquí al pasar a v4.8.0
el 2026-06-24. Cada subcarpeta agrupa por prefijo; los nombres se preservan.

| Subdir | Prefijo | Origen |
|---|---|---|
| audit/ | audit_* | scripts de auditoría S0–S11 |
| check/ | check_* | verificaciones puntuales |
| diag_debug/ | diag_*, debug_*, heal_*, simplify_*, modularize_*, regress_*, strip_*, square_*, stub_*, sync_*, trace_*, rewrite_*, show_lines* | diagnosis y fixes one-off |
| dump/ | dump_* | volcados de boot/estado |
| fix/ | fix_* | parches puntuales |
| oneoff_tests/ | test_* (excepto los 8 oficiales) | tests no canónicos |
| patch/ | patch_* | parches de banner/UI |
| promote/ | promote_* | scripts de promoción entre copias |
| restore/ | restore_* | rollback releases (v4.7.2 official) |
| split/ | split_* | divisores de archivos en modularización |

## Tests oficiales (NO en sprints/)

Estos viven en la raíz o en `tests/` y son parte de la release:
- test_e2e.py
- test_security_release.py
- test_command_intents.py
- test_translators.py
- test_issue_take_agent.py
- test_ollama_live_optional.py
- test_browser_actions.py
- test_browser_debug.py

## Cómo volver a dejar todo en raíz (rollback)

```powershell
# Inverso: cada archivo vuelve a su origen Program Files\BAGO\
# (no aplica si esos archivos ya no existen en Program Files)
```

Si querés **borrar** todo esto después de auditarlo, una vez confirmado que
no hay nada útil, ejecutá:

```powershell
Remove-Item -Recurse -Force tools\sprints
```

## Historial

- 2026-06-24 — creado durante pase a v4.8.0, agrupando scripts one-off de
  Program Files\BAGO.