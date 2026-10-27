#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
require_context
kubectl apply -f "$ROOT/manifests/postgresql.yaml"
kubectl -n velero-demo rollout status deployment/postgres --timeout=300s
"$ROOT/demo.sh" seed
