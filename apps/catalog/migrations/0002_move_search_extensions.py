"""Keep search extensions outside the schema exposed by Supabase's Data API."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("catalog", "0001_initial"),
        ("common", "0002_deny_supabase_api_access"),
    ]
    operations = [  # noqa: RUF012
        # Move existing objects in place so search indexes and mappings stay intact.
        migrations.RunSQL(
            sql=[
                "CREATE SCHEMA IF NOT EXISTS extensions",
                "ALTER EXTENSION unaccent SET SCHEMA extensions",
                "ALTER EXTENSION pg_trgm SET SCHEMA extensions",
            ],
            reverse_sql=[
                "ALTER EXTENSION pg_trgm SET SCHEMA public",
                "ALTER EXTENSION unaccent SET SCHEMA public",
            ],
        ),
    ]
