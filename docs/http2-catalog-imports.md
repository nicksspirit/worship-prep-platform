# HTTP/2 Catalog Imports

The exporter uses Go's HTTPS transport with automatic HTTP/2 negotiation. The
platform path is exporter → Cloud Run app TLS frontend → app Nginx h2c → verified
TLS HTTP/2 to the Bolt service → Cloud Run Bolt TLS frontend → Bolt Nginx h2c →
local Bolt HTTP/1. Django pages continue to use local Gunicorn. Both services keep
600-second request timeouts and public access with application API-key scopes.

Nginx 1.30.5 is installed from its official signed stable Debian repository. The
build verifies the documented signing-key fingerprint and the HTTP/2 module.
Both Cloud Build deployment commands set `--use-http2`. Django Bolt remains at the
locked 0.6.0 version; its server does not accept h2c itself.

Both Nginx ingress configurations render the same structured logging fragment.
They preserve validated request and Cloud trace identities across the proxy chain,
generate bounded identities for direct Bolt requests, and omit query strings and
credentials from completion logs.

The API service uses 2 GiB memory and concurrency 1. In the local Linux full-chain
test, a valid 126,479,404-byte package plus 1,048,576 event bytes caused the Bolt
process to peak at 679,284 KiB RSS (about 664 MiB). This exceeds the previous
512 MiB default. Cloud Run also charges its writable in-memory filesystem against
instance memory, including temporary upload files; 2 GiB gives room for those
files and parsed records. Concurrency 1 prevents simultaneous large imports from
multiplying that memory use. Django service resources are unchanged.

Runtime references: [Cloud Run HTTP/2](https://cloud.google.com/run/docs/configuring/http2),
[Cloud Run memory and writable filesystem](https://cloud.google.com/run/docs/configuring/services/memory-limits),
and [Nginx HTTP/2 upstream support](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_http_version).

## Repeatable local verification

Use Docker and run from the repository root. On an ARM Mac, select amd64 because
the locked Bolt release ships its Linux wheel only for x86_64.

```bash
docker build --platform linux/amd64 -f docker/Dockerfile.proxy-test -t wpp-http2-test .
docker run --rm --platform linux/amd64 wpp-http2-test python tests/integration/test_api_proxy.py
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
The full-chain test migrates only the dedicated database supplied in
`WPP_HTTP2_TEST_DATABASE_URL`. Never point that variable at an existing platform
database. Fixtures and API keys are temporary.

The suite uses real production launchers and Nginx templates, trusted local TLS
frontends representing Cloud Run, the exporter `delivery.Send` function, locked
Bolt, and PostgreSQL. The two local container backends use separate loopback ports
inside the shared test namespace. Generated ZIP_STORED packages stay large on the
wire; the near-limit fixture uses approximately 120 MiB of records and a 1 MiB
manifest, matching the existing expanded-content limits. It includes a full 1 MiB
event timeline, tests rejected package/event/envelope sizes, invalid content and
credentials, and verifies the active Song Catalog is preserved after failures and
retry. HTTP/2 protocol logs confirm both TLS service hops.

## Deployed verification

After reviewed deployment, inspect both revisions:

```bash
gcloud run services describe wpp-app --region=us-west1 --format=export
gcloud run services describe wpp-api --region=us-west1 --format=export
curl --http2 --silent --show-error --output /dev/null \
  --write-out '%{http_version} %{http_code}\n' https://app.rccgcm.org/api/v1/docs
```

Both revision container ports should be named `h2c`; timeouts should remain 600
seconds. The Bolt revision should have 2 GiB memory and concurrency 1. Confirm the
image has the pinned Nginx version. Probe the returned Bolt
service URL with the same curl options. On an authorized staging instance, deliver
a valid package above 32 MiB and one near the supported limit through the platform
URL, then check the completed Catalog Import Run and its song count in Admin.
Use the existing run identity when retrying a transport failure. Rejected oversized,
invalid and unauthorized requests must leave the previous Song Catalog active.

## Windows exporter smoke procedure

Use the installed Catalog Exporter under its configured Windows account with
EasyWorship closed. Follow [the normal first-import procedure](windows-catalog-exporter.md#5-run-and-verify-the-first-import)
using the same platform URL and protected key. Capture exit code 0 and the completed
Catalog Import Run identity, song count, and exporter/importer timeline. When the
actual library produces a package above 32 MiB, confirm its size and completion.
For size fixtures and deliberate failure/retry checks, use an authorized staging
instance rather than replacing the production Song Catalog with generated content.

The local fixtures emulate Cloud Run's TLS frontends. They do not prove a deployed
revision's configuration or Windows TLS negotiation; perform these smoke checks
after rollout. Local verification results and measured memory are recorded in the PR.
