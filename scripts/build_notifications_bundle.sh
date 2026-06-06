#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE_DIR="$ROOT_DIR/static/js/notifications/modules"
OUT_FILE="$ROOT_DIR/static/js/notifications.js"

if [ ! -d "$MODULE_DIR" ]; then
  echo "Module directory not found: $MODULE_DIR" >&2
  exit 1
fi

{
  cat <<'HEADER'
/**
 * AUTO-GENERATED FILE.
 * Source modules: static/js/notifications/modules/*.js
 * Use scripts/build_notifications_bundle.sh after editing modules.
 */

HEADER

  first_module=1
  for module in "$MODULE_DIR"/*.js; do
    [ -f "$module" ] || continue
    if [ "$first_module" -eq 0 ]; then
      printf '
'
    fi
    first_module=0
    printf '/* ===== Module: %s ===== */

' "$(basename "$module")"
    cat "$module"
  done
} > "$OUT_FILE"

echo "Built $OUT_FILE from modules in $MODULE_DIR"
