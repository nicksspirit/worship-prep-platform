#!/bin/sh
set -eu

/docker-entrypoint.sh nginx -e stderr -c /tmp/wpp-nginx.conf -g 'daemon off;' &
pid=$!
# Cloud Run sends SIGTERM; Nginx drains active requests on SIGQUIT.
trap 'kill -QUIT "$pid"; wait "$pid"; exit 0' TERM INT
wait "$pid"
