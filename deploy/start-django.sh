#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must be set for the Django service." >&2
  exit 1
fi

PORT="${PORT:-8080}"
WORKERS="${WEB_CONCURRENCY:-2}"

if [[ ! "${PORT}" =~ ^[0-9]+$ ]] || [[ "${PORT}" == 8000 ]]; then
  echo "PORT must be numeric and different from the internal Django port 8000." >&2
  exit 1
fi
if [[ ! "${BOLT_UPSTREAM_URL:-}" =~ ^https://[a-zA-Z0-9.-]+(:[0-9]+)?$ ]]; then
  echo "BOLT_UPSTREAM_URL must be an HTTPS origin for the Bolt service." >&2
  exit 1
fi

GCP_PROJECT_ID="${GCP_PROJECT_ID:-}"
if [[ -n "${GCP_PROJECT_ID}" && ! "${GCP_PROJECT_ID}" =~ ^[a-z][a-z0-9-]{4,61}[a-z0-9]$ ]]; then
  echo "GCP_PROJECT_ID must be a valid Cloud project ID." >&2
  exit 1
fi

BOLT_ADDRESS="${BOLT_UPSTREAM_URL#https://}"
if [[ "${BOLT_ADDRESS}" != *:* ]]; then
  BOLT_ADDRESS="${BOLT_ADDRESS}:443"
fi

sed -e "s/__GCP_PROJECT_ID__/${GCP_PROJECT_ID}/g" \
  deploy/nginx-logging.conf.template > /tmp/wpp-nginx-logging.conf

sed -e "s/__PORT__/${PORT}/g" \
  -e "s/__BOLT_HOST__/${BOLT_UPSTREAM_URL#https:\/\/}/g" \
  -e "s/__BOLT_ADDRESS__/${BOLT_ADDRESS}/g" \
  deploy/nginx.conf.template > /tmp/wpp-nginx.conf
nginx -e stderr -t -c /tmp/wpp-nginx.conf

# Give each server its own process group so forced cleanup includes its workers.
set -m
gunicorn backend.wsgi:application \
  --bind "127.0.0.1:8000" \
  --workers "${WORKERS}" \
  --config python:backend.gunicorn &
BACKEND_PID=$!
nginx -e stderr -c /tmp/wpp-nginx.conf -g 'daemon off;' &
PROXY_PID=$!

source deploy/supervise.sh
