#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
require_context
: "${AI_APP_IMAGE:?Set AI_APP_IMAGE to your pushed image, or run ./ai-app/build-and-push.sh first}"
# Validate before substituting into YAML.
[[ "$AI_APP_IMAGE" =~ ^[a-zA-Z0-9][a-zA-Z0-9./_:@-]+$ ]] || { echo 'Invalid image reference' >&2; exit 1; }
kubectl -n velero-demo get deployment/postgres >/dev/null
sed "s|AI_APP_IMAGE_PLACEHOLDER|$AI_APP_IMAGE|g" "$ROOT/manifests/ai-app.yaml" | kubectl apply -f -
kubectl -n velero-demo rollout status deployment/ai-assistant --timeout=300s
echo 'Open the app: kubectl -n velero-demo port-forward svc/ai-assistant 8080:8080'
echo 'Then visit http://localhost:8080, upload ai-app/sample-docs/recovery-plan.md, and ask about the recovery passphrase.'
