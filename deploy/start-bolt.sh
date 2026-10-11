#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must be set for the Bolt service." >&2
  exit 1
fi

PORT="${PORT:-8080}"
PROCESSES="${BOLT_PROCESSES:-1}"

if [[ ! "${PORT}" =~ ^[0-9]+$ ]] || [[ "${PORT}" == 8000 ]]; then
  echo "PORT must be numeric and different from the internal Bolt port 8000." >&2
  exit 1
fi

GCP_PROJECT_ID="${GCP_PROJECT_ID:-}"
if [[ -n "${GCP_PROJECT_ID}" && ! "${GCP_PROJECT_ID}" =~ ^[a-z][a-z0-9-]{4,61}[a-z0-9]$ ]]; then
  echo "GCP_PROJECT_ID must be a valid Cloud project ID." >&2
  exit 1
fi

sed -e "s/__GCP_PROJECT_ID__/${GCP_PROJECT_ID}/g" \
  deploy/nginx-logging.conf.template > /tmp/wpp-nginx-logging.conf

sed -e "s/__PORT__/${PORT}/g" \
  deploy/nginx-bolt.conf.template > /tmp/wpp-nginx.conf
nginx -e stderr -t -c /tmp/wpp-nginx.conf

# Bolt 0.6 serves HTTP/1; Nginx supplies Cloud Run's required h2c ingress.
set -m
python manage.py runbolt \
  --host 127.0.0.1 \
  --port 8000 \
  --processes "${PROCESSES}" &
BACKEND_PID=$!
nginx -e stderr -c /tmp/wpp-nginx.conf -g 'daemon off;' &
PROXY_PID=$!
source deploy/supervise.sh
