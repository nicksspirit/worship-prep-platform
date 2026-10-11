# ADR-0014: Route App API Requests Through Ingress

## Status

Accepted

## Date

2026-10-11

## Context

Cloud Run maps `app.rccgcm.org` directly to the Django service. The Windows
exporter uses that platform URL, so its Bolt import path returns Django's 404.
The deployment has no load balancer with path-based routing.

## Decision

Run Nginx at the Django service's ingress. Forward `/api/` to the existing Bolt
service over verified HTTPS, and other requests to local Gunicorn. Cloud Build
discovers the Bolt service URL rather than hard-coding a production hostname.
Keep endpoint ownership and independent service scaling as defined in ADR-0004.

Enable HTTP/2 on both Cloud Run services. Their ingress Nginx listeners accept
cleartext HTTP/2 (h2c), and the app-to-Bolt proxy uses HTTP/2 over verified TLS.
Django Bolt 0.6.0 accepts HTTP/1 only, so its container also runs Nginx and forwards
to Bolt on loopback. The local HTTP/1 connection does not cross Cloud Run's
HTTP/1 request boundary. This retains the same two independently scaled services.

## Alternatives Considered

An external load balancer would add infrastructure and require DNS changes.
A redirect would require the streaming exporter to replay the request and send
its authorization header to another host. A Django proxy view would violate
ADR-0004. The ingress proxy avoids those changes.

## Consequences

The production image installs the signed official stable Nginx 1.30.5 package
for Debian bookworm. Nginx 1.29.4 introduced HTTP/2 upstream proxying; the pinned
stable release includes subsequent security fixes. Both launchers use bounded
shutdown supervision for their backend and Nginx.

Catalog Import Packages remain limited to 128 MiB and exporter events to 1 MiB.
Both ingress proxies allow 130 MiB for the complete multipart request. Cloud Run's
32 MiB HTTP/1 limit no longer gates this HTTP/2 path. The importer retains its
existing expanded-content, authentication, validation, and atomic promotion rules.

See [HTTP/2 deployment and verification](../http2-catalog-imports.md),
[Cloud Run HTTP/2](https://docs.cloud.google.com/run/docs/configuring/http2), and
[Nginx upstream protocol support](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_http_version).
