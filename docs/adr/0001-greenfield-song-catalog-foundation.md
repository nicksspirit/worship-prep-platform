# ADR-0001: Establish a Greenfield Song Catalog Foundation

## Status

Accepted

## Date

2026-08-01

## Context

The former product centered on service schedules, content submissions, and inbound
song intake. The approved direction in GitHub issues #20 and #21 is a public,
read-only Song Catalog whose source of truth is the church's EasyWorship Library.
Keeping the legacy runtime or migration history active would make later snapshot,
rights, search, and import work depend on concepts that are explicitly out of scope.

The pivot must retain operational infrastructure that still fits the target product:
custom account identity, invitation-only administration, Unfold, Reactivated,
health/readiness checks, shared model utilities, PostgreSQL, private object storage,
Django-Bolt, static serving, and Cloud Run deployment.

## Decision

Archive commit `32a56db` as `archive/pre-song-catalog-pivot` and build the pivot on
`codex/pivot/song-catalog`.

Use four top-level Django modules with narrow interfaces:

- `accounts` owns users, invitation requests, sign-in, and invitation administration.
- `api_keys` owns Integration Client credential lifecycle and Song Catalog scopes.
- `catalog` owns the Song Catalog domain introduced by subsequent slices.
- `common` owns shared infrastructure with no product-specific schedule or intake
  behavior.

Delete the schedule, content-submission, legacy song, n8n, runtime route, UI, test, and
migration surfaces. Recreate the schema from fresh initial migrations; no legacy rows
are migrated into the Song Catalog.

## Alternatives Considered

### Evolve the legacy apps in place

Rejected because schedule and intake concepts would remain embedded in model labels,
routes, migrations, tests, and administration despite being outside the target
product.

### Keep compatibility routes and migrations temporarily

Rejected because the approved pivot explicitly chooses a greenfield runtime and
database baseline. Git history and the archival tag provide the recovery path.

## Consequences

- A deployment of this foundation requires an empty PostgreSQL schema.
- The active product has no schedule, content-submission, or inbound-song routes.
- Later pull requests can add package, import, search, and presentation behavior at
  the `catalog` seam without compatibility constraints.
- Pre-pivot behavior remains recoverable from the immutable archival tag.
