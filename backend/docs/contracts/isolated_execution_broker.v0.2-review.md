# ISOLATED_EXECUTION_BROKER v0.2 — evidencia y revisión

Fecha: 2026-10-01. Alcance: fase de decisiones técnicas pedida por el usuario.
No certifica aislamiento implementado, candidate release ni canon.

## Artefactos y acciones

- Especificación: `isolated_execution_broker.v0.2-decisions.md`.
- Probe nativo ejecutado:
  `python artifacts/ieb-decisions-20261001/probe_windows_commit_identity.py`.
- Resultado completo final: exit 0; seis casos de rename en scratch recién
  creado, sin mutar targets de producto.
- Reporte:
  `artifacts/ieb-decisions-20261001/run-d73c49e77ac64515ae4fc210c503f071/observations.json`.
- Plataforma de ese run: Windows 10 build 19045; Python 3.14.5.
- No creación LPAC, CredUI, firma, activación, build ni edición de runtime.

## Identidad y límites de candidato

Rama `fix/spbe-runtime-fix1-20260927`, HEAD
`b10178bf8a13d0035079e989e46c36760dbd2a46`, worktree dirty.
Los documentos son untracked: lectura y hashes fijan la identidad documental.
No atribuirles cobertura de `git diff --check` ni un fingerprint global nuevo.
Sin afirmación remota; se conservaron los cambios anteriores de bootstrap.

| Artefacto / fuente | SHA-256 |
| --- | --- |
| v0.2 final sometido a relectura | `869fff252006dfd15e1c1f36b8ca28d955cfa14ddc203d778b50278977218268` |
| Probe final | `b20e9fa52cfe8cae5d755ae116481f771d0cd2fa7f5c3bdaad80cb53cbc26dac` |
| Observations final | `b0fa96dc2a06fe8e2b4dcc8f90dc1c87f5d8759bf701ff830c8e50b399242402` |
| v0.1 antecedente | `6590dcdbfcfebe7b3d1899f8790830b5094427cb1cfd06192374d000091dcaa6` |
| CRIT v0.1 | `b6932bd312b5e85f624c348643c16795809fb87848143385242af3498a958531` |
| authorization_boundary.py | `5b84b17e3156643d2e57be12439331583a80cca9cf627f15627ea474398d0537` |
| execution_gateway.py | `a2c22e0996eb1440c8a315c003aa45d070759b3df476924f9dc4f19a2908dba7` |
| native_approval.py | `d69351251f90e3dfa946db70bc535e91e118d0bb22f8a0f1ed9e44988d838fa4` |
| execution_request.py | `9fc2c35ff802b1a7e041c66f7f3aba57bb8b17aa08ffca2e77a11daf3adb8ca3` |
| execution_adapters/filesystem.py | `53111f4649a58fdae1ceb078c0215bd15be8cc0d25c70a1f544f9b3c9bc1713a` |
| execution_adapters/process.py | `6b116b5edd57a6b140c22726e21f24759dcd20b863027a16de6608b22e1cb20b` |
| filesystem_effects.py | `5ba723ed8b47c8bc4ee1bf695ad51b01990f71252b62a2360dbf96402834bfdd` |
| bago.effect-registry.v1.json | `ab1edad052f705ae01092b120858c876ce1ec760e88875beb89b37d55fd61f30` |

## Primera revisión independiente

Revisor read-only: `ieb_draft_review`, rol `bago_final_verifier` mediante
`.agents/skills/bago-final-verifier/SKILL.md`.
Documento inicial revisado hash
`fc0ef647b3cd69aa35f74f1680f14e464acc0efb45e7a437bfc716ffda80161a`.
Dictamen inicial: **FAIL de especificación, evidencia experimental válida y
cierre parcial del paso**. No se borra ese resultado al corregir el documento.

El revisor confirmó que seis casos concuerdan con el probe y que la conclusión
D-FS es acotada: no expected-target-FileId en la llamada ensayada. No es prueba
de imposibilidad universal, carrera multiproceso o aislamiento.

### F1 — recuperación durable tras crash

- Regla: commit_started/UNKNOWN y prohibición de replay deben sobrevivir crash.
- Observación: el documento inicial mantenía autoridad en memoria sin definir
  journal durable para distinguir admisión previa de operación nueva.
- Violación/impacto: epoch invalida tokens antiguos pero no impide nuevo Permit
  equivalente; riesgo de duplicar efectos o de no poder reconciliar.
- Corrección aplicada a la especificación: sección 4.1, journal transaccional
  interno al mismo Boundary, admisión antes del efecto, UNKNOWN/fences por
  semántica y recurso, bloqueo también en emisión, consulta y reconciliación.
- Verificación futura: crash antes/después de admisión, efecto y receipt;
  restart y nueva emisión equivalente deben bloquear hasta reconciliar.

### F2 — PREPARE parcial sin máquina de recuperación

- Regla: fallo parcial quema admisión, bloquea RUN y permite cleanup por owner.
- Observación: documento inicial no fijaba transiciones/errors/receipts para
  scratch, perfil, proceso suspendido, Job e inspección.
- Violación/impacto: recursos huérfanos, PREPARE parcial reutilizado o cleanup
  duplicado/incorrecto.
- Corrección aplicada a la especificación: sección 5.1, estados y códigos por
  fase, RESOURCE_INTENT/CREATED durable, invalidación y cleanup idempotente,
  receipt de pendientes. JOB_LIST en creación elegido para evitar la ventana
  del fallback CreateProcess seguido de AssignJob; exige prueba nativa.
- Verificación futura: fault injection por fase y caída del broker; RUN siempre
  deniega contextos parciales y recursos inciertos mantienen fence.

## Comprobaciones y estado

Hashes del código de producto revalidados: 8/8 coinciden con los inspeccionados;
HEAD no cambió. `git diff --check` sobre tracked: exit 0; no verifica nuevos docs.
La lectura de hashes/observations no vuelve a ejecutar el experimento.

El paso sigue parcialmente cerrado: perfil LPAC/Job especificado, API Boundary
y ceremonias elegidas; receta FS insuficiente descartada con evidencia real.
D-FS, verificador/proveedor CredUI y gates Windows permanecen abiertos.
Diseño **PROPOSED**, artefactos **PREPARED**, experimento **EXECUTED**.

## Relectura independiente final

Dictamen recibido: **PASS documental** sobre hash final
`869fff252006dfd15e1c1f36b8ca28d955cfa14ddc203d778b50278977218268`.
El revisor cerró F1 y F2 **en especificación**, sin nuevas contradicciones
materiales. Confirmó coherencia de JOB_LIST en creación suspendida, comprobación
antes de resume y DENY ante atributo/nesting/pertenencia inválidos.

Conclusión del revisor: journal del mismo Boundary sin emisión, fences entre
sesiones/epochs/IDs/roots y recuperación UNKNOWN cierran el hueco de crash en
el diseño; estados, registros anticipados, cleanup idempotente y receipts de
PREPARE cierran el hueco de fallos parciales en el diseño. No son cambios de
runtime ejecutados ni pruebas de esas propiedades en el producto.

OPEN confirmado: D-FS/CAS, proveedor CredUI/SID/rendering, protección real del
journal/guard OS/WAL, LPAC/Job/nesting/herencia/IPC y todos los criterios IEB-01..12.
El paso permanece **PARCIAL** respecto de cerrar todas las decisiones con una
primitiva mutante elegible. Este PASS no certifica implementación, aislamiento,
canon, VERIFIED ni VALIDATED.

Comprobación final del autor: identidad de contrato/probe/observations PASS
3/3, checks directos de whitespace y fences PASS 2/2 sobre documentos nuevos.
El receipt de revisión transcribe el dictamen; no atribuirle revisión
independiente adicional sobre sus propios bytes.
