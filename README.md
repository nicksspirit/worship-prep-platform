# Worship Prep Platform

Worship Prep Platform is becoming a public, read-only Song Catalog sourced from the
church's EasyWorship Library. The EasyWorship Library remains authoritative; the
platform will ingest immutable snapshots without writing back to the source.

This stacked branch contains the complete six-slice Song Catalog pivot: the greenfield
foundation, the portable
[Catalog Exporter](exporter/), the versioned
[Catalog Import Package contract](contracts/catalog-import/v1/), immutable Catalog
Importer snapshots, PostgreSQL search, and the Integration Client read API. Public
Song Catalog search, Song Detail, and Projection Preview are also available without an
account. Audited Catalog Administration, Windows delivery and scheduling, recovery,
rollback, alerts, and automated release gates complete the final slice tracked by
GitHub issue #21.

## Quick Start

Install Python and JavaScript dependencies, then run the Django application:

```bash
uv sync --group local
npm ci --legacy-peer-deps
poe migrate
poe dev
```

Catalog imports and search require PostgreSQL; configure `DATABASE_URL` before applying
migrations or running the API locally. Local automated tests boot a disposable
PostgreSQL 16 database through Testcontainers, so Docker must be running. GitHub Actions
uses its native PostgreSQL service container instead.

```bash
poe test
```

## Foundation Modules

- `apps.accounts`: custom user identity, invitation requests, sign-in, and invitation
  administration.
- `apps.api_keys`: hashed Integration Client credentials, target Song Catalog scopes,
  rotation, revocation, database-coordinated rate limits, and administration.
- `apps.catalog`: immutable Song Catalog snapshots, import processing, search, signed
  continuations, rights-aware reads, audited Lyrics Rights Provenance, recovery,
  rollback, and failure alerts.
- `apps.common`: shared Django infrastructure, model utilities, middleware, and
  Reactivated context.

The archived schedule, content-submission, and inbound-song product is available at
tag `archive/pre-song-catalog-pivot`; it is intentionally absent from the active
runtime and migrations.

## HTTP Architecture

- Django Bolt serves product and machine-facing JSON APIs from each app's `api.py`.
- Each app defines its msgspec-backed Django Bolt request and response types in
  `schema.py`; handlers construct those contracts rather than ad hoc dictionaries.
- Django views and Reactivated templates serve rendered product UI.
- Transport-neutral services hold reusable domain and application behavior.
- Django's standard stack continues to own operational and framework routes such as
  health/readiness, admin, invitations, and authentication callbacks.

See [ADR-0004](docs/adr/0004-separate-json-and-rendered-transports.md) for the boundary,
rationale, and review rule.

## Integration Client API

The versioned API is served under `/api/v1/` with Bearer-key scopes:

- `GET /api/v1/catalog/search` requires `catalog.search`; Lyrics mode also requires
  `catalog.lyrics.read`.
- `GET /api/v1/catalog/songs/{song_uid}` requires `catalog.song.read`.
- `GET /api/v1/catalog/songs/{song_uid}/lyrics` requires `catalog.lyrics.read`, plus
  `catalog.lyrics.restricted` for restricted lyrics.
- `POST /api/v1/catalog/imports` requires `catalog.import`; the Catalog Exporter may
  attach its durable event timeline and scheduled/manual trigger identity.

Machine-readable OpenAPI is available at `/api/v1/docs/openapi.json`. Local development
serves Swagger UI at `/api/v1/docs`; production serves ReDoc at the same entry point.
Search continuations are opaque server-provided URLs and expire after 24 hours.

## Public Song Catalog

The root route serves the public Song Catalog through Django and Reactivated. Visitors
can search titles or lyrics, follow snapshot-pinned result continuations, and open
rights-aware Song Detail pages. Approved and unknown entries include structured lyrics
and an accessible approximate 16:9 Projection Preview; restricted entries remain
metadata-only. Empty search input shows guidance rather than dumping the catalog.

Rendered pages reuse the transport-neutral catalog search/read services directly. They
do not call the Integration Client API, and restricted lyric fields are removed before
the Reactivated props are serialized. See
[ADR-0006](docs/adr/0006-public-catalog-presentation.md).

## Catalog Administration and Automation

Invited Catalog Administrators can inspect Catalog Import Runs, exporter/importer event
timelines, retained snapshots, and Lyrics Rights Provenance. Superusers alone change
rights with policy-valid evidence, recover a retained failed package, roll back the
active pointer, manage invitations, and issue, rotate, or revoke Integration Client
keys.

The stable Windows installer is served at `/static/install-catalog-exporter.ps1`. It
verifies the latest `exporter/v*` binary, protects the import key with current-user
DPAPI, and schedules the Catalog Exporter weekly at 3:00 AM America/Los_Angeles with one
retry after 30 minutes. See [ADR-0007](docs/adr/0007-audit-and-automate-catalog-operations.md)
and the [Catalog Exporter guide](exporter/README.md).

## Commands

Project commands are Poe aliases over Django management commands:

```bash
poe --help
poe manage --help
poe makemig
poe migrate
poe test
```

See [deployment documentation](docs/deploy.md) for Cloud Run, Supabase PostgreSQL,
and private Supabase Object Storage setup. Architectural decisions live in
`docs/adr/`; the approved domain vocabulary and product contract are in issue #21.
