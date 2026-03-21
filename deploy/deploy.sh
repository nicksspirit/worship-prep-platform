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
#   DJANGO_SERVICE          (default: wpp-app)
#   BOLT_SERVICE            (default: wpp-api)
#   MIGRATE_JOB             (default: wpp-migrate)
#   SUPABASE_S3_REGION      (default: us-east-1)
#   ALLOWED_HOSTS           Comma-separated runtime hosts; .run.app is always appended
#   CSRF_TRUSTED_ORIGINS    Comma-separated trusted origins; https://*.run.app is always appended
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
DJANGO_SERVICE="${DJANGO_SERVICE:-wpp-app}"
BOLT_SERVICE="${BOLT_SERVICE:-wpp-api}"
MIGRATE_JOB="${MIGRATE_JOB:-wpp-migrate}"
SUPABASE_S3_REGION="${SUPABASE_S3_REGION:-us-east-1}"

append_csv_value() {
  local csv="${1:-}"
  local required="$2"
  local IFS=','
  local values=()

  if [[ -n "$csv" ]]; then
    read -r -a values <<< "$csv"
    for value in "${values[@]}"; do
      value="${value#"${value%%[![:space:]]*}"}"
      value="${value%"${value##*[![:space:]]}"}"
      if [[ "$value" == "$required" ]]; then
        printf '%s' "$csv"
        return
      fi
    done

    printf '%s,%s' "$csv" "$required"
    return
  fi

  printf '%s' "$required"
}

# Keep wildcard Cloud Run entries even when deploying from an older .env that
# still sets narrower host/origin lists.
ALLOWED_HOSTS="$(append_csv_value "${ALLOWED_HOSTS:-localhost,127.0.0.1}" ".run.app")"
CSRF_TRUSTED_ORIGINS="$(
  append_csv_value \
    "${CSRF_TRUSTED_ORIGINS:-http://localhost:8000,http://127.0.0.1:8000}" \
    "https://*.run.app"
)"

gcloud builds submit "${ROOT}" \
  --project="${PROJECT_ID}" \
  --config="${ROOT}/cloudbuild.yaml" \
  --substitutions=\
"^|^_REGION=${REGION}|\
_AR_REPOSITORY=${AR_REPO}|\
_IMAGE_NAME=${IMAGE_NAME}|\
_RUNTIME_SA=${RUNTIME_SA}|\
_DJANGO_SERVICE=${DJANGO_SERVICE}|\
_BOLT_SERVICE=${BOLT_SERVICE}|\
_MIGRATE_JOB=${MIGRATE_JOB}|\
_SUPABASE_STORAGE_BUCKET=${SUPABASE_STORAGE_BUCKET}|\
_SUPABASE_S3_ENDPOINT=${SUPABASE_S3_ENDPOINT}|\
_SUPABASE_S3_REGION=${SUPABASE_S3_REGION}|\
_ALLOWED_HOSTS=${ALLOWED_HOSTS}|\
_CSRF_TRUSTED_ORIGINS=${CSRF_TRUSTED_ORIGINS}"
