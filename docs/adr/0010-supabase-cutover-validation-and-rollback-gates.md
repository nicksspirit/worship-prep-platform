# ADR-0010: Gate Supabase Cutover Validation and Recovery

## Status

Accepted

## Date

2026-08-16

## Context

The Song Catalog will move from `wpp_catalog_v1` to `wpp_app` while `public`
continues to hold Supabase shared objects and the temporarily retained legacy Django
state. The schema rename itself is reversible before legacy cleanup; deleting reviewed
legacy objects is not. The cutover therefore needs evidence-based gates, a local
operator record, and recovery paths that do not overwrite Supabase-managed objects.

## Decision

Use a fail-closed four-stage cutover:

1. Capture the non-secret baseline and complete a disposable restore rehearsal before
   mutation.
2. Perform the schema and role cutover during a maintenance window.
3. Run data, security, health, password-admin, and Google-login validation gates.
4. Permit, but never automatically run, legacy cleanup only after a separate manual
   approval.

The operator stores the cutover record in the gitignored `.local/` directory. It is
not a database artifact or issue-tracker record. The record holds the approved
non-secret baseline, validation outcomes, exact reviewed 28-table allowlist and owned
sequences, approval, and timestamps. It remains until legacy cleanup completes or the
seven-day maximum observation window ends, then is manually deleted.

Legacy cleanup may occur immediately after every gate passes; seven days is an upper
bound, not a mandatory delay. Before cleanup, rerun dependency inventory and abort if
the object set differs from the reviewed allowlist or touches `public` extensions,
`public.wpp_simple_unaccent`, or Supabase-managed objects. Run the resulting cleanup
as one manually invoked transaction.

Before cleanup, rollback reverses the schema rename and runtime search path in a
maintenance window. After cleanup, never restore the complete dump directly over live
`public`; restore it first into an isolated recovery environment or schema, validate
it, and obtain a separate recovery approval.

The validation gates require:

- Baseline counts in `wpp_app` to match the local preflight record, including the
  catalog's 2,283 entries and rights rows, one snapshot, one activation, three import
  runs, and 20 import events; Django's migration ledger and catalog/text-search smoke
  tests must also pass.
- `wpp_app` to remain absent from PostgREST exposure, with RLS enabled and no policies;
  `anon`, `authenticated`, and `service_role` must have no access, while `wpp_prod_user`
  operates with `wpp_app,public` as its search path.
- Web and API health checks, password access to `/admin/`, and incognito Google login
  to the recreated superuser to pass. Exactly one Google `SocialAccount` must exist and
  no `SocialToken` may be created.

## Alternatives Considered

### Fixed seven-day retention before cleanup

Rejected because it delays an already validated cutover without improving safety. The
same duration remains a maximum window for rollback evidence.

### Direct full-dump restoration to live public

Rejected because it risks overwriting shared Supabase objects and obscures recovery
scope.

### Automatic cleanup after validation

Rejected because the legacy-table boundary is destructive and must receive an explicit
human approval.

## Consequences

- An operator-facing, fail-closed SQL script and runbook are required before the map
  can be closed.
- No destructive database work is performed by the plan itself.
- The local record contains operational evidence only while it is needed for rollback
  and approval.
