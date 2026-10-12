# HTTP/2 Catalog Imports

The exporter uses Go's HTTPS transport with automatic HTTP/2 negotiation. It
uploads directly to `https://api.rccgcm.org/api/v1/catalog/imports`:
exporter → Cloud Run API TLS frontend → Bolt Nginx h2c → local Bolt HTTP/1.
Django pages use Gunicorn directly on the app domain. Both services keep
600-second request timeouts and public access with application API-key scopes.

The API runs two containers in one Cloud Run service. Its ingress uses the `ingress`
Docker target based on the official `nginx:1.30.5-trixie` image with our
configuration templates and a small shutdown launcher. Its `bolt` backend uses the same `prod` Python image as
Django and migrations, with no Nginx binary or installation script. The launcher
calls the official entrypoint to expand templates and start Nginx, waits for the
child, and converts Cloud Run SIGTERM to SIGQUIT for graceful request draining.
Nginx limits that drain to eight seconds within Cloud Run's ten-second window.
The API manifest names the ingress port `h2c`; the app explicitly deploys with
`--no-use-http2`.
Locked Bolt 0.12.0 does not accept h2c itself.

The API ingress preserves validated request and Cloud trace identities, generates
bounded identities when absent, and omits query strings and credentials from
completion logs. Cloud Run starts Bolt first and probes `/api/v1/docs` on port
8000. Nginx depends on that successful startup probe, then its own probe checks
the same route through ingress port 8080. Traffic is admitted only after both
checks succeed. Django probes `/health/` directly. These probes check application
startup, not database or storage availability.

The Bolt container uses 2 GiB memory; Nginx has a separate 256 MiB allocation.
The API service uses concurrency 1. In an earlier local Linux full-chain test
using Bolt 0.6.0, a valid 126,479,404-byte package plus 1,048,576 event bytes caused the Bolt
process to peak at 679,284 KiB RSS (about 664 MiB). This exceeds the previous
512 MiB default. Cloud Run also charges its writable in-memory filesystem against
instance memory, including temporary upload files; 2 GiB gives room for those
files and parsed records. Concurrency 1 prevents simultaneous large imports from
multiplying that memory use. Django service resources are unchanged.

Runtime references: [Cloud Run HTTP/2](https://cloud.google.com/run/docs/configuring/http2),
[Cloud Run memory and writable filesystem](https://cloud.google.com/run/docs/configuring/services/memory-limits),
[Cloud Run startup probes](https://docs.cloud.google.com/run/docs/configuring/healthchecks),
and [container startup dependencies](https://docs.cloud.google.com/run/docs/configuring/services/containers#container-ordering).

## Repeatable local verification

Use Docker and run from the repository root. On an ARM Mac, select amd64 to verify
the same architecture as Cloud Run; Bolt 0.12 also provides Linux ARM64 wheels.

```bash
docker build --platform linux/amd64 -f docker/Dockerfile.proxy-test -t wpp-http2-test .
docker run --rm --platform linux/amd64 wpp-http2-test python tests/integration/test_bolt_ingress.py
docker run --rm --platform linux/amd64 --user 1000:1000 wpp-http2-test python tests/integration/test_shutdown.py
docker network create wpp-http2-tests
docker run -d --name wpp-http2-postgres --network wpp-http2-tests \
  -e POSTGRES_PASSWORD=http2-fixture -e POSTGRES_DB=http2_fixture postgres:16-alpine
docker exec wpp-http2-postgres pg_isready -U postgres
docker run --rm --platform linux/amd64 --user 1000:1000 --network wpp-http2-tests \
  -e WPP_HTTP2_TEST_DATABASE_URL=postgresql://postgres:http2-fixture@wpp-http2-postgres:5432/http2_fixture \
  wpp-http2-test
docker rm -f wpp-http2-postgres
docker network rm wpp-http2-tests
```

Wait until `pg_isready` reports accepting connections before the import test.
The direct API test migrates only the dedicated database supplied in
`WPP_HTTP2_TEST_DATABASE_URL`. Never point that variable at an existing platform
database. Fixtures and API keys are temporary.

The suite uses real production launchers and Nginx templates, trusted local TLS
frontends representing Cloud Run, the exporter `delivery.Send` function, locked
Bolt, and PostgreSQL. The API backend uses a separate loopback port inside the
shared test namespace. Generated ZIP_STORED packages stay large on the wire; the near-limit fixture uses approximately 120 MiB of records and a 1 MiB
manifest, matching the existing expanded-content limits. It includes a full 1 MiB
event timeline, tests rejected package/event/envelope sizes, invalid content and
credentials, and verifies the active Song Catalog is preserved after failures and
retry. HTTP/2 protocol logs confirm the direct API TLS hop.

## Deployed verification

After reviewed deployment, inspect both revisions:

```bash
gcloud run services describe wpp-app --region=us-west1 --format=export
gcloud run services describe wpp-api --region=us-west1 --format=export
curl --http2 --silent --show-error --output /dev/null \
  --write-out '%{http_version} %{http_code}\n' https://api.rccgcm.org/api/v1/docs
```

Only the API ingress port should be named `h2c`; the app uses `http1`. The API
revision must contain exactly an ingress container and the `bolt` backend, with
`run.googleapis.com/container-dependencies` making ingress depend on `bolt`.
Timeouts should remain 600 seconds. Inspect the backend HTTP startup probe on
port 8000 and ingress probe on port 8080, both using `/api/v1/docs`; the app uses
`/health/`. Bolt should have 2 GiB memory, Nginx 256 MiB, and API concurrency 1.
The app and Bolt image should contain no Nginx binary. Probe the returned API
service URL with the same curl options. On an authorized staging instance, deliver
a valid package above 32 MiB and one near the supported limit through the API
URL, then check the completed Catalog Import Run and its song count in Admin.
Use the existing run identity when retrying a transport failure. Rejected oversized,
invalid and unauthorized requests must leave the previous Song Catalog active.

## Windows exporter smoke procedure

Use the installed Catalog Exporter under its configured Windows account with
EasyWorship closed. Follow [the normal first-import procedure](windows-catalog-exporter.md#5-run-and-verify-the-first-import)
using the API URL and protected key. Capture exit code 0 and the completed
Catalog Import Run identity, song count, and exporter/importer timeline. When the
actual library produces a package above 32 MiB, confirm its size and completion.
For size fixtures and deliberate failure/retry checks, use an authorized staging
instance rather than replacing the production Song Catalog with generated content.

The local fixtures emulate Cloud Run's TLS frontends. They do not prove a deployed
revision's configuration or Windows TLS negotiation; perform these smoke checks
after rollout. Local verification results and measured memory are recorded in the PR.
