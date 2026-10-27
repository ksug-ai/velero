#!/usr/bin/env bash
# KSUG.AI: one command for the GKE + Aurora + Velero demo.
source "$(dirname "$0")/scripts/common.sh"
[[ $# -eq 0 ]] || { echo 'Usage: ./setup.sh (configure via setenv.sh environment overrides)' >&2; exit 1; }
for tool in gcloud kubectl velero; do
  command -v "$tool" >/dev/null || { echo "Missing required tool: $tool. See README.md prerequisites." >&2; exit 1; }
done
velero version --client-only | grep -F "Version: $VELERO_VERSION" >/dev/null || {
  echo "Install Velero CLI $VELERO_VERSION before setup (see README.md)." >&2; exit 1;
}
"$ROOT/createsa.sh"
cluster_info=$(gcloud container clusters list --project "$MY_PROJECT_ID" --filter="name=$MY_CLUSTER" --format='value(location,status)')
if [[ -z "$cluster_info" ]]; then
  "$ROOT/gke-deploy.sh"
else
  IFS=$'\t' read -r location status <<< "$cluster_info"
  [[ "$cluster_info" != *$'\n'* && "$location" == "$MY_ZONE" ]] || {
    echo "Cluster $MY_CLUSTER exists in another location: $cluster_info. Set MY_ZONE to its zone and retry." >&2; exit 1;
  }
  [[ "$status" == RUNNING ]] || { echo "Cluster $MY_CLUSTER is $status; wait for RUNNING before retrying." >&2; exit 1; }
  gcloud container clusters get-credentials "$MY_CLUSTER" --project "$MY_PROJECT_ID" --zone "$MY_ZONE"
fi
"$ROOT/postgresql-deploy.sh"
if [[ -n "${AI_APP_IMAGE:-}" ]]; then
  "$ROOT/ai-app-deploy.sh"
else
  "$ROOT/ai-app/build-and-push.sh"
fi
"$ROOT/velero-deploy.sh"
echo 'KSUG.AI demo setup complete: PostgreSQL, Aurora, and Velero are ready.'
echo 'Next: kubectl -n velero-demo port-forward svc/ai-assistant 8080:8080'
echo 'Open http://localhost:8080, or Cloud Shell Web Preview on port 8080.'
