#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 18 or newer is required." >&2
  exit 1
fi

exec node "$SCRIPT_DIR/.skill-tree/bin/install.js" "$@"
