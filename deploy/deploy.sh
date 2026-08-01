#!/usr/bin/env bash
# Submit Cloud Build using cloudbuild.yaml.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source "${ROOT}/deploy/config.sh"

ENV_FILE=".env"
DRY_RUN=0

usage() {
  cat <<EOF
Usage: ./deploy/deploy.sh [--env-file PATH] [--dry-run]

Loads deployment values from the environment and, when present, .env.
Required values that cannot be defaulted:
  SUPABASE_S3_ENDPOINT or SUPABASE_URL
  EMAIL_HOST
  EMAIL_HOST_USER
  DEFAULT_FROM_EMAIL

Secrets are read by Cloud Build and Cloud Run from Google Secret Manager.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="${2:?--env-file requires a path}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

load_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
  fi
}

normalize_runtime_lists() {
  ALLOWED_HOSTS="$(normalize_allowed_hosts "${ALLOWED_HOSTS:-}")"
  export ALLOWED_HOSTS

  CSRF_TRUSTED_ORIGINS="$(normalize_csrf_origins "${CSRF_TRUSTED_ORIGINS:-}")"
  export CSRF_TRUSTED_ORIGINS
}

configure() {
  load_env_file

  apply_local_defaults

  if [[ -z "${SUPABASE_S3_ENDPOINT:-}" && -n "${SUPABASE_URL:-}" ]]; then
    SUPABASE_S3_ENDPOINT="${SUPABASE_URL%/}/storage/v1/s3"
    export SUPABASE_S3_ENDPOINT
  fi

  normalize_runtime_lists

  local key
  for key in "${REQUIRED_DEPLOY_ENV_KEYS[@]}"; do
    require_var "$key"
  done
}

build_substitutions() {
  local substitutions=()
  local joined=""
  local item
  local key
  local cloudbuild_key
  local shell_key

  for item in "${INFRA_SUBSTITUTIONS[@]}"; do
    cloudbuild_key="${item%%=*}"
    shell_key="${item#*=}"
    substitutions+=("$(cloudbuild_var "$cloudbuild_key")=${!shell_key}")
  done

  for key in "${COMMON_RUNTIME_ENV_KEYS[@]}" "${DJANGO_RUNTIME_ENV_KEYS[@]}"; do
    substitutions+=("$(cloudbuild_var "$key")=${!key}")
  done

  for item in "${substitutions[@]}"; do
    if [[ -z "$joined" ]]; then
      joined="$item"
    else
      joined="${joined}|${item}"
    fi
  done

  printf '^|^%s' "$joined"
}

print_summary() {
  cat <<EOF
Deploy configuration
  project:        ${GCP_PROJECT_ID}
  region:         ${GCP_REGION}
  image:          ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}
  services:       ${DJANGO_SERVICE}, ${BOLT_SERVICE}
  migrate job:    ${MIGRATE_JOB}
  runtime SA:     ${RUNTIME_SA}
  allowed hosts:  ${ALLOWED_HOSTS}
  CSRF origins:   ${CSRF_TRUSTED_ORIGINS}
EOF
}

main() {
  configure
  print_summary

  local substitutions
  substitutions="$(build_substitutions)"

  if [[ "$DRY_RUN" == 1 ]]; then
    return
  fi

  gcloud builds submit "${ROOT}" \
    --project="${GCP_PROJECT_ID}" \
    --config="${ROOT}/cloudbuild.yaml" \
    --substitutions="$substitutions"
}

main
