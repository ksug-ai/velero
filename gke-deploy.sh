#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
gcloud container clusters create "$MY_CLUSTER" --project "$MY_PROJECT_ID" \
  --zone "$MY_ZONE" --num-nodes 1 --machine-type "$MY_MACHINE_TYPE" \
  --release-channel regular --image-type COS_CONTAINERD \
  --workload-pool "$MY_PROJECT_ID.svc.id.goog" \
  --workload-metadata GKE_METADATA --addons GcePersistentDiskCsiDriver
gcloud container clusters get-credentials "$MY_CLUSTER" --project "$MY_PROJECT_ID" --zone "$MY_ZONE"
echo 'Cluster ready. Run ./postgresql-deploy.sh next.'
