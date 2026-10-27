#!/usr/bin/env bash
# KSUG.AI: run the pinned Velero CLI without changing your shell PATH.
source "$(dirname "$0")/scripts/common.sh"
require_context
ensure_velero
exec velero "$@"
