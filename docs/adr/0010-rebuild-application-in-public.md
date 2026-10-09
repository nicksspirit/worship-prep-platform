# ADR-0010: Rebuild the Application in Public

## Status

Accepted. Supersedes ADR-0008 and the schema-cutover identity procedure in ADR-0009.

## Date

2026-10-09

## Context

The operator chose a fresh application database based on commit `2632475`, with
`public` as the only application schema. The live database contained 28 legacy
Django tables in `public` and 29 current application tables in `wpp_app`.
Preserving those separate application histories is no longer required.

## Decision

Create and retain a private database backup before removing application data.
Remove the inventoried legacy Django tables from `public`, rebuild the current
application there, verify it, then remove `wpp_app`. Preserve Supabase-managed
schemas, Storage files, and shared PostgreSQL extensions. Do not drop `public`.

Regenerate first-party Django migrations from the current models. Keep third-party
migrations intact. Retain the custom catalog text-search configuration, extensions,
indexes, row-level security, and Supabase API privilege revocations. Reapply the
new migration graph to the empty database rather than faking migration history.
Both runtime and migration connections explicitly select `public`.

## Consequences

The reset removes application users, Google identity links, sessions, invitations,
API keys, catalog entries, rights records, and import history. Administrator setup
and catalog imports occur after the verified reset. Django creates its required
framework records during migrations, so a fresh database is not entirely row-free.

The new migration graph requires a fresh database; it is not an incremental upgrade
for databases with the previous migration history. Keep the private backup and
operational record outside version control. Application tables remain inaccessible
to Supabase's `anon` and `authenticated` roles; the product uses Django and Bolt.
