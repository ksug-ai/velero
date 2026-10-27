#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT/setenv.sh"
: "${MY_PROJECT_ID:?Export MY_PROJECT_ID with your Google Cloud project ID}"
GSA_EMAIL="$MY_GSA_NAME@$MY_PROJECT_ID.iam.gserviceaccount.com"
require_context() {
  local expected="gke_${MY_PROJECT_ID}_${MY_ZONE}_${MY_CLUSTER}"
  if [[ "$(kubectl config current-context)" != "$expected" ]]; then
    echo "Expected kubectl context: $expected. Run gcloud container clusters get-credentials first." >&2
    exit 1
  fi
}
confirm() {
  local answer
  read -r -p "$1 Type $MY_CLUSTER to continue: " answer
  [[ "$answer" == "$MY_CLUSTER" ]] || exit 1
}

ensure_velero() {
  if command -v velero >/dev/null 2>&1 && velero version --client-only 2>/dev/null | grep -F "Version: $VELERO_VERSION" >/dev/null; then
    return
  fi
  local cli
  cli=$("$ROOT/scripts/install-velero-cli.sh")
  export PATH="$(dirname "$cli"):$PATH"
}
