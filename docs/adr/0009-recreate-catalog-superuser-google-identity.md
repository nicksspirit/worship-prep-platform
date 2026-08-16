# ADR-0009: Recreate the Catalog Superuser and Google Identity

## Status

Accepted

## Date

2026-08-16

## Context

The production Song Catalog is being promoted from `wpp_catalog_v1` to `wpp_app` as
described by [ADR-0008](0008-isolate-greenfield-production-schema.md). The imported
catalog is present in the backup and the new schema, but the new schema has no
application authentication rows. The legacy `public` schema contains the existing
operator identity.

The cutover starts the application identity state from scratch. The operator selects
the target email address before the cutover. The backup and legacy tables are
available during preflight, but the procedure must not depend on them after cleanup.
The operator must capture the selected user's email, names, and stable Google
provider UID in an approved operational cutover record before deleting that data.
OAuth tokens, refresh tokens, client secrets, and legacy `extra_data` JSON are not
migration inputs.

## Decision

Create the new `apps.accounts.User` through Django's interactive
`poe manage createsuperuser` command after the `wpp_app` schema is active. The
operator chooses the password at the prompts; the password is not placed in an
environment variable, command line, repository, issue, or log. The command creates
the account with `is_staff=True` and `is_superuser=True`.

Capture the legacy user's `first_name` and `last_name` during preflight. If either
value is blank, capture the corresponding verified Google profile value. Use these
captured values when creating the new user. Do not query the legacy tables after
cleanup.

Create a fresh `SocialAccount` row in `wpp_app` with:

- `provider="google"`
- the legacy Google `uid`
- the new `User` foreign key
- `extra_data={}`

Do not create a `SocialToken` row and do not copy the legacy social account's
`extra_data`. The Google OAuth client remains configured through the existing
`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` deployment secrets. The stable provider
UID is the identity link; the verified Google email is used for the login and
post-cutover verification.

Remove the reviewed legacy authentication tables/rows only after the new catalog,
admin access, and Google login have all passed validation. The cleanup is part of the
archive-first public-schema cleanup plan, not an automatic side effect of creating the
new user.

## Procedure

Set the target email in the shell. Do not set a password variable:

```bash
export TARGET_EMAIL='<TARGET_EMAIL>'
```

Run these checks against the promoted database before creating the user:

```bash
poe manage dbshell -- -c "SELECT current_schema(), current_setting('search_path');"
```

The result must show `wpp_app` as the first schema. Read the legacy identity from the
backup or the still-present `public` tables without selecting OAuth payloads. The
legacy table names below are the names recorded by the preflight inventory; stop if
the inventory differs:

```bash
psql "$DIRECT_URL" -X -v ON_ERROR_STOP=1 \
  -v target_email="$TARGET_EMAIL" \
  -c \
  "SELECT u.email, u.first_name, u.last_name, s.provider, s.uid
     FROM public.account_user AS u
     JOIN public.socialaccount_socialaccount AS s ON s.user_id = u.id
    WHERE lower(u.email) = lower(:'target_email')
      AND s.provider = 'google';"
```

Confirm that the result has exactly one Google UID. Before cleanup, record the target
email, first name, last name, provider, and UID in the approved operational cutover
record. Keep the record outside the repository and issue tracker. Retain it until the
validation and rollback window ends. Do not print or copy `extra_data`,
`socialaccount_socialtoken`, client secrets, or access/refresh tokens.

Set `TARGET_GOOGLE_UID` from that cutover record. The cutover record, not the backup,
must supply the values after cleanup.

Create the new superuser interactively. Replace the two name placeholders with the
values in the cutover record:

```bash
poe manage createsuperuser \
  --email "$TARGET_EMAIL" \
  --first_name "<FIRST_NAME>" \
  --last_name "<LAST_NAME>"
```

Answer the password prompts yourself. Do not use `--noinput` or
`DJANGO_SUPERUSER_PASSWORD` for this cutover.

Verify the new user's flags without printing the password:

```bash
poe manage shell -c "import os; from apps.accounts.models import User; u=User.objects.get(email__iexact=os.environ['TARGET_EMAIL']); assert u.is_active and u.is_staff and u.is_superuser; print({'id': u.pk, 'email': u.email, 'first_name': u.first_name, 'last_name': u.last_name, 'has_usable_password': u.has_usable_password()})"
```

Create the Google identity link only after the schema preflight above confirms that
`wpp_app` is first in the search path. The command uses only the UID in the cutover
record, creates an empty `extra_data` object, and never creates a `SocialToken`. Its
guard fails rather than reassigning an existing provider identity to a different user.
A retry with the correct link verifies that link without creating a duplicate:

```bash
export TARGET_GOOGLE_UID='<GOOGLE_UID_FROM_PREFLIGHT>'

poe manage link_google_identity \
  --email "$TARGET_EMAIL" \
  --uid "$TARGET_GOOGLE_UID"
```

Do not replace the empty profile metadata with the legacy JSON.

## Validation gate

Before removing legacy authentication state:

1. Confirm the active catalog has the expected snapshot and entry counts.
2. Open `/admin/` and sign in with the recreated password; confirm the account can
   access the catalog administration.
3. In an incognito browser, start Google sign-in from the deployed app URL. Use the
   selected Google account.
4. Confirm the callback completes, the resulting session is the recreated user, and
   the user remains `is_staff=True` and `is_superuser=True`.
5. Confirm exactly one `google` `SocialAccount` exists for the user and no
   `SocialToken` was created by the rebuild.

Only after all five checks pass may the operator execute the reviewed legacy cleanup
allowlist. If a check fails before cleanup, stop and use the retained rollback
artifacts. If cleanup has started, follow the approved rollback procedure. Do not
assume that deleted backup or legacy data remains available.

## Alternatives Considered

### Copy the legacy user and social-account rows

Rejected because those rows belong to the legacy schema and may carry profile payloads
or token-related data that is unnecessary for the new application. Recreating the
minimal identity state makes the schema boundary explicit.

### Rely on email auto-linking without a precreated SocialAccount

Rejected because the cutover requirement is to preserve the known Google identity
explicitly. The stable provider UID in the cutover record gives a deterministic link
and avoids depending on a first-login account matching path.

### Create the account non-interactively with a password environment variable

Rejected because it exposes a long-lived credential to process or deployment state.
The interactive Django command gives the operator control while retaining a password
for recovery.

## Consequences

- The new superuser has an operator-selected password and a deterministic Google
  identity link.
- No OAuth token or secret is migrated into `wpp_app`.
- Legacy authentication state remains available only until the post-login validation
  gate and reviewed cleanup.
- The cutover operator must keep the cutover record outside the repository and issue
  tracker until the validation and rollback window ends.
- The procedure remains executable after the backup and legacy tables are deleted.
