# Auditoría de las 14 pruebas obligatorias — ARQ v0.3 §4

**Fecha:** 2026-07-16
**Origen:** Tarea #2 del PLAN v0.3
**Método:** lectura directa de los tests en `backend/tests/integrations/pi/`

---

## Resumen ejecutivo

| Estado | Conteo | Tests |
| --- | --- | --- |
| ✅ Referenciables (existe test equivalente) | 8 | T1, T2, T3, T4, T5, T6, T7, T8 |
| ⚠️ Cubierto parcialmente — requiere ampliación | 3 | T12 (3 sub-casos sí), T13 (usa `cancel`, falta `SIGKILL`), T15 (cubre receipt, falta log) |
| ❌ Gap real (test nuevo necesario) | 4 | T9, T10, T11, T14 |

**Total tests del ARQ:** 15 (T1-T15; el ARQ §4 lista 14 + T15 bonus "secretos en logs").

**Tests a crear en T13:** 4 nuevos + 2 mejorados (T13, T15) = **6 archivos a tocar** en `test_v03_arq_separation.py`.

---

## Tabla detallada

| # | Test ARQ | Test existente equivalente | Ubicación | Acción |
| --- | --- | --- | --- | --- |
| 1 | `test_read_outside_workspace_scope_root_blocked` | `test_resolve_path_outside` | `test_scope_validator.py:32` | ✅ Referenciar |
| 2 | `test_write_in_phase_1_blocked` | `test_kill_switch_phase_lock_blocks_below_max` | `test_phase1_adversarial.py:85` | ✅ Referenciar |
| 3 | `test_bash_in_phase_1_3_blocked` | `test_filter_env_blocks_pi_prefix` | `test_process_boundary.py:27` | ✅ Referenciar (filter_env bloquea bash) |
| 4 | `test_dotpi_load_blocked` | `test_deny_implicit_pi_sources` | `test_scope_validator.py:98` | ✅ Referenciar |
| 5 | `test_skills_extensions_load_blocked` | `test_filter_env_strips_unallowed` + `test_build_boundary_creates_ephemeral_home` | `test_process_boundary.py:42,49` | ✅ Referenciar |
| 6 | `test_AGENTS_md_load_blocked` | `test_deny_implicit_pi_sources` (cubre `.agents`) | `test_scope_validator.py:98` | ✅ Referenciar; ampliar con literal `AGENTS.md` |
| 7 | `test_provider_drift_blocks_certification` | `test_provider_drift_raises` | `test_phase1_adversarial.py:191` | ✅ Referenciar |
| 8 | `test_credential_outside_bago_rejected` | `test_credential_drift_detected` + `test_run_sidecar_rejects_injected_pi_env` | `test_phase1_adversarial.py:112` + `test_process_boundary.py:147` | ✅ Referenciar (2 tests cubren esto) |
| 9 | `test_tool_call_without_approval_rejected` | (no existe test específico) | — | ❌ **GAP — T9 nuevo** |
| 10 | `test_tool_result_without_receipt_rejected` | (no existe test específico con `ToolReceipt.id` ausente) | — | ❌ **GAP — T10 nuevo** |
| 11 | `test_agent_end_without_context_receipt_rejected` | `test_no_persistent_state_after_chat` (parcial) | `test_phase1_adversarial.py:279` | ❌ **GAP — T11 nuevo** (caso explícito agent_end) |
| 12 | `test_path_escape_blocked` (symlink, junction, UNC) | `test_symlink_escape_denied` + `test_unc_on_non_windows_rejected` + NEG-011/012 en `test_negatives.py:315,334` | `test_scope_validator.py:63,105` + `test_negatives.py` | ✅ Referenciar (3 sub-casos) |
| 13 | `test_sidecar_crash_keeps_session_intact` (SIGKILL real) | `test_runner_cancel_kills_sidecar_process` (usa `cancel`, no `SIGKILL`) | `test_phase3_adversarial.py:392` | ⚠️ **MEJORAR — T13 nuevo con SIGKILL** |
| 14 | `test_cross_session_contamination_zero` | (no existe) | — | ❌ **GAP — T14 nuevo** |
| 15 | `test_secret_does_not_appear_in_logs` | `test_secret_does_not_appear_in_receipt` (cubre receipt, no logs) | `test_phase1_adversarial.py:143` | ⚠️ **MEJORAR — T15 nuevo con assert sobre logs** |

---

## Gaps a crear en T13 (6 tests)

1. **`test_beforeToolCall_without_approval_raises_ToolNotApproved`** — T9: la policy_gate bloquea el tool call sin approval.
2. **`test_execution_done_without_ToolReceipt_id_raises_BridgeError`** — T10: el bridge rechaza cierre sin receipt.
3. **`test_agent_end_without_ContextReceipt_keeps_session_open`** — T11: la sesión BAGO no cierra.
4. **`test_sidecar_SIGKILL_keeps_session_intact`** — T13 ampliado: usa `os.kill(pid, SIGKILL)` en lugar de `cancel()`.
5. **`test_cross_session_contamination_zero`** — T14: 2 ejecuciones consecutivas, asserts sobre memoria compartida.
6. **`test_secret_patterns_not_in_logs`** — T15 ampliado: assert que ningún log contiene `sk-...`, `ghp_...`, `Bearer `, etc.

---

## Tests existentes que se referencian (sin duplicar)

| Test | Cubre ARQ |
| --- | --- |
| `test_resolve_path_outside` | T1 |
| `test_kill_switch_phase_lock_blocks_below_max` | T2 |
| `test_filter_env_blocks_pi_prefix` | T3 |
| `test_deny_implicit_pi_sources` | T4, T6 |
| `test_filter_env_strips_unallowed` | T5 |
| `test_provider_drift_raises` | T7 |
| `test_credential_drift_detected` + `test_run_sidecar_rejects_injected_pi_env` | T8 |
| `test_symlink_escape_denied` + `test_unc_on_non_windows_rejected` + NEG-011/012 | T12 |
| `test_runner_cancel_kills_sidecar_process` | T13 (parcial — base del nuevo test SIGKILL) |
| `test_secret_does_not_appear_in_receipt` | T15 (parcial — base del nuevo test logs) |

---

## Conclusión

- **6 tests nuevos** a crear en `backend/tests/integrations/pi/test_v03_arq_separation.py`.
- **10 tests existentes** se referencian (tabla de mapeo en cabecera del archivo).
- **No se duplica cobertura** ya existente.

**Próximo paso:** T13 del PLAN crea el archivo de consolidación con la tabla de mapeo y los 6 tests nuevos.
