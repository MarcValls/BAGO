#!/usr/bin/env bash
# version=3.5.0b1
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/install.sh" "$@"
