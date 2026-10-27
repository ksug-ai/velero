#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
require_context
confirm 'Uninstall Velero? Backups and Google Cloud IAM identity will be retained.'
ensure_velero
velero uninstall --force
