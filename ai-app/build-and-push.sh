#!/usr/bin/env bash
# Build and deploy by default. --build-only supports CI or preparing images elsewhere.
build_only=false
case "${1:-}" in
  '') ;;
  --build-only) build_only=true ;;
  -h|--help) echo 'Usage: ./ai-app/build-and-push.sh [--build-only]'; exit 0 ;;
  *) echo 'Usage: ./ai-app/build-and-push.sh [--build-only]' >&2; exit 1 ;;
esac
[[ $# -le 1 ]] || { echo 'Unexpected arguments' >&2; exit 1; }
source "$(dirname "$0")/../scripts/common.sh"
if ! "$build_only"; then
  # Fail before a billed build when deployment prerequisites are missing.
  require_context
  kubectl -n velero-demo get deployment/postgres >/dev/null || {
    echo 'PostgreSQL is missing. Run ./setup.sh for the full setup, or ./postgresql-deploy.sh first.' >&2
    exit 1
  }
fi
repo=velero-demo
image="$MY_REGION-docker.pkg.dev/$MY_PROJECT_ID/$repo/ai-assistant:$(date -u +%Y%m%d%H%M%S)"
gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com --project "$MY_PROJECT_ID"
if ! gcloud artifacts repositories describe "$repo" --location "$MY_REGION" --project "$MY_PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$repo" --location "$MY_REGION" --repository-format docker --project "$MY_PROJECT_ID"
fi
gcloud builds submit "$ROOT/ai-app" --tag "$image" --project "$MY_PROJECT_ID"
if "$build_only"; then
  printf '\nBuild-only complete. The app has NOT been deployed.\nDeploy explicitly with:\nAI_APP_IMAGE=%q ./ai-app-deploy.sh\n' "$image"
else
  echo 'Build complete. Deploying the image now...'
  AI_APP_IMAGE="$image" "$ROOT/ai-app-deploy.sh"
fi
