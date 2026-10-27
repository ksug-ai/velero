#!/usr/bin/env bash
source "$(dirname "$0")/../scripts/common.sh"
# Builds remotely; no local Docker daemon required. Uses a dedicated Artifact Registry repo.
repo=velero-demo
image="$MY_REGION-docker.pkg.dev/$MY_PROJECT_ID/$repo/ai-assistant:$(date -u +%Y%m%d%H%M%S)"
gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com --project "$MY_PROJECT_ID"
if ! gcloud artifacts repositories describe "$repo" --location "$MY_REGION" --project "$MY_PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$repo" --location "$MY_REGION" --repository-format docker --project "$MY_PROJECT_ID"
fi
gcloud builds submit "$ROOT/ai-app" --tag "$image" --project "$MY_PROJECT_ID"
printf '\nBuild complete. Deploy with:\nAI_APP_IMAGE=%q ./ai-app-deploy.sh\n' "$image"
