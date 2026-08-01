#!/usr/bin/env bash
# One-time GCP bootstrap: APIs, Artifact Registry, Cloud Build + runtime service accounts, IAM.
#
# Required env:
#   GCP_PROJECT_ID   (or use gcloud config project)
# Optional:
#   GCP_REGION       default us-central1
#   AR_REPOSITORY    default worship-prep
#   RUNTIME_SA       default worship-prep-runtime@${PROJECT}.iam.gserviceaccount.com
#
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Set GCP_PROJECT_ID or gcloud config set project <id>." >&2
  exit 1
fi

REGION="${GCP_REGION:-us-central1}"
AR_REPO="${AR_REPOSITORY:-worship-prep}"
RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-worship-prep-runtime}"
RUNTIME_SA_EMAIL="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Using project=${PROJECT_ID} region=${REGION}"

gcloud config set project "${PROJECT_ID}"

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com

gcloud artifacts repositories describe "${AR_REPO}" \
  --location="${REGION}" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Worship Prep Platform images"

gcloud iam service-accounts describe "${RUNTIME_SA_EMAIL}" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "${RUNTIME_SA_NAME}" \
    --display-name="Worship Prep runtime (Cloud Run)"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/run.admin" \
  --condition=None

gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SA_EMAIL}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/iam.serviceAccountUser" \
  --project="${PROJECT_ID}"

gcloud artifacts repositories add-iam-policy-binding "${AR_REPO}" \
  --location="${REGION}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/artifactregistry.writer"

echo "Bootstrap complete."
echo "Runtime service account: ${RUNTIME_SA_EMAIL}"
echo "Create secrets in Secret Manager (DATABASE_URL, DIRECT_URL, SECRET_KEY, OAuth, S3 keys) and wire them in cloudbuild / deploy."
