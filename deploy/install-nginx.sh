#!/usr/bin/env bash
set -euo pipefail

# Stable 1.30 includes HTTP/2 upstream support and its security fixes.
NGINX_VERSION=1.30.5-1~bookworm
apt-get update -qq
apt-get install -y --no-install-recommends curl ca-certificates gnupg
curl -fsSL https://nginx.org/keys/nginx_signing.key \
  -o /tmp/nginx-signing.key
gpg --batch --show-keys --with-colons /tmp/nginx-signing.key \
  | grep -q '^fpr:::::::::573BFD6B3D8FBC641079A6ABABF5BD827BD9BF62:$'
gpg --batch --yes --dearmor -o /usr/share/keyrings/nginx-archive-keyring.gpg \
  /tmp/nginx-signing.key
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] https://nginx.org/packages/debian bookworm nginx' \
  > /etc/apt/sources.list.d/nginx.list
apt-get update -qq
apt-get install -y --no-install-recommends "nginx=${NGINX_VERSION}"
nginx -V 2>&1 | grep -q -- '--with-http_v2_module'
rm -f /tmp/nginx-signing.key
rm -rf /var/lib/apt/lists/*
