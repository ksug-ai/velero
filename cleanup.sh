#!/usr/bin/env bash
# KSUG.AI: preview by default; use --apply to delete the dedicated demo resources.
source "$(dirname "$0")/scripts/common.sh"
exec python3 "$ROOT/scripts/cleanup.py" "$@"
