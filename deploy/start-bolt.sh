#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL must be set for the Bolt service." >&2
  exit 1
fi

BOLT_PORT="${BOLT_PORT:-8000}"
if [[ ! "${BOLT_PORT}" =~ ^[0-9]+$ ]]; then
  echo "BOLT_PORT must be numeric." >&2
  exit 1
fi

export DJANGO_BOLT_SHUTDOWN_TIMEOUT="${DJANGO_BOLT_SHUTDOWN_TIMEOUT:-8}"
exec python manage.py runbolt \
  --host 0.0.0.0 \
  --port "${BOLT_PORT}" \
  --processes "${BOLT_PROCESSES:-1}" \
  --workers-kill-timeout 8
