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

Supabase's `rls_enabled_no_policy` advisor notice is informational: RLS without
policies rejects row access by ordinary roles. Explicit restrictive
`deny_supabase_api` policies reject every command for `anon` and `authenticated`,
so the advisor can see the intended boundary. Table and column privileges remain
revoked. The application's database connection continues to use its existing
privileged role; browser and Integration Client authorization stays in Django and
Bolt. See [Supabase's advisor guidance](https://github.com/supabase/splinter/blob/main/docs/0008_rls_enabled_no_policy.md).

The `unaccent` and `pg_trgm` extensions live in the infrastructure schema
`extensions`, outside the application schema exposed by the Data API. PostgreSQL
connections use `search_path=public,extensions` so app tables remain in `public`
and Django's search lookups can resolve extension operators. Production connection
paths must also include `extensions`. Move the extensions in place to preserve search
indexes and dictionary mappings. See [Supabase's extension guidance](https://github.com/supabase/splinter/blob/main/docs/0014_extension_in_public.md).
