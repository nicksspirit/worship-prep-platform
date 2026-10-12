# ADR-0015: Deliver Catalog Imports Directly to the API

## Status

Accepted; supersedes ADR-0014.

## Date

2026-10-12

## Context

The exporter accepts a separate API origin, but `/install` derived that origin
from its own app hostname. ADR-0014 added an app Nginx proxy for those uploads.
On October 12, Cloud Run's default TCP startup probe admitted requests to Nginx
before Gunicorn was listening, causing homepage 502s. The independent API service
has the same proxy/backend startup race.

## Decision

Configure new exporter installations to upload directly to `api.rccgcm.org` while
serving the bootstrap and installer from `app.rccgcm.org`. Reinstall existing
Windows exporters during the rollout; retain their instance identity,
outbox, and protected API key, and update the saved endpoint and scheduled task.
`CATALOG_EXPORTER_API_URL` selects the upload origin for other environments.

Run only Gunicorn in the app container, using `exec` and an eight-second graceful
shutdown. Remove the app Nginx configuration and Bolt upstream discovery. Build
separate `prod` (Python app, Bolt, and migrations) and `ingress` images from the
shared Dockerfile. Run Nginx and Bolt as separate containers in the API service.
Nginx uses the official `nginx:1.30.5-trixie` image with our configuration templates
and its standard entrypoint; no custom installation, binary copying, or Python
library matching is needed. Keep HTTP/2 ingress because Bolt 0.12.0 serves HTTP/1
and catalog uploads must exceed Cloud Run's 32 MiB HTTP/1 request limit.

Upgrade Django Bolt from 0.6.0 to the stable 0.12 series. Use its public `Response`
for schema-backed error responses and adapt exception responses to its middleware
wrapper. Set its aggregate upload limit to 130 MiB, matching Nginx while keeping
the existing 128 MiB package and 1 MiB event limits. Preserve request and Cloud
trace identities in ingress, dispatch, and import-result logs.

Configure an HTTP startup probe for `/health/` on the app. The API backend probes
the existing `/api/v1/docs` route on port 8000. Its Nginx ingress depends on Bolt,
so Cloud Run waits for Bolt's successful probe before starting Nginx, then probes
that route through Nginx on port 8080 before admitting traffic. These probes prove
application startup, not database or storage availability. Gunicorn and Bolt run
directly as their main processes. A small Nginx launcher converts Cloud Run's
SIGTERM to SIGQUIT so active requests can drain for up to eight seconds. It calls
the official entrypoint to render configuration. Cloud Run manages startup
dependencies, replacing the shell supervisor without adding Tini.

## Alternatives Considered

Nginx and Django sidecars would retain an unnecessary app proxy after exporters
move to the API origin. Keep sidecars only for the API's required HTTP/2 boundary.
Copying an official Nginx binary into Python still requires matching shared
libraries and supervising two servers. The independent official container avoids
those concerns. Tini reaps processes and forwards signals, but does not establish
application readiness; Cloud Run startup probes and dependencies provide that gate.

## Consequences

The app domain intentionally no longer serves `/api/`. Existing callers must move
to the API domain; old Windows installations fail until reconfigured. API
credentials, import validation, request limits, and independent scaling remain
unchanged. Cold starts can still delay requests, but traffic is withheld until
the application responds successfully to its startup probe.
