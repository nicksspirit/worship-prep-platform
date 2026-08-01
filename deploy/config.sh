#!/usr/bin/env bash
# Shared deployment configuration. Add or rename deploy keys here first.

DEFAULT_ENV_VALUES=(
  "GCP_PROJECT_ID=worship-prep-portal"
  "GCP_REGION=us-west1"
  "AR_REPOSITORY=worship-prep"
  "IMAGE_NAME=worship-prep-app"
  "DJANGO_SERVICE=wpp-app"
  "BOLT_SERVICE=wpp-api"
  "MIGRATE_JOB=wpp-migrate"
  "RUNTIME_SA_NAME=wpp-runtime"
  "SUPABASE_STORAGE_BUCKET=wpp-media"
  "SUPABASE_CATALOG_IMPORT_BUCKET=wpp-catalog-imports"
  "SUPABASE_S3_REGION=us-east-1"
  "EMAIL_PORT=587"
)

CANONICAL_HOSTS=(
  "app.rccgcm.org"
  "api.rccgcm.org"
)

INFRA_SUBSTITUTIONS=(
  "REGION=GCP_REGION"
  "AR_REPOSITORY=AR_REPOSITORY"
  "IMAGE_NAME=IMAGE_NAME"
  "RUNTIME_SA=RUNTIME_SA"
  "DJANGO_SERVICE=DJANGO_SERVICE"
  "BOLT_SERVICE=BOLT_SERVICE"
  "MIGRATE_JOB=MIGRATE_JOB"
)

COMMON_RUNTIME_ENV_KEYS=(
  SUPABASE_STORAGE_BUCKET
  SUPABASE_CATALOG_IMPORT_BUCKET
  SUPABASE_S3_ENDPOINT
  SUPABASE_S3_REGION
  EMAIL_HOST
  EMAIL_PORT
  EMAIL_HOST_USER
  DEFAULT_FROM_EMAIL
  ALLOWED_HOSTS
)

COMMON_RUNTIME_ENV_VALUES=(
  "DJANGO_ENV=prod"
)

DJANGO_RUNTIME_ENV_KEYS=(
  CSRF_TRUSTED_ORIGINS
)

REQUIRED_DEPLOY_ENV_KEYS=(
  SUPABASE_S3_ENDPOINT
  EMAIL_HOST
  EMAIL_HOST_USER
  DEFAULT_FROM_EMAIL
)

BUILD_SECRET_KEYS=(
  SUPABASE_S3_ACCESS_KEY
  SUPABASE_S3_SECRET_KEY
)

BUILD_ARG_KEYS=(
  SUPABASE_STORAGE_BUCKET
  SUPABASE_CATALOG_IMPORT_BUCKET
  SUPABASE_S3_ENDPOINT
  SUPABASE_S3_REGION
  "${BUILD_SECRET_KEYS[@]}"
)

COMMON_RUNTIME_SECRET_KEYS=(
  DATABASE_URL
  SECRET_KEY
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  SUPABASE_S3_ACCESS_KEY
  SUPABASE_S3_SECRET_KEY
  EMAIL_HOST_PASSWORD
)

MIGRATE_SECRET_KEYS=(
  DIRECT_URL
  SECRET_KEY
)

append_csv_value() {
  local csv="${1:-}"
  local required="$2"
  local IFS=','
  local values=()
  local value

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

join_csv() {
  local IFS=','
  printf '%s' "$*"
}

join_gcloud_map() {
  local joined=""
  local item

  for item in "$@"; do
    if [[ -z "$joined" ]]; then
      joined="$item"
    else
      joined="${joined}|${item}"
    fi
  done

  printf '^|^%s' "$joined"
}

cloudbuild_var() {
  printf '_%s' "$1"
}

default_var() {
  local name="$1"
  local value="$2"

  if [[ -z "${!name:-}" ]]; then
    printf -v "$name" '%s' "$value"
    export "$name"
  fi
}

default_value_for_key() {
  local search_key="$1"
  local item
  local key
  local value

  for item in "${DEFAULT_ENV_VALUES[@]}"; do
    key="${item%%=*}"
    value="${item#*=}"
    if [[ "$key" == "$search_key" ]]; then
      printf '%s' "$value"
      return 0
    fi
  done

  return 1
}

runtime_service_account() {
  local project_id="$1"
  local runtime_sa_name="$2"

  printf '%s@%s.iam.gserviceaccount.com' "$runtime_sa_name" "$project_id"
}

apply_local_defaults() {
  local item
  local key
  local value

  for item in "${DEFAULT_ENV_VALUES[@]}"; do
    key="${item%%=*}"
    value="${item#*=}"
    default_var "$key" "$value"
  done

  default_var RUNTIME_SA "$(runtime_service_account "$GCP_PROJECT_ID" "$RUNTIME_SA_NAME")"
}

require_var() {
  local name="$1"
  local hint="${2:-}"

  if [[ -z "${!name:-}" ]]; then
    echo "Set ${name}. ${hint}" >&2
    exit 1
  fi
}

secret_mappings() {
  local mappings=()
  local key

  for key in "$@"; do
    mappings+=("${key}=${key}:latest")
  done

  join_csv "${mappings[@]}"
}

runtime_env_mappings() {
  local mappings=("${COMMON_RUNTIME_ENV_VALUES[@]}")
  local key
  local substitution

  for key in "$@"; do
    substitution="$(cloudbuild_var "$key")"
    require_var "$substitution"
    mappings+=("${key}=${!substitution}")
  done

  join_gcloud_map "${mappings[@]}"
}

build_arg_flags() {
  local flags=()
  local key
  local substitution

  for key in "${BUILD_ARG_KEYS[@]}"; do
    if [[ " ${BUILD_SECRET_KEYS[*]} " == *" ${key} "* ]]; then
      require_var "$key"
      flags+=("--build-arg=${key}=${!key}")
    else
      substitution="$(cloudbuild_var "$key")"
      require_var "$substitution"
      flags+=("--build-arg=${key}=${!substitution}")
    fi
  done

  printf '%s\n' "${flags[@]}"
}

apply_cloudbuild_defaults() {
  local item
  local cloudbuild_key
  local shell_key
  local substitution
  local default_value
  local key

  require_var PROJECT_ID "Cloud Build should provide PROJECT_ID."
  require_var BUILD_ID "Cloud Build should provide BUILD_ID."

  for item in "${INFRA_SUBSTITUTIONS[@]}"; do
    cloudbuild_key="${item%%=*}"
    shell_key="${item#*=}"
    substitution="$(cloudbuild_var "$cloudbuild_key")"

    if [[ "$shell_key" == "RUNTIME_SA" ]]; then
      default_value="$(runtime_service_account \
        "$PROJECT_ID" \
        "$(default_value_for_key RUNTIME_SA_NAME)"
      )"
    elif default_value="$(default_value_for_key "$shell_key")"; then
      :
    else
      continue
    fi

    default_var "$substitution" "$default_value"
  done

  for key in "${COMMON_RUNTIME_ENV_KEYS[@]}" "${DJANGO_RUNTIME_ENV_KEYS[@]}"; do
    substitution="$(cloudbuild_var "$key")"

    if default_value="$(default_value_for_key "$key")"; then
      default_var "$substitution" "$default_value"
    fi
  done

  _ALLOWED_HOSTS="$(normalize_allowed_hosts "${_ALLOWED_HOSTS:-}")"
  export _ALLOWED_HOSTS

  _CSRF_TRUSTED_ORIGINS="$(normalize_csrf_origins "${_CSRF_TRUSTED_ORIGINS:-}")"
  export _CSRF_TRUSTED_ORIGINS
}

require_cloudbuild_runtime_env() {
  local key
  local substitution

  for key in "${REQUIRED_DEPLOY_ENV_KEYS[@]}"; do
    substitution="$(cloudbuild_var "$key")"
    require_var "$substitution"
  done
}

image_uri() {
  printf '%s-docker.pkg.dev/%s/%s/%s:%s' \
    "$_REGION" \
    "$PROJECT_ID" \
    "$_AR_REPOSITORY" \
    "$_IMAGE_NAME" \
    "$BUILD_ID"
}

normalize_allowed_hosts() {
  local hosts="${1:-localhost,127.0.0.1}"
  local host

  hosts="$(append_csv_value "$hosts" ".run.app")"
  for host in "${CANONICAL_HOSTS[@]}"; do
    hosts="$(append_csv_value "$hosts" "$host")"
  done

  printf '%s' "$hosts"
}

normalize_csrf_origins() {
  local origins="${1:-http://localhost:8000,http://127.0.0.1:8000}"
  local host

  origins="$(append_csv_value "$origins" "https://*.run.app")"
  for host in "${CANONICAL_HOSTS[@]}"; do
    origins="$(append_csv_value "$origins" "https://${host}")"
  done

  printf '%s' "$origins"
}
