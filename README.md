# Worship Prep Platform

Worship Prep Platform is becoming a public, read-only Song Catalog sourced from the
church's EasyWorship Library. The EasyWorship Library remains authoritative; the
platform will ingest immutable snapshots without writing back to the source.

This stacked branch contains the greenfield foundation plus the portable
[Catalog Exporter](exporter/) and versioned
[Catalog Import Package contract](contracts/catalog-import/v1/). Catalog importing,
search, the read interface, public discovery, and administration arrive in later
stacked pull requests tracked by GitHub issue #21.

## Quick Start

Install Python and JavaScript dependencies, then run the Django application:

```bash
uv sync --group local
npm ci --legacy-peer-deps
poe migrate
poe dev
```

The default local database is SQLite for interactive development. The automated test
suite boots a disposable PostgreSQL 16 database through Testcontainers, so Docker must
be running:

```bash
poe test
```

## Foundation Modules

- `apps.accounts`: custom user identity, invitation requests, sign-in, and invitation
  administration.
- `apps.api_keys`: hashed Integration Client credentials, target Song Catalog scopes,
  rotation, revocation, and administration.
- `apps.catalog`: the Song Catalog module seam for subsequent slices.
- `apps.common`: shared Django infrastructure, model utilities, middleware, and
  Reactivated context.

The archived schedule, content-submission, and inbound-song product is available at
tag `archive/pre-song-catalog-pivot`; it is intentionally absent from the active
runtime and migrations.

## HTTP Architecture

- Django Bolt serves product and machine-facing JSON APIs from each app's `api.py`.
- Django views and Reactivated templates serve rendered product UI.
- Transport-neutral services hold reusable domain and application behavior.
- Django's standard stack continues to own operational and framework routes such as
  health/readiness, admin, invitations, and authentication callbacks.

See [ADR-0004](docs/adr/0004-separate-json-and-rendered-transports.md) for the boundary,
rationale, and review rule.

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
