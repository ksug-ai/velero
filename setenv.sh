#!/usr/bin/env bash
# Override these in your shell; no credentials belong in this file.
export MY_PROJECT_ID="${MY_PROJECT_ID:-}"
export MY_CLUSTER="${MY_CLUSTER:-velero-demo}"
export MY_MACHINE_TYPE="${MY_MACHINE_TYPE:-e2-standard-2}"
export MY_REGION="${MY_REGION:-us-central1}"
export MY_ZONE="${MY_ZONE:-us-central1-f}"
export MY_BUCKET="${MY_BUCKET:-${MY_PROJECT_ID}-velero-demo}"
export MY_GSA_NAME="${MY_GSA_NAME:-velero-demo}"
export VELERO_VERSION="${VELERO_VERSION:-v1.18.1}"
export GCP_PLUGIN_VERSION="${GCP_PLUGIN_VERSION:-v1.14.4}"
