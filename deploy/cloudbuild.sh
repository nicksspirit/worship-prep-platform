#!/usr/bin/env bash
# Cloud Build step helpers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source "${ROOT}/deploy/config.sh"

docker_build_args() {
  local args=()
  local arg

  while IFS= read -r arg; do
    args+=("$arg")
  done < <(build_arg_flags)

  printf '%s\n' "${args[@]}"
}

build_image() {
  local args=()
  local arg

  while IFS= read -r arg; do
    args+=("$arg")
  done < <(docker_build_args)

  docker build \
    -f docker/Dockerfile \
    --target=prod \
    "${args[@]}" \
    -t "$(image_uri)" \
    .
}

push_image() {
  docker push "$(image_uri)"
}

deploy_migrate_job() {
  gcloud run jobs deploy "$_MIGRATE_JOB" \
    --image="$(image_uri)" \
    --region="$_REGION" \
    --service-account="$_RUNTIME_SA" \
    --set-secrets="$(secret_mappings "${MIGRATE_SECRET_KEYS[@]}")" \
    --command=/bin/bash \
    --args=deploy/start-migrate.sh \
    --max-retries=1 \
    --tasks=1
}

run_migrate_job() {
  gcloud run jobs execute "$_MIGRATE_JOB" \
    --region="$_REGION" \
    --wait
}

deploy_django() {
  local env_keys=(
    "${COMMON_RUNTIME_ENV_KEYS[@]}"
    "${DJANGO_RUNTIME_ENV_KEYS[@]}"
  )

  gcloud run deploy "$_DJANGO_SERVICE" \
    --image="$(image_uri)" \
    --region="$_REGION" \
    --service-account="$_RUNTIME_SA" \
    --allow-unauthenticated \
    --port=8080 \
    --set-env-vars="$(runtime_env_mappings "${env_keys[@]}")" \
    --set-secrets="$(secret_mappings "${COMMON_RUNTIME_SECRET_KEYS[@]}")" \
    --command=/bin/bash \
    --args=deploy/start-django.sh
}

deploy_bolt() {
  gcloud run deploy "$_BOLT_SERVICE" \
    --image="$(image_uri)" \
    --region="$_REGION" \
    --service-account="$_RUNTIME_SA" \
    --allow-unauthenticated \
    --port=8080 \
    --set-env-vars="$(runtime_env_mappings "${COMMON_RUNTIME_ENV_KEYS[@]}")" \
    --set-secrets="$(secret_mappings "${COMMON_RUNTIME_SECRET_KEYS[@]}")" \
    --command=/bin/bash \
    --args=deploy/start-bolt.sh
}

main() {
  apply_cloudbuild_defaults
  require_cloudbuild_runtime_env

  case "${1:-}" in
    build-image)
      build_image
      ;;
    push-image)
      push_image
      ;;
    deploy-migrate-job)
      deploy_migrate_job
      ;;
    run-migrate-job)
      run_migrate_job
      ;;
    deploy-django)
      deploy_django
      ;;
    deploy-bolt)
      deploy_bolt
      ;;
    *)
      echo "Usage: $0 {build-image|push-image|deploy-migrate-job|run-migrate-job|deploy-django|deploy-bolt}" >&2
      exit 2
      ;;
  esac
}

main "$@"
