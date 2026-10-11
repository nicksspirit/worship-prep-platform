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

BOLT_ADDRESS="${BOLT_UPSTREAM_URL#https://}"
if [[ "${BOLT_ADDRESS}" != *:* ]]; then
  BOLT_ADDRESS="${BOLT_ADDRESS}:443"
fi

sed -e "s/__PORT__/${PORT}/g" \
  -e "s/__BOLT_HOST__/${BOLT_UPSTREAM_URL#https:\/\/}/g" \
  -e "s/__BOLT_ADDRESS__/${BOLT_ADDRESS}/g" \
  deploy/nginx.conf.template > /tmp/wpp-nginx.conf
nginx -t -c /tmp/wpp-nginx.conf

# Give each server its own process group so forced cleanup includes its workers.
set -m
gunicorn backend.wsgi:application \
  --bind "127.0.0.1:8000" \
  --workers "${WORKERS}" \
  --access-logfile - \
  --error-logfile - &
DJANGO_PID=$!
nginx -c /tmp/wpp-nginx.conf -g 'daemon off;' &
PROXY_PID=$!

stop_servers() {
  trap '' TERM INT
  kill -QUIT "$PROXY_PID" 2>/dev/null || true
  kill -TERM "$DJANGO_PID" 2>/dev/null || true
  # Cloud Run allows ten seconds; reserve two for forced cleanup and reaping.
  (
    sleep 8
    kill -KILL -- "-$DJANGO_PID" "-$PROXY_PID" 2>/dev/null || true
  ) &
  DEADLINE_PID=$!
  wait "$DJANGO_PID" "$PROXY_PID" 2>/dev/null || true
  kill -KILL -- "-$DEADLINE_PID" "-$DJANGO_PID" "-$PROXY_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}

trap stop_servers EXIT
trap 'exit 0' TERM INT
wait -n "$DJANGO_PID" "$PROXY_PID" || true
echo "A supervised server exited unexpectedly; stopping the app service." >&2
exit 1
