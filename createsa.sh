#!/usr/bin/env bash
source "$(dirname "$0")/scripts/common.sh"
# Historical filename retained; this enables APIs, without creating keys.
gcloud services enable container.googleapis.com compute.googleapis.com iam.googleapis.com iamcredentials.googleapis.com storage.googleapis.com --project "$MY_PROJECT_ID"
