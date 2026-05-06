# BAGO Kernel Lockdown — Operación activa

**Estado:** EN PROGRESO  
**Inicio:** 2026-05-06  
**Target release:** v3.2-kernel  
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

## Métricas objetivo (v3.2-kernel)

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

| PR | Nombre | Estado |
|----|--------|--------|
| PR-01 | kernel-freeze-baseline | ✅ EN PROGRESO |
| PR-02 | registry-single-source-of-truth | ⬜ pendiente |
| PR-03 | preflight-fail-closed | ⬜ pendiente |
| PR-04 | command-risk-model | ⬜ pendiente |
| PR-05 | clean-packaging-no-recursion | ⬜ pendiente |
| PR-06 | runtime-state-boundary | ⬜ pendiente |
| PR-07 | proper-python-package | ⬜ pendiente |
| PR-08 | core-test-harness | ⬜ pendiente |
| PR-09 | hard-ci-gates | ⬜ pendiente |
| PR-10 | docs-core-truth | ⬜ pendiente |

---

## Checklist de aceptación final

```bash
# 1. instalación limpia
tmpdir=$(mktemp -d)
git clone https://github.com/MarcValls/BAGO_v3.1 "$tmpdir/bago"
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
unzip -l dist/*.zip | grep -v ".bago/state/sessions"

# 5. seguridad
bago install        # debe pedir confirmación
bago autonomous --dry-run
bago autonomous --unsafe --dry-run

# 6. CI
git push            # falla si gates críticos fallan
```

---

## Artefactos generados

- `docs/generated/registry_snapshot.json` — instantánea del registry v3.1
- `docs/generated/baseline_health.txt` — health baseline antes de lockdown
- `docs/generated/baseline_audit.txt` — audit baseline antes de lockdown
- `docs/COMMAND_AUDIT.md` — clasificación completa de comandos
