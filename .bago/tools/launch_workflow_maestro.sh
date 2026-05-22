#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKFLOW_FILE="$ROOT_DIR/.bago/workflows/WORKFLOW_MAESTRO_BAGO.md"
INDEX_FILE="$ROOT_DIR/.bago/workflows/WORKFLOWS_INDEX.md"
STATE_FILE="$ROOT_DIR/.bago/state/ESTADO_BAGO_ACTUAL.md"
CANON_FILE="$ROOT_DIR/.bago/docs/BAGO_CANON.md"
REPO_GUARD="$ROOT_DIR/.bago/tools/repo_context_guard.py"

usage() {
  cat <<'EOF'
Usage: launch_workflow_maestro.sh [--tactical W1|W2|W3|W4|W5|W6]

Launches the BAGO master workflow by validating the canonical entry points and
printing the operational route.
EOF
}

selected_tactical=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tactical)
      selected_tactical="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

for path in "$WORKFLOW_FILE" "$INDEX_FILE" "$STATE_FILE" "$CANON_FILE"; do
  if [[ ! -f "$path" ]]; then
    printf 'Missing required BAGO artifact: %s\n' "$path" >&2
    exit 1
  fi
done

repo_guard_status="ok"
if [[ -f "$REPO_GUARD" ]]; then
  if ! python3 "$REPO_GUARD" check >/dev/null 2>&1; then
    repo_guard_status="mismatch"
  fi
fi

printf 'BAGO workflow launcher ready\n'
printf 'Root: %s\n' "$ROOT_DIR"
printf 'Master workflow: %s\n' "$WORKFLOW_FILE"
printf 'Index: %s\n' "$INDEX_FILE"
printf 'State: %s\n' "$STATE_FILE"
printf 'Canon: %s\n' "$CANON_FILE"
printf '\nOperational route:\n'
printf '  canon -> integracion -> entorno -> validacion_escalonada -> baseline -> regresion -> operacion_continua\n'

if [[ "$repo_guard_status" = "mismatch" ]]; then
  printf '\nRepo-context guard:\n'
  printf '  Se detectó cambio de repositorio o contexto.\n'
  printf '  Para evitar bucles con estado heredado, arranca con W1/repo-first antes de otros workflows.\n'
  printf '  Recomendado: make workflow-tactical NAME=W1\n'
  if [[ -n "$selected_tactical" && "$selected_tactical" != "W1" ]]; then
    printf '  Bloqueado: no se permite %s hasta pasar por W1.\n' "$selected_tactical" >&2
    exit 2
  fi
fi

if [[ -n "$selected_tactical" ]]; then
  case "$selected_tactical" in
    W1|W2|W3|W4|W5|W6)
      tactical_path="$(find "$ROOT_DIR/.bago/workflows" -maxdepth 1 -type f -name "${selected_tactical}_*.md" | head -n 1 || true)"
      if [[ -z "$tactical_path" ]]; then
        printf 'Tactical workflow not found: %s\n' "$selected_tactical" >&2
        exit 1
      fi
      printf '\nSelected tactical workflow: %s\n' "$tactical_path"
      cat "$tactical_path"
      ;;
    *)
      printf 'Invalid tactical workflow: %s\n' "$selected_tactical" >&2
      exit 1
      ;;
  esac
else
  printf '\nNext step:\n'
  printf '  Read %s and choose a tactical workflow from %s\n' "$WORKFLOW_FILE" "$INDEX_FILE"
  printf '  Or run %s for ideas, or %s W1 to inspect a workflow for human configuration\n' \
    "$ROOT_DIR/ideas" "$ROOT_DIR/workflow-info"
fi
