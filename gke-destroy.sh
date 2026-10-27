#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
confirm "Delete cluster $MY_CLUSTER in $MY_PROJECT_ID/$MY_ZONE?"
gcloud container clusters delete "$MY_CLUSTER" --project "$MY_PROJECT_ID" --zone "$MY_ZONE"
echo "Backup bucket and IAM identity retained. See LAB_GUIDE.md for explicit cleanup."
