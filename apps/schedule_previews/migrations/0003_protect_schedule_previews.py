from typing import ClassVar

from django.db import migrations


def protect_schedule_previews(apps, schema_editor):
    """Keep preview snapshots behind the Django and Bolt access boundary."""

    if schema_editor.connection.vendor != "postgresql":
        return

    model = apps.get_model("schedule_previews", "SchedulePreview")
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT current_schema()")
        table = f"{quote(cursor.fetchone()[0])}.{quote(model._meta.db_table)}"
        cursor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        cursor.execute(
            "SELECT rolname FROM pg_roles "
            "WHERE rolname IN ('anon', 'authenticated', 'service_role')"
        )
        roles = [row[0] for row in cursor.fetchall()]
        grant_roles = ", ".join(["PUBLIC", *(quote(role) for role in roles)])
        cursor.execute(f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM {grant_roles}")

        api_roles = ", ".join(quote(role) for role in roles if role != "service_role")
        if api_roles:
            cursor.execute(f"DROP POLICY IF EXISTS deny_supabase_api ON {table}")
            cursor.execute(
                f"CREATE POLICY deny_supabase_api ON {table} "
                f"AS RESTRICTIVE FOR ALL TO {api_roles} USING (false) WITH CHECK (false)"
            )


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("common", "0002_deny_supabase_api_access"),
        ("schedule_previews", "0002_schedulepreview_created_at"),
    ]
    operations: ClassVar[list[migrations.RunPython]] = [
        migrations.RunPython(protect_schedule_previews, migrations.RunPython.noop),
    ]
