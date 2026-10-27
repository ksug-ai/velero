#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
require_context
ensure_velero
if ! gcloud storage buckets describe "gs://$MY_BUCKET" --project "$MY_PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$MY_BUCKET" --project "$MY_PROJECT_ID" --location "$MY_REGION" --uniform-bucket-level-access
fi
if ! gcloud iam service-accounts describe "$GSA_EMAIL" --project "$MY_PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$MY_GSA_NAME" --project "$MY_PROJECT_ID" --display-name 'Velero demo'
fi
gcloud storage buckets add-iam-policy-binding "gs://$MY_BUCKET" --member "serviceAccount:$GSA_EMAIL" --role roles/storage.objectAdmin
gcloud iam service-accounts add-iam-policy-binding "$GSA_EMAIL" --project "$MY_PROJECT_ID" \
  --member "serviceAccount:$MY_PROJECT_ID.svc.id.goog[velero/velero]" --role roles/iam.workloadIdentityUser
gcloud iam service-accounts add-iam-policy-binding "$GSA_EMAIL" --project "$MY_PROJECT_ID" \
  --member "serviceAccount:$GSA_EMAIL" --role roles/iam.serviceAccountTokenCreator
velero install --image "velero/velero:$VELERO_VERSION" --provider gcp \
  --plugins "velero/velero-plugin-for-gcp:$GCP_PLUGIN_VERSION" --bucket "$MY_BUCKET" \
  --no-secret --sa-annotations "iam.gke.io/gcp-service-account=$GSA_EMAIL" \
  --backup-location-config "serviceAccount=$GSA_EMAIL" \
  --use-volume-snapshots=false --use-node-agent
kubectl -n velero rollout status deployment/velero --timeout=300s
kubectl -n velero rollout status daemonset/node-agent --timeout=300s
kubectl -n velero wait backupstoragelocation/default --for=jsonpath='{.status.phase}'=Available --timeout=180s
kubectl apply -f "$ROOT/velero-schedule.yaml"
