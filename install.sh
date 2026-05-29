#!/usr/bin/env bash
# version=3.5.0b1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${BAGO_TARGET_ROOT:-$HOME/.local/share/bago}"
BIN_DIR="${BAGO_BIN_DIR:-$HOME/.local/bin}"

mkdir -p "$TARGET" "$BIN_DIR"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete \
    --exclude ".git" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".pytest_cache" \
    "$ROOT/" "$TARGET/"
else
  tar -cf - \
    --exclude ".git" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude ".pytest_cache" \
    -C "$ROOT" . | tar -xf - -C "$TARGET"
fi

python3 -m pip install --user -e "$TARGET"

echo
echo "BAGO instalado en $TARGET"
echo "Comando: bago"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo
    echo "Abre una terminal nueva o añade esto a tu shell:"
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
    ;;
esac
