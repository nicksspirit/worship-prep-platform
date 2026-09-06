#!/usr/bin/env bash
# Produce evidence for, or manually apply, the one-time Supabase schema cutover.
#
# This script deliberately never reads a database URL from .local. Export DIRECT_URL
# in the operator shell and keep the non-secret, per-cutover values in the local record.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_DIR="${SUPABASE_CUTOVER_LOCAL_DIR:-${ROOT}/.local/supabase-cutover}"
RECORD="${LOCAL_DIR}/cutover.env"
CLEANUP_SQL="${LOCAL_DIR}/cleanup.sql"
MODE="preflight"
APPLY=false

usage() {
  cat <<'EOF'
Usage: deploy/supabase-cutover.sh [generate-password|init|preflight|validate|dependencies|rename|rollback|cleanup] [--apply]

Commands default to read-only preflight. rename, rollback, and cleanup refuse to
run unless --apply is supplied and the local record contains the matching approval.

Export DIRECT_URL in the operator shell. Never put it in .local/cutover.env.
EOF
}

if [[ $# -gt 0 && "$1" != "--apply" ]]; then
  MODE="$1"
  shift
fi
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=true
  shift
fi
if [[ $# -ne 0 ]]; then
  usage >&2
  exit 2
fi

require_psql() {
  command -v psql >/dev/null 2>&1 || {
    echo "psql is required." >&2
    exit 1
  }
}

require_direct_url() {
  : "${DIRECT_URL:?Export DIRECT_URL in the operator shell.}"
}

load_record() {
  [[ -f "$RECORD" ]] || {
    echo "Missing ${RECORD}. Run: $0 init" >&2
    exit 1
  }
  # The record is operator-owned and gitignored. It must contain only shell-safe,
  # non-secret values; DIRECT_URL is intentionally rejected below.
  # shellcheck disable=SC1090
  source "$RECORD"
  [[ -z "${DIRECT_URL_IN_RECORD:-}" ]] || {
    echo "Remove DIRECT_URL_IN_RECORD; credentials must stay in the shell." >&2
    exit 1
  }
  : "${EXPECTED_CATALOG_SONGS:?Set EXPECTED_CATALOG_SONGS in ${RECORD}.}"
  : "${EXPECTED_RIGHTS_ROWS:?Set EXPECTED_RIGHTS_ROWS in ${RECORD}.}"
  : "${EXPECTED_SNAPSHOTS:?Set EXPECTED_SNAPSHOTS in ${RECORD}.}"
  : "${EXPECTED_ACTIVATIONS:?Set EXPECTED_ACTIVATIONS in ${RECORD}.}"
  : "${EXPECTED_IMPORT_RUNS:?Set EXPECTED_IMPORT_RUNS in ${RECORD}.}"
  : "${EXPECTED_IMPORT_EVENTS:?Set EXPECTED_IMPORT_EVENTS in ${RECORD}.}"
}

require_apply_approval() {
  [[ "$APPLY" == true ]] || {
    echo "Refusing destructive operation without --apply." >&2
    exit 1
  }
  [[ "${CUTOVER_APPROVED:-NO}" == "YES" ]] || {
    echo "Set CUTOVER_APPROVED=YES in ${RECORD} after recording manual approval." >&2
    exit 1
  }
}

init_record() {
  mkdir -p "$LOCAL_DIR"
  if [[ -e "$RECORD" || -e "$CLEANUP_SQL" ]]; then
    echo "Refusing to overwrite existing local cutover files in ${LOCAL_DIR}." >&2
    exit 1
  fi
  umask 077
  cat >"$RECORD" <<'EOF'
# Gitignored, non-secret cutover evidence. Do not put DIRECT_URL, OAuth tokens,
# passwords, client secrets, or SocialAccount extra_data in this file.
CUTOVER_APPROVED=NO
CLEANUP_APPROVED=NO
DEPENDENCY_REVIEWED=NO
EXPECTED_CATALOG_SONGS=2283
EXPECTED_RIGHTS_ROWS=2283
EXPECTED_SNAPSHOTS=1
EXPECTED_ACTIVATIONS=1
EXPECTED_IMPORT_RUNS=3
EXPECTED_IMPORT_EVENTS=20
# Set after the identity preflight, then keep only until cleanup or day seven.
TARGET_EMAIL=''
TARGET_GOOGLE_UID=''
EOF
  cat >"$CLEANUP_SQL" <<'EOF'
-- Replace with the individually reviewed, explicitly schema-qualified legacy objects.
-- Allowed statements: DROP TABLE public.<lowercase_identifier>;
--                     DROP SEQUENCE public.<lowercase_identifier>;
-- Do not use CASCADE. Do not include extensions, functions, wpp_simple_unaccent,
-- Supabase-managed objects, credentials, tokens, or comments containing secrets.
EOF
  chmod 600 "$RECORD" "$CLEANUP_SQL"
  echo "Created ${RECORD} and ${CLEANUP_SQL}. Review and fill them before validation."
}

generate_password() {
  command -v python3 >/dev/null 2>&1 || {
    echo "python3 is required to generate a database password." >&2
    exit 1
  }
  python3 - <<'PYTHON'
import string
import secrets


def generate_db_password(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


print(generate_db_password(20))
PYTHON
}

psql_readonly() {
  psql "$DIRECT_URL" -X -v ON_ERROR_STOP=1 -v expected_songs="$EXPECTED_CATALOG_SONGS" \
    -v expected_rights="$EXPECTED_RIGHTS_ROWS" -v expected_snapshots="$EXPECTED_SNAPSHOTS" \
    -v expected_activations="$EXPECTED_ACTIVATIONS" -v expected_runs="$EXPECTED_IMPORT_RUNS" \
    -v expected_events="$EXPECTED_IMPORT_EVENTS" "$@"
}

preflight() {
  psql "$DIRECT_URL" -X -v ON_ERROR_STOP=1 <<'SQL'
BEGIN READ ONLY;
SELECT current_database(), current_schema(), current_setting('search_path');
SELECT n.nspname AS schema_name, c.relkind, c.relname AS object_name,
       pg_get_userbyid(c.relowner) AS owner
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname IN ('public', 'wpp_catalog_v1', 'wpp_app')
   AND c.relkind IN ('r', 'S', 'v', 'm')
 ORDER BY n.nspname, c.relkind, c.relname;
SELECT extname, nspname AS schema_name
  FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace
 ORDER BY extname;
SELECT n.nspname AS schema_name, c.relname AS table_name, c.relrowsecurity,
       c.relforcerowsecurity
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname IN ('public', 'wpp_catalog_v1', 'wpp_app') AND c.relkind = 'r'
 ORDER BY n.nspname, c.relname;
SELECT table_schema, table_name, grantee, privilege_type
  FROM information_schema.role_table_grants
 WHERE table_schema IN ('public', 'wpp_catalog_v1', 'wpp_app')
 ORDER BY table_schema, table_name, grantee, privilege_type;
ROLLBACK;
SQL
}

validate() {
  psql_readonly <<'SQL'
BEGIN READ ONLY;
SELECT current_schema() = 'wpp_app' AS current_schema_is_wpp_app,
       current_setting('search_path') LIKE 'wpp_app,%' AS search_path_is_wpp_app_first;
SELECT 'catalog_catalogentry' AS check_name, count(*) AS actual,
       :'expected_songs'::bigint AS expected,
       count(*) = :'expected_songs'::bigint AS passed FROM wpp_app.catalog_catalogentry
UNION ALL
SELECT 'catalog_catalogsongrights', count(*), :'expected_rights'::bigint,
       count(*) = :'expected_rights'::bigint FROM wpp_app.catalog_catalogsongrights
UNION ALL
SELECT 'catalog_catalogsnapshot', count(*), :'expected_snapshots'::bigint,
       count(*) = :'expected_snapshots'::bigint FROM wpp_app.catalog_catalogsnapshot
UNION ALL
SELECT 'catalog_catalogactivation', count(*), :'expected_activations'::bigint,
       count(*) = :'expected_activations'::bigint FROM wpp_app.catalog_catalogactivation
UNION ALL
SELECT 'catalog_catalogimportrun', count(*), :'expected_runs'::bigint,
       count(*) = :'expected_runs'::bigint FROM wpp_app.catalog_catalogimportrun
UNION ALL
SELECT 'catalog_catalogimportevent', count(*), :'expected_events'::bigint,
       count(*) = :'expected_events'::bigint FROM wpp_app.catalog_catalogimportevent;
SELECT count(*) > 0 AS migration_ledger_present FROM wpp_app.django_migrations;
SELECT EXISTS (
  SELECT 1
    FROM pg_ts_config config
    JOIN pg_namespace schema ON schema.oid = config.cfgnamespace
   WHERE schema.nspname = 'public'
     AND config.cfgname = 'wpp_simple_unaccent'
) AS text_search_config_present;
WITH expected_roles(role_name) AS (
  VALUES ('anon'), ('authenticated'), ('service_role'), ('wpp_prod_user')
)
SELECT expected_roles.role_name,
       roles.oid IS NOT NULL AS role_exists,
       COALESCE(has_schema_privilege(roles.oid, 'wpp_app', 'USAGE'), false)
         AS has_wpp_app_usage
  FROM expected_roles
  LEFT JOIN pg_roles roles ON roles.rolname = expected_roles.role_name
 ORDER BY expected_roles.role_name;
SELECT n.nspname, c.relname, c.relrowsecurity, count(p.polname) AS policy_count
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  LEFT JOIN pg_policy p ON p.polrelid = c.oid
 WHERE n.nspname = 'wpp_app' AND c.relkind = 'r'
 GROUP BY n.nspname, c.relname, c.relrowsecurity
 ORDER BY c.relname;
ROLLBACK;
SQL
}

rename_schema() {
  require_apply_approval
  psql "$DIRECT_URL" -X -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
DO $$
DECLARE
  source_schema_exists boolean;
  target_schema_exists boolean;
BEGIN
  SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'wpp_catalog_v1')
    INTO source_schema_exists;
  SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'wpp_app')
    INTO target_schema_exists;

  IF source_schema_exists AND target_schema_exists THEN
    RAISE EXCEPTION 'Both wpp_catalog_v1 and wpp_app exist; refusing ambiguous cutover.';
  ELSIF source_schema_exists THEN
    ALTER SCHEMA wpp_catalog_v1 RENAME TO wpp_app;
    RAISE NOTICE 'Renamed wpp_catalog_v1 to wpp_app.';
  ELSIF target_schema_exists THEN
    RAISE NOTICE 'wpp_app already exists; schema rename was previously applied.';
  ELSE
    RAISE EXCEPTION 'Neither wpp_catalog_v1 nor wpp_app exists; refusing cutover.';
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_extension ext
      JOIN pg_namespace namespace ON namespace.oid = ext.extnamespace
     WHERE ext.extname = 'unaccent' AND namespace.nspname <> 'public'
  ) THEN
    ALTER EXTENSION unaccent SET SCHEMA public;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_extension ext
      JOIN pg_namespace namespace ON namespace.oid = ext.extnamespace
     WHERE ext.extname = 'pg_trgm' AND namespace.nspname <> 'public'
  ) THEN
    ALTER EXTENSION pg_trgm SET SCHEMA public;
  END IF;
END
$$;
COMMIT;
SQL
  echo "Update both database URLs to search_path=wpp_app,public, restart services, then run validate."
}

rollback_schema() {
  require_apply_approval
  psql "$DIRECT_URL" -X -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
ALTER SCHEMA wpp_app RENAME TO wpp_catalog_v1;
COMMIT;
SQL
  echo "Restore both database URLs to search_path=wpp_catalog_v1,public and restart services."
}

validate_cleanup_sql() {
  [[ "${CLEANUP_APPROVED:-NO}" == "YES" ]] || {
    echo "Set CLEANUP_APPROVED=YES in ${RECORD} after separate manual approval." >&2
    exit 1
  }
  [[ -s "$CLEANUP_SQL" ]] || {
    echo "Missing reviewed cleanup file: ${CLEANUP_SQL}" >&2
    exit 1
  }
  if ! grep -Ev '^[[:space:]]*(--.*)?$|^DROP (TABLE|SEQUENCE) public\.[a-z_][a-z0-9_]*;$' "$CLEANUP_SQL" >/dev/null; then
    echo "Cleanup file may contain only explicit DROP TABLE/SEQUENCE public.<identifier>; statements." >&2
    exit 1
  fi
  if grep -Ev '^[[:space:]]*(--.*)?$' "$CLEANUP_SQL" | grep -Eqi 'cascade|wpp_simple_unaccent|extension|function|procedure'; then
    echo "Cleanup file includes a forbidden operation or protected object." >&2
    exit 1
  fi
}

review_cleanup_dependencies() {
  validate_cleanup_sql
  local statement object_type object_name
  while IFS= read -r statement; do
    [[ "$statement" =~ ^DROP[[:space:]](TABLE|SEQUENCE)[[:space:]]public\.([a-z_][a-z0-9_]*)\;$ ]] || continue
    object_type="${BASH_REMATCH[1]}"
    object_name="${BASH_REMATCH[2]}"
    echo "Dependencies for ${object_type} public.${object_name}:"
    psql "$DIRECT_URL" -X -v ON_ERROR_STOP=1 -v object_name="$object_name" <<'SQL'
BEGIN READ ONLY;
WITH target AS (
  SELECT c.oid
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public' AND c.relname = :'object_name'
)
SELECT dep_ns.nspname AS dependent_schema, dep.relname AS dependent_object,
       dep.relkind AS dependent_kind, d.deptype
  FROM pg_depend d
  JOIN target ON target.oid = d.refobjid
  JOIN pg_class dep ON dep.oid = d.objid
  JOIN pg_namespace dep_ns ON dep_ns.oid = dep.relnamespace
 ORDER BY dependent_schema, dependent_object, d.deptype;
ROLLBACK;
SQL
  done < "$CLEANUP_SQL"
  echo "Review this output, record it locally, then set DEPENDENCY_REVIEWED=YES."
}

cleanup() {
  require_apply_approval
  validate_cleanup_sql
  [[ "${DEPENDENCY_REVIEWED:-NO}" == "YES" ]] || {
    echo "Run '$0 dependencies', record the review, then set DEPENDENCY_REVIEWED=YES." >&2
    exit 1
  }
  psql "$DIRECT_URL" -X -v ON_ERROR_STOP=1 -c 'BEGIN;' -f "$CLEANUP_SQL" -c 'COMMIT;'
}

require_psql
case "$MODE" in
  generate-password) generate_password ;;
  init) init_record ;;
  preflight) require_direct_url; preflight ;;
  validate) require_direct_url; load_record; validate ;;
  dependencies) require_direct_url; load_record; review_cleanup_dependencies ;;
  rename) require_direct_url; load_record; rename_schema ;;
  rollback) require_direct_url; load_record; rollback_schema ;;
  cleanup) require_direct_url; load_record; cleanup ;;
  *) usage >&2; exit 2 ;;
esac
