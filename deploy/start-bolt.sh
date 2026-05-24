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

exec python manage.py runbolt \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --processes "${PROCESSES}"
