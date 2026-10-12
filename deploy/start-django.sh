#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must be set for the Django service." >&2
  exit 1
fi

PORT="${PORT:-8080}"
if [[ ! "${PORT}" =~ ^[0-9]+$ ]]; then
  echo "PORT must be numeric." >&2
  exit 1
fi

# Cloud Run allows ten seconds; leave two for container cleanup.
exec gunicorn backend.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --graceful-timeout 8 \
  --forwarded-allow-ips '*' \
  --config python:backend.gunicorn
