from django.db import migrations

SUPABASE_API_ROLES = ("anon", "authenticated")
DJANGO_INTERNAL_TABLES = ("django_migrations",)


def harden_supabase_api_exposure(apps, schema_editor):
    """Remove direct Supabase API access to Django-owned public tables."""

    if schema_editor.connection.vendor != "postgresql":
        return

    table_names = sorted(
        {
            model._meta.db_table
            for model in apps.get_models(include_auto_created=True)
            if model._meta.managed and "." not in model._meta.db_table
        }
        | set(DJANGO_INTERNAL_TABLES)
    )
    quote_name = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        schema_name = cursor.fetchone()[0]
        qualified_tables = [
            f"{quote_name(schema_name)}.{quote_name(table_name)}"
            for table_name in table_names
        ]
        cursor.execute(
            """
            SELECT rolname
            FROM pg_catalog.pg_roles
            WHERE rolname = ANY(%s)
            """,
            [list(SUPABASE_API_ROLES)],
        )
        existing_roles = {row[0] for row in cursor.fetchall()}

        for table_name in qualified_tables:
            cursor.execute(
                f"ALTER TABLE IF EXISTS {table_name} ENABLE ROW LEVEL SECURITY"
            )

        if not existing_roles:
            return

        role_list = ", ".join(
            quote_name(role) for role in SUPABASE_API_ROLES if role in existing_roles
        )
        table_list = ", ".join(qualified_tables)
        cursor.execute(f"REVOKE ALL PRIVILEGES ON TABLE {table_list} FROM {role_list}")
        for object_type in ("SEQUENCES", "FUNCTIONS"):
            cursor.execute(
                f"REVOKE ALL PRIVILEGES ON ALL {object_type} IN SCHEMA "
                f"{quote_name(schema_name)} "
                f"FROM {role_list}"
            )
            cursor.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {quote_name(schema_name)} "
                f"REVOKE ALL PRIVILEGES ON {object_type} FROM {role_list}"
            )
        cursor.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {quote_name(schema_name)} "
            f"REVOKE ALL PRIVILEGES ON TABLES FROM {role_list}"
        )


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("account", "0009_emailaddress_unique_primary_email"),
        ("accounts", "0002_invitation_request"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("api_keys", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("catalog", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("invitations", "0004_auto_20230328_1430"),
        ("sessions", "0001_initial"),
        ("sites", "0002_alter_domain_unique"),
        ("socialaccount", "0006_alter_socialaccount_extra_data"),
    ]
    operations = [
        migrations.RunPython(
            harden_supabase_api_exposure,
            reverse_code=migrations.RunPython.noop,
        )
    ]
