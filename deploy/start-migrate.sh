#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${DIRECT_URL:-}" ]]; then
  echo "DIRECT_URL must be set for migrations (Supabase direct Postgres, port 5432)." >&2
  exit 1
fi

export DATABASE_URL="${DIRECT_URL}"
exec python manage.py migrate --noinput
