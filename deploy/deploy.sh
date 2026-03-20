#!/usr/bin/env bash
# Submit Cloud Build using cloudbuild.yaml (build → migrate job → run job → deploy Django + Bolt).
#
# Required environment variables:
#   RUNTIME_SA              Full email of Cloud Run runtime service account
#   SUPABASE_STORAGE_BUCKET
#   SUPABASE_S3_ENDPOINT    e.g. https://<ref>.supabase.co/storage/v1/s3
#
# Optional:
#   GCP_PROJECT_ID          (default: gcloud config project)
#   GCP_REGION              (default: us-central1)
#   AR_REPOSITORY           (default: worship-prep)
#   IMAGE_NAME              (default: worship-prep-app)
#   DJANGO_SERVICE          (default: worship-prep-django)
#   BOLT_SERVICE            (default: worship-prep-bolt)
#   MIGRATE_JOB             (default: worship-prep-migrate)
#   SUPABASE_S3_REGION      (default: us-east-1)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Set GCP_PROJECT_ID or run: gcloud config set project <id>" >&2
  exit 1
fi

RUNTIME_SA="${RUNTIME_SA:?Set RUNTIME_SA to the Cloud Run runtime service account email}"
SUPABASE_STORAGE_BUCKET="${SUPABASE_STORAGE_BUCKET:?Set SUPABASE_STORAGE_BUCKET}"
SUPABASE_S3_ENDPOINT="${SUPABASE_S3_ENDPOINT:?Set SUPABASE_S3_ENDPOINT}"

REGION="${GCP_REGION:-us-central1}"
AR_REPO="${AR_REPOSITORY:-worship-prep}"
IMAGE_NAME="${IMAGE_NAME:-worship-prep-app}"
DJANGO_SERVICE="${DJANGO_SERVICE:-worship-prep-django}"
BOLT_SERVICE="${BOLT_SERVICE:-worship-prep-bolt}"
MIGRATE_JOB="${MIGRATE_JOB:-worship-prep-migrate}"
SUPABASE_S3_REGION="${SUPABASE_S3_REGION:-us-east-1}"

gcloud builds submit "${ROOT}" \
  --project="${PROJECT_ID}" \
  --config="${ROOT}/cloudbuild.yaml" \
  --substitutions=\
"_REGION=${REGION},\
_AR_REPOSITORY=${AR_REPO},\
_IMAGE_NAME=${IMAGE_NAME},\
_RUNTIME_SA=${RUNTIME_SA},\
_DJANGO_SERVICE=${DJANGO_SERVICE},\
_BOLT_SERVICE=${BOLT_SERVICE},\
_MIGRATE_JOB=${MIGRATE_JOB},\
_SUPABASE_STORAGE_BUCKET=${SUPABASE_STORAGE_BUCKET},\
_SUPABASE_S3_ENDPOINT=${SUPABASE_S3_ENDPOINT},\
_SUPABASE_S3_REGION=${SUPABASE_S3_REGION}"
