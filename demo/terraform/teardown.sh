#!/usr/bin/env bash
set -euo pipefail

echo "=================================================================="
echo "🧹 GSIS Gabay AI Executive Demo — 1-Command Terraform Teardown"
echo "=================================================================="

export GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token)"
export GOOGLE_PROJECT="markea-testbed-dev"

TERRAFORM_BIN="${HOME}/.local/bin/terraform"
if ! command -v "${TERRAFORM_BIN}" &> /dev/null; then
  TERRAFORM_BIN="terraform"
fi

"${TERRAFORM_BIN}" destroy -auto-approve

echo "✅ All GSIS Gabay AI Demo Cloud Run, Secret Manager, IAM, and Artifact Registry resources have been cleanly destroyed."
