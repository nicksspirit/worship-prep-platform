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

exec gunicorn backend.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WORKERS}" \
  --access-logfile - \
  --error-logfile -
