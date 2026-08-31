#!/usr/bin/env bash
set -euo pipefail

# Absolute backend API base URL baked into the SPA at build time.
# Override with: BACKEND_API_BASE_URL=https://your-api.run.app/api/v1 ./frontend_deploy.sh
REGION="${REGION:-europe-north1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-therecode-api}"
IMAGE="${IMAGE:-europe-north1-docker.pkg.dev/therecode-ai/therecode-frontend/therecode-frontend-dashboard:v1}"

if [[ -z "${BACKEND_API_BASE_URL:-}" ]]; then
  if BACKEND_HOST="$(
    gcloud run services describe "${BACKEND_SERVICE}" \
      --region="${REGION}" \
      --format='value(status.url)' 2>/dev/null
  )" && [[ -n "${BACKEND_HOST}" ]]; then
    BACKEND_API_BASE_URL="${BACKEND_HOST}/api/v1"
  else
    echo "ERROR: _VITE_API_BASE_URL is required for the frontend image build." >&2
    echo "Set BACKEND_API_BASE_URL to your Cloud Run API URL, for example:" >&2
    echo "  BACKEND_API_BASE_URL=https://therecode-api-xxxxx.${REGION}.run.app/api/v1 ./frontend_deploy.sh" >&2
    exit 1
  fi
fi

echo "Building frontend with VITE_API_BASE_URL=${BACKEND_API_BASE_URL}"

gcloud builds submit ./frontend \
  --config=./frontend/cloudbuild.yaml \
  --substitutions="_IMAGE=${IMAGE},_VITE_API_BASE_URL=${BACKEND_API_BASE_URL}"


gcloud builds submit ./frontend \
  --config=./frontend/cloudbuild.yaml \
  --substitutions=_IMAGE=europe-north1-docker.pkg.dev/therecode-ai/therecode-frontend/therecode-frontend-dashboard:v2,_VITE_API_BASE_URL=https://therecode-backend-api-683080071974.europe-west1.run.app/api/v1