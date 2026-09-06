# Supabase Cutover Runbook

This is the non-secret template for the one-time `wpp_catalog_v1` to `wpp_app`
cutover. It implements [ADR-0008](adr/0008-isolate-greenfield-production-schema.md),
[ADR-0009](adr/0009-recreate-catalog-superuser-google-identity.md), and
[ADR-0010](adr/0010-supabase-cutover-validation-and-rollback-gates.md).

Do not run it from CI or a Cloud Run job. The production operator runs each command
manually during a maintenance window. The script is read-only by default; all schema
or cleanup changes need `--apply` and a local approval.

## Local evidence

Keep per-cutover values only under the gitignored `.local/supabase-cutover/` directory:

```bash
./deploy/supabase-cutover.sh init
```

This creates a mode-600 `cutover.env` and `cleanup.sql`. Do not place `DIRECT_URL`,
passwords, OAuth data, tokens, or secrets there. Export `DIRECT_URL` in the active
operator shell instead. The record holds the preflight counts, Google UID, approval,
and reviewed cleanup list. Delete it manually after cleanup or when the maximum
seven-day observation window ends.

## 1. Preflight and rehearsal

Load the direct Supabase PostgreSQL URL from Google Secret Manager into the current
shell, then capture the output in an operator-controlled local file. This requires an
authenticated `gcloud` session with access to the `DIRECT_URL` secret:

```bash
export GCP_PROJECT_ID="${GCP_PROJECT_ID:-worship-prep-portal}"
export DIRECT_URL="$(gcloud secrets versions access latest \
  --secret=DIRECT_URL \
  --project="$GCP_PROJECT_ID")"

case "$DIRECT_URL" in
  postgresql://*|postgres://*) ;;
  *) echo "DIRECT_URL is missing or not a PostgreSQL URL" >&2; exit 1 ;;
esac

./deploy/supabase-cutover.sh preflight | tee .local/supabase-cutover/preflight.txt
```

Do not echo the variable or write it to `.local/`; it remains only in the current
shell. A bare value such as `postgres` makes `psql` fall back to a local Unix socket
and is not a usable Supabase connection.

Review the output against the approved inventory: `wpp_catalog_v1` contains the
catalog; `public` contains the legacy objects; extensions and
`public.wpp_simple_unaccent` are identified; and no unexpected cross-schema dependency
exists. Fill `cutover.env` from the approved baseline. Its recorded counts begin at
2,283 songs, 2,283 rights rows, one snapshot, one activation, three import runs, and
20 import events.

Restore the supplied dump into an isolated disposable database or schema and run the
same preflight and validation commands there. Confirm the schema owner can move
`unaccent` and `pg_trgm` to `public`. A failed rehearsal stops the cutover.

## 2. Rename and runtime configuration

After separately recording approval, set `CUTOVER_APPROVED=YES` in the local record
and run:

```bash
./deploy/supabase-cutover.sh rename --apply
```

It atomically renames `wpp_catalog_v1` to `wpp_app` and moves the two extensions to
`public`.

### Provision the application role

Run the following as the current privileged schema owner, while the maintenance window
is still active. It is idempotent for the role and transfers ownership only of objects
inside `wpp_app`; it does not reassign or alter Supabase-managed `public` objects.

```bash
if ! psql "$DIRECT_URL" -X -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wpp_prod_user') THEN
    RAISE EXCEPTION
      'wpp_prod_user already exists; refusing to alter an existing role'
      USING HINT =
        'Inspect the existing role and resolve it explicitly before rerunning this block.';
  END IF;

  CREATE ROLE wpp_prod_user LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
END
$$;

ALTER SCHEMA wpp_app OWNER TO wpp_prod_user;

DO $$
DECLARE
  object_record record;
  object_kind text;
BEGIN
  FOR object_record IN
    SELECT class.relkind, namespace.nspname, class.relname
      FROM pg_class class
      JOIN pg_namespace namespace ON namespace.oid = class.relnamespace
     WHERE namespace.nspname = 'wpp_app'
       AND class.relkind IN ('r', 'p', 'S', 'v', 'm')
  LOOP
    object_kind := CASE object_record.relkind
      WHEN 'S' THEN 'SEQUENCE'
      WHEN 'v' THEN 'VIEW'
      WHEN 'm' THEN 'MATERIALIZED VIEW'
      ELSE 'TABLE'
    END;
    EXECUTE format(
      'ALTER %s %I.%I OWNER TO wpp_prod_user',
      object_kind,
      object_record.nspname,
      object_record.relname
    );
  END LOOP;
END
$$;

REVOKE ALL ON SCHEMA wpp_app FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON ALL TABLES IN SCHEMA wpp_app FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA wpp_app FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE, CREATE ON SCHEMA wpp_app TO wpp_prod_user;
GRANT USAGE, CREATE ON SCHEMA public TO wpp_prod_user;
ALTER DEFAULT PRIVILEGES FOR ROLE wpp_prod_user IN SCHEMA wpp_app
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE wpp_prod_user IN SCHEMA wpp_app
  REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE wpp_prod_user IN SCHEMA wpp_app
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

COMMIT;
SQL
then
  echo "Role provisioning failed; password was not changed." >&2
  exit 1
fi

# Generate a 20-character password using Python's secrets module. Store it in the
# approved password manager, then enter it at the prompt below. Do not export it.
./deploy/supabase-cutover.sh generate-password

# Prompts twice; the password is never stored in the shell, a file, or the command line.
psql "$DIRECT_URL" -X -v ON_ERROR_STOP=1 -c '\password wpp_prod_user'
```

If the `ALTER ... OWNER` statements fail, stop. The connected role lacks the authority
to transfer ownership; do not substitute broad `REASSIGN OWNED` or alter `public` to
work around it. The role's search path is controlled by the application connection
URLs, not `ALTER ROLE`.

Immediately change both `DATABASE_URL` and `DIRECT_URL` to:

```text
options=-c%20search_path%3Dwpp_app%2Cpublic
```

Restart the application and migration services. Do not change Supabase exposed schemas.

## 3. Validation gates

Run database validation:

```bash
./deploy/supabase-cutover.sh validate | tee .local/supabase-cutover/validation.txt
```

All expected counts and schema/security checks must pass. Then separately confirm:

```bash
curl -fsSL https://<APP_HOST>/health/
curl -fsSL https://<APP_HOST>/ready/
curl -fsSL https://<API_HOST>/api/v1/health
curl -fsSL https://<API_HOST>/api/v1/ready
```

Follow ADR-0009 to recreate the superuser and Google identity. Confirm password login
to `/admin/` and incognito Google sign-in both reach that user, with exactly one Google
social account and no social token. Keep the legacy state while checks fail or until a
separately approved cleanup is ready.

## 4. Cleanup or recovery

Cleanup is eligible as soon as all gates pass; seven days is only the maximum evidence
window. Build `.local/supabase-cutover/cleanup.sql` from the reviewed 28-table
allowlist and owned sequences. Each statement must be exactly one of:

```sql
DROP TABLE public.<lowercase_identifier>;
DROP SEQUENCE public.<lowercase_identifier>;
```

Run the dependency check and record its output locally:

```bash
./deploy/supabase-cutover.sh dependencies | tee .local/supabase-cutover/dependencies.txt
```

After review, set both `DEPENDENCY_REVIEWED=YES` and `CLEANUP_APPROVED=YES`, then run:

```bash
./deploy/supabase-cutover.sh cleanup --apply
```

The command rejects `CASCADE`, extensions, functions, and protected text-search
objects. It runs the reviewed list in one transaction. Do not use it to drop a schema
or any Supabase-managed object.

Before cleanup, recover by restoring the previous search path and running:

```bash
./deploy/supabase-cutover.sh rollback --apply
```

After cleanup, never restore the full dump over live `public`. Restore it first into
an isolated recovery environment/schema, validate it, and obtain a separate approval
for any recovery action.
