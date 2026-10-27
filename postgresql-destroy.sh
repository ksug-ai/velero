#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
require_context
confirm 'Delete the velero-demo namespace and its database volumes?'
kubectl delete namespace velero-demo --wait=true
