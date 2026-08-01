# ADR-0008: Isolate the Greenfield Catalog Production Schema

## Status

Accepted

## Date

2026-08-01

## Context

ADR-0001 deliberately replaces the schedule-oriented product with a greenfield Song
Catalog and requires an empty PostgreSQL schema. The existing production Supabase
database still contains the pre-pivot migration ledger, accounts, schedules, and songs.
Applying the new migration graph to that `public` schema fails because the old
`account.0001_initial` is recorded before the new `accounts.0001_initial` dependency.

Dropping `public` would satisfy the greenfield requirement but would irreversibly remove
the legacy production data. Faking migrations or editing the old ledger would couple the
new product to a history ADR-0001 intentionally archived.

## Decision

Run the production Song Catalog in the dedicated `wpp_catalog_v1` PostgreSQL schema.
Both `DATABASE_URL` and `DIRECT_URL` put `wpp_catalog_v1` first in `search_path`, with
`public` second for shared PostgreSQL extensions and the catalog text-search
configuration. The URL option must encode its space as `%20`, not `+`:

```text
options=-c%20search_path%3Dwpp_catalog_v1%2Cpublic
```

Initialize `wpp_catalog_v1.django_migrations` before the first migration so it shadows
the preserved `public.django_migrations` ledger. Migrations that harden application
tables must qualify them using `current_schema()` rather than assuming `public`.
Objects intentionally shared across schemas, such as `public.wpp_simple_unaccent`,
remain explicitly qualified.

## Alternatives Considered

### Drop and recreate the public schema

Rejected because the pivot does not require destroying the archived product's data, and
the deployment can meet the empty-schema requirement without that loss.

### Rewrite or fake the legacy migration history

Rejected because matching two unrelated greenfield histories would be fragile and
would leave the new runtime dependent on tables outside its domain.

### Create a separate Supabase project

Rejected for this deployment because a separate schema provides the required isolation
while retaining the existing database, storage credentials, and operational footprint.

## Consequences

- Legacy production tables and their migration ledger remain intact in `public`.
- Song Catalog services, migrations, and administration use only `wpp_catalog_v1` for
  Django-owned tables.
- New deployment tooling and database-secret rotations must preserve the encoded
  `search_path` option on both database URLs.
- Migration tests must cover non-`public` schemas so hard-coded qualifiers do not recur.
- Supabase API exposure remains limited because the custom schema is not added to the
  exposed PostgREST schemas.
