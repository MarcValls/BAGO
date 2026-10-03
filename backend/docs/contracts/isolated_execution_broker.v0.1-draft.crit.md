# CRIT — ISOLATED_EXECUTION_BROKER_CONTRACT v0.1-DRAFT

Fecha: 2026-10-01. Alcance: contrato documental y confrontación con fuentes
locales; no certificación del runtime. Contrato:
`isolated_execution_broker.v0.1-draft.md`.

## Identidad de la revisión

Rama local `fix/spbe-runtime-fix1-20260927`, HEAD
`b10178bf8a13d0035079e989e46c36760dbd2a46`, worktree sucio.
Documento nuevo sin commit: la identidad revisada se fija por SHA-256, no por
HEAD. No hay afirmación sobre GitHub, canon adoptado o candidato de release.

| Artefacto | SHA-256 |
| --- | --- |
| Draft revisado | `6590dcdbfcfebe7b3d1899f8790830b5094427cb1cfd06192374d000091dcaa6` |
| Adjunto de entrada | `ba0688e47a337c2a392389d068a76b686f7ea15f04e1cd3d44544ab3002dd0ee` |
| `authorization_boundary.py` | `5b84b17e3156643d2e57be12439331583a80cca9cf627f15627ea474398d0537` |
| `execution_gateway.py` | `a2c22e0996eb1440c8a315c003aa45d070759b3df476924f9dc4f19a2908dba7` |
| `native_approval.py` | `d69351251f90e3dfa946db70bc535e91e118d0bb22f8a0f1ed9e44988d838fa4` |

## CRIT independiente

Revisor: subagente `ieb_draft_review`, rol `bago_final_verifier`, read-only,
aplicando `.agents/skills/bago-final-verifier/SKILL.md`. El autor del documento
transcribe la revisión; no la presenta como certificación propia.

Dictamen final recibido: **PASS — alcance estrictamente documental**. El
revisor no encontró requisitos materiales omitidos ni contradicciones que
impidan aprobar el borrador. Sin hallazgos bloqueantes en los cuatro ejes.
Conserva Boundary como único emisor/claim/revocación y Gateway como único
despacho; bloquea COMMIT por ruta, replay/retry y mutación sin evidencia.
Reconoce los límites actuales de MessageBoxW, RLock y proyección JSON.
Este PASS no certifica aislamiento, implementación, canon, VERIFIED ni VALIDATED.

| Eje | Regla y evidencia documental | Límite de la conclusión |
| --- | --- | --- |
| Escape | Secciones 3–5 y 9: AppContainer efectivo, Job sin breakaway, handles mínimos, sin red directa, IPC tipado, hijos brokerizados | No prueba contención Windows; IEB-01/02/03/09 abiertos |
| TOCTOU | Secciones 5–8: identidad de objeto/padre/contenido, primitiva FS por demostrar, output sellado, gate final, nueva ronda para bytes desconocidos | No prueba CAS ni atomicidad; IEB-04/06/07/08 abiertos |
| Replay | Secciones 6–8: claim único Boundary, IN_FLIGHT, admisión final única, epoch de restart, resultado UNKNOWN sin retry automático | RLock actual no es CAS entre procesos; IEB-05/10 abiertos |
| Duplicación de autoridad | Secciones 1/4/6/7/9: Boundary emite y reclama, Gateway resuelve owner, preparación exige autoridad, política derivada | No crea modos nuevos ni canon; integración IEB-11/12 abierta |

En los cuatro ejes, el revisor indicó: violación documental ninguna y
corrección del draft no requerida. Impacto residual y método de verificación
se conservan en la tabla y criterios IEB referenciados. La aprobación es del
draft como producto documental, no de una implementación.

### CRIT-DOC-OBS-01 — cobertura del diff (no bloqueante)

- Regla: evidencia ligada a los bytes revisados.
- Observación: draft untracked; `git diff --check` no lo inspecciona.
- Violación potencial: usar ese PASS como prueba del documento sería incorrecto.
- Impacto: impide atribuirle evidencia de un candidato Git final; no impide
  revisión documental por lectura y SHA-256.
- Evidencia: estado Git untracked, lectura directa y hash final por revisor;
  comprobación específica sin whitespace final.
- Corrección: en la futura preparación del candidato, incluir draft y CRIT
  en el conjunto versionado y fijar hashes de nuevo.
- Verificación: estado Git, hashes y check sobre el candidato con ambos documentos.

## Correspondencia con la entrada

| Requisito del adjunto | Cobertura en el draft |
| --- | --- |
| 1. AppContainer + Job | Sección 4 y IEB-01/02 |
| 2. Recursos por identidad retenida | Sección 5 y IEB-06 |
| 3. Herencia explícita | Sección 4 y IEB-03; precisión TRUE para HANDLE_LIST |
| 4. Red brokerizada | Sección 9 y IEB-09 |
| 5. Preparar, autorizar y ejecutar | Secciones 1/4/6/7 y IEB-04 |
| 6. ExecutionContextAttestation | Sección 6, campos y registro privado |
| 7. Single-use + CAS | Sección 7; transición propuesta y autoridad única |
| 8. STATE_DRIFT | Secciones 6/8 y IEB-07 |
| 9. Staging y COMMIT | Secciones 7/8 y IEB-08 |
| 10. Efectos externos peligrosos | Sección 9; owner/preconditions específicos |
| 11. Subprocesos | Sección 4 y IEB-02 |
| 12. Consentimiento aislado y fallback | Sección 4; DEGRADED no elegible para mutaciones |
| Cuatro invariantes y Boundary único | Secciones 1/3 |
| DRAFT + CRIT, estado PROPOSED | Este par documental, con límites explícitos |

Precisiones necesarias respecto de la propuesta: un handle no vuelve seguro
un reemplazo posterior por pathname; no se puede consumir al arrancar y tratar
el mismo token como una admisión nueva al commit; la salida desconocida requiere
consentimiento sobre resultado final; preparación sandbox también materializa
efectos y necesita autoridad. Esas precisiones preservan el objetivo de una sola
autoridad y una ventana final acotada.

## Comprobaciones ejecutadas

- Lectura del adjunto, contrato y fuentes locales indicadas.
- Consulta de las fuentes Microsoft enlazadas en el draft.
- Comprobación directa del draft: trailing whitespace 0, fences 8/balanceados.
- Presencia documental de 9 marcadores requeridos: 9/9; esto solo prueba presencia.
- Referencias de código: 3/3 existen; hashes revalidados sin drift.
- `git diff --check`: exit 0 sobre cambios tracked; no cubre archivos untracked.
- Búsqueda de símbolos de broker/attestation en fuentes Python/C#/TS/JS de
  backend/bootstrap/frontend/Electron, incluyendo ocultos: sin coincidencias.
  Alcance limitado a esos nombres y árboles, no prueba ausencia global.
- Tests, build, live sandbox, CredUI y gates de runtime: **NOT_RUN** porque
  solo se han producido documentos y no hay implementación bajo revisión.

## Condiciones abiertas

Antes de implementación mutante deben resolverse primitiva FS/CAS, perfil
Windows, integración de la máquina Permit y consentimiento sobre resultado
final, además de autoridad de preparación y recuperación tras crash. Los
criterios IEB-01..12 requieren evidencia futura del candidato implementado.
La CRIT de este documento no cierra bootstrap P0 ni la partición global de sinks.

Estado del diseño **PROPOSED**; contrato y CRIT **PREPARED**. No se promueven
el estado global del repositorio ni las decisiones canónicas.
