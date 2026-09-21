# BAGO Sync Agent

`bago-sync-agent` mantiene una rama y su PR trazables sin convertir GitHub en
una autoridad implícita. La definición conversacional vive en
`.github/agents/bago-sync-agent.agent.md`; el ejecutor acotado vive en
`scripts/bago_sync_agent.py`.

## Flujo

```text
plan -> fetch -> validadores read-only -> commit acotado -> push
     -> binding del PR -> merge -> comprobación remota -> receipt
```

El modo de planificación no muta historial ni worktree. El modo de ejecución
requiere acciones explícitas y sólo admite un máximo de tres validadores.

## Uso

Planificación segura:

```powershell
python scripts/bago_sync_agent.py plan --fetch --json
```

Commit y push de paths autorizados:

```powershell
python scripts/bago_sync_agent.py execute `
  --path backend/bago_core/example.py `
  --message "fix: ejemplo gobernado" `
  --validator tests="python -m pytest backend/tests/test_example.py -q" `
  --commit --push --json
```

Promoción a través de un PR ya abierto:

```powershell
python scripts/bago_sync_agent.py execute `
  --path backend/bago_core/example.py `
  --message "fix: ejemplo gobernado" `
  --validator tests="python -m pytest backend/tests/test_example.py -q" `
  --validator contracts="python scripts/check_contracts.py" `
  --commit --push --merge-pr 123 --json
```

Para un cambio sensible se puede añadir un tercer validador, por ejemplo
`security="python scripts/security_check.py"`. Los validadores se ejecutan en
paralelo, sin shell, y el flujo se detiene si alguno falla o modifica HEAD o
el worktree.

## Guardas

- El worktree sucio exige `--path`; cambios ajenos sólo se conservan con
  `--preserve-unrelated-dirty`.
- Cambios `ahead` y `behind` a la vez producen `BLOCKED/CONFLICT`; no hay
  rebase o resolución automática.
- El push directo a `main` está bloqueado salvo `--allow-main-push`.
- `--skip-validation` es explícito y queda registrado como `SKIPPED`.
- Merge sólo acepta el PR indicado y comprueba base, head, draft y estado antes
  de llamar a `gh pr merge`.
- No hay force-push, reset destructivo, borrado de ramas ni credenciales en
  receipts.

Los receipts se escriben en `.bago/evidence/sync-agent/`, que es estado local
ignorado por Git. El agente comunica `PREPARED`, `EXECUTED`, `BLOCKED`,
`CONFLICT` o `FAILED`; nunca declara `VALIDATED` por sí solo.
