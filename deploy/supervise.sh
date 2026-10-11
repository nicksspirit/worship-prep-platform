#!/usr/bin/env bash
stop_servers() {
  trap '' TERM INT
  kill -QUIT "$PROXY_PID" 2>/dev/null || true
  kill -TERM "$BACKEND_PID" 2>/dev/null || true
  # Cloud Run allows ten seconds; reserve two for forced cleanup and reaping.
  (
    sleep 8
    kill -KILL -- "-$BACKEND_PID" "-$PROXY_PID" 2>/dev/null || true
  ) &
  DEADLINE_PID=$!
  wait "$BACKEND_PID" "$PROXY_PID" 2>/dev/null || true
  kill -KILL -- "-$DEADLINE_PID" "-$BACKEND_PID" "-$PROXY_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}

trap stop_servers EXIT
trap 'exit 0' TERM INT
wait -n "$BACKEND_PID" "$PROXY_PID" || true
echo "A supervised server exited unexpectedly; stopping the service." >&2
exit 1
