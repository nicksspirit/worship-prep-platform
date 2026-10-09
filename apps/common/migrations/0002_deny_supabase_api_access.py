"""Make the application's Supabase API rejection explicit to the advisor."""

from django.db import migrations


def _select_table_names(models):
    """Select managed, unqualified tables from historical models."""
    return sorted(
        {
            model._meta.db_table
            for model in models
            if model._meta.managed and "." not in model._meta.db_table
        }
        | {"django_migrations"}
    )


def _build_denial_policies(schema, tables, roles):
    """Build rejection policies from already quoted SQL identifiers."""
    if not roles:
        return []
    return [
        f"CREATE POLICY deny_supabase_api ON {schema}.{table} "
        f"AS RESTRICTIVE FOR ALL TO {', '.join(roles)} "
        "USING (false) WITH CHECK (false)"
        for table in tables
    ]


def deny_supabase_api_access(apps, schema_editor):
    """Reject all row access by Supabase's public API roles."""
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    tables = [
        quote(table)
        for table in _select_table_names(apps.get_models(include_auto_created=True))
    ]
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        schema = quote(cursor.fetchone()[0])
        cursor.execute(
            "SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')"
        )
        roles = [quote(row[0]) for row in cursor.fetchall()]
        for statement in _build_denial_policies(schema, tables, roles):
            cursor.execute(statement)


def remove_supabase_api_denial(apps, schema_editor):
    """Restore the previous implicit rejection while retaining RLS and grants."""
    if schema_editor.connection.vendor != "postgresql":
        return

    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        schema = cursor.fetchone()[0]
        for table in _select_table_names(apps.get_models(include_auto_created=True)):
            cursor.execute(
                f"DROP POLICY IF EXISTS deny_supabase_api "
                f"ON {quote(schema)}.{quote(table)}"
            )


class Migration(migrations.Migration):
    dependencies = [("common", "0001_harden_supabase_api_exposure")]
    operations = [
        migrations.RunPython(deny_supabase_api_access, remove_supabase_api_denial),
    ]
