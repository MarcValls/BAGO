# BAGO Kernel Lockdown — Operación activa

**Estado:** COMPLETADO ✅  
**Inicio:** 2026-05-06  
**Completado:** 2026-05-06  
**Target release:** kernel-lockdown  
**Rama:** kernel-lockdown (PRs individuales → main)

---

## Objetivo

Convertir BAGO de "megapack potente pero expansivo" en un **núcleo pequeño, estricto, verificable y difícil de romper**.

La jugada ganadora no es añadir herramientas. Es hacer que las existentes obedezcan una arquitectura limpia.

---

## Regla de oro (no negociable)

```
NO FEATURES.
NO BANNERS.
NO NUEVOS COMANDOS.
NO "YA QUE ESTAMOS".
SOLO NÚCLEO, SEGURIDAD, PACKAGING, TESTS Y CI.
```

---

## Métricas de partida (baseline v3.1)

| Métrica | Antes |
|---------|-------|
| Comandos públicos declarados | 83 |
| Comandos deprecated (legacy) | 29 |
| Comandos activos no-deprecated | 54 |
| Tools Python en .bago/tools/ | 178 |
| Comandos core estables | 0 (sin clasificar) |
| Tests unitarios | 0 |
| Rutas fail-open en preflight | sí |
| Estado runtime en git | parcialmente |
| Pack con dist interno | sí |
| CI gates duros | no |

---

## Métricas objetivo (kernel-lockdown)

| Métrica | Después |
|---------|---------|
| Comandos core declarados | ≤12 |
| Comandos clasificados | 100% |
| Comandos sin `risk` | 0 |
| Comandos core sin preflight | 0 |
| Rutas fail-open | 0 |
| Builds dentro del pack | 0 |
| Estado runtime empaquetado | 0 |
| pytest obligatorio | sí |
| CI gates duros | sí |
| README contractual | sí |

---

## Arquitectura objetivo

```
bago                          # thin wrapper / console entry
.bago/
  core/
    cli.py                    # parser + dispatch limpio
    command_contract.py       # tipos: safe/mutating/dangerous/experimental
    command_runner.py         # ejecución uniforme
    preflight_engine.py       # fail-closed
    paths.py                  # resolución central de rutas
    runtime.py                # estado runtime
  tools/
    tool_registry.py          # única fuente de verdad
    legacy_registry.py        # comandos deprecated (separados)
  state.example/              # plantillas versionadas
  state/                      # runtime local, gitignored
  dist/                       # excluido del pack
tests/
  test_registry.py
  test_preflight.py
  test_launcher.py
  test_packaging.py
  test_runtime_state.py
  test_autonomous_dry_run.py
pyproject.toml
```

---

## Roadmap de PRs

| PR | Nombre | Estado | Commit |
|----|--------|--------|--------|
| PR-01 | kernel-freeze-baseline | ✅ COMPLETADO | commit `c5fa826` |
| PR-02 | registry-single-source-of-truth | ✅ COMPLETADO | commit `6e65f9e` |
| PR-03 | preflight-fail-closed | ✅ COMPLETADO | commit `83a5ac3` |
| PR-04 | command-risk-model | ✅ COMPLETADO | commit `c5c5db4` |
| PR-05 | clean-packaging-no-recursion | ✅ COMPLETADO | commit `37a2ac8` |
| PR-06 | runtime-state-boundary | ✅ COMPLETADO | commit `e3efc4e` |
| PR-07 | proper-python-package | ✅ COMPLETADO | commit `7e03d37` |
| PR-08 | core-test-harness | ✅ COMPLETADO | commit `0b3e8ee` |
| PR-09 | hard-ci-gates | ✅ COMPLETADO | commit `91ef37c` |
| PR-10 | docs-core-truth | ✅ COMPLETADO | commit `d9bd021` |

---

## Checklist de aceptación final

```bash
# 1. instalación limpia
tmpdir=$(mktemp -d)
git clone https://github.com/MarcValls/BAGO "$tmpdir/bago"
cd "$tmpdir/bago"
pip install -e .

# 2. comandos core
bago validate
bago health
bago status

# 3. tests
pytest

# 4. pack
python3 .bago/tools/build_pack.py --clean --out dist/
unzip -l dist/*.zip | grep -v ".bago/dist"
unzip -l dist/*.zip | grep ".bago/state/" && echo "ERROR: state/ in pack" || echo "OK"

# 5. seguridad
bago install        # debe pedir confirmación
bago autonomous --dry-run
bago autonomous --unsafe --dry-run

# 6. CI
git push            # falla si gates críticos fallan
```

---

## Post-lockdown: hallazgos resueltos (kernel-lockdown)

Los siguientes problemas P0 fueron identificados en la reauditoría post-lockdown y resueltos antes de cerrar el tag del lockdown:

| # | Hallazgo | Fix |
|---|---------|-----|
| P0-1 | `validate` listado como legacy Y core simultáneamente | Eliminado `deprecated=True` del registry; añadido a `_CORE_CMDS` |
| P0-2 | `next` en `_CORE_CMDS` pero experimental en README | Eliminado de `_CORE_CMDS`; queda como experimental |
| P0-3 | `KERNEL_LOCKDOWN.md` desactualizado (PR-01 "en progreso") | Actualizado con todos los PR completados + commit SHAs |
| P0-4 | Preflight con ruta fail-open vía fallback a `preflight.py` | Eliminado el fallback; fail-closed para core/dangerous si falta el engine |
| P0-5 | `--dry-run` desbloqueaba comandos dangerous sin implementarlo | Añadido `supports_dry_run: bool` al registry; sólo `auto` y `autonomous` tienen `True` |
| P0-6 | `validate_pack_contents.py` sólo bloqueaba `state/sessions`, no `state/` | `FORBIDDEN_PREFIXES` cambiado a `.bago/state/` completo |
| P0-7 | `autonomous` e `inbox` bypasseaban `_dispatch` (sin preflight/session log) | Eliminadas ramas especiales; fluyen por `_dispatch` normal |
| P0-8 | CI `gate-security` no ejecutaba `bago secrets` | Añadido paso `python3 bago secrets --json` al gate |

---

## Artefactos generados

- `docs/generated/registry_snapshot.json` — instantánea del registry v3.1
- `docs/generated/baseline_health.txt` — health baseline antes de lockdown
- `docs/generated/baseline_audit.txt` — audit baseline antes de lockdown
- `docs/COMMAND_AUDIT.md` — clasificación completa de comandos
