# Contratos operativos de BAGO v4

Estos contratos describen el comportamiento que el repositorio debe poder demostrar, no solo la intención del proyecto.

## Contratos

- `bago_v4_runtime_contract.json` — estructura mínima del runtime, persistencia y comandos de validación.
- `bago_v4_repl_contract.md` — contrato de la superficie REPL y de los resultados de comandos.
- `bago_v4_evidence_contract.md` — formato y objetivos demostrables de la evidencia.
- `bago_v4_knowledge_contract.md` — reglas para conocimiento recuperable y contribución reutilizable.
- `bago_v4_governance_contract.md` — **modos [B][A][G][O], preflight, culpa, gobernanza, SAC, invalidez canónica.** ← principios de v3.x formalizados para v4.
- `bago_v4_engineering_contract.md` — **invariantes de implementación: escrituras atómicas, sandbox de tests, freno de tokens, contrato de herramientas, detección de huérfanos, sinceridad de docs, control de release.** ← principios de código v3.x no documentados en contratos anteriores.
- `bago_v4_surfaces_contract.md` — separación obligatoria entre conversación, administración y autoridad del backend.
- `cpp_local_runtime_protocol.md` — contrato inicial del backend híbrido `cpp-local`.

## Validación mínima

```powershell
python test_e2e.py
python -m unittest discover -s tests -p test_surface_contract.py
python bago_core\cli.py evidence --test
python bago_core\cli.py evidence --mode simulated --objective community-knowledge --output docs\evidence\example_bundle --overwrite
```
