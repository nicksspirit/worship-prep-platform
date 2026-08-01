import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def harden_administration_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    tables = (
        "catalog_catalogsongrights",
        "catalog_lyricsrightschange",
    )
    with schema_editor.connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        cursor.execute(
            "SELECT rolname FROM pg_catalog.pg_roles "
            "WHERE rolname = ANY(%s)",
            [["anon", "authenticated"]],
        )
        roles = [row[0] for row in cursor.fetchall()]
        if roles:
            role_list = ", ".join(f'"{role}"' for role in roles)
            table_list = ", ".join(f'public."{table}"' for table in tables)
            cursor.execute(
                f"REVOKE ALL PRIVILEGES ON TABLE {table_list} FROM {role_list}"
            )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0003_catalog_search"),
    ]

    operations = [
        migrations.AddField(
            model_name="catalogimportrun",
            name="trigger",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("scheduled", "Scheduled"),
                ],
                default="manual",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="CatalogSongRights",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("song_uid", models.CharField(max_length=255, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("approved", "Approved"),
                            ("unknown", "Unknown"),
                            ("restricted", "Restricted"),
                        ],
                        default="unknown",
                        max_length=16,
                    ),
                ),
                (
                    "basis",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("public_domain", "Documented public-domain status"),
                            ("direct_license", "Direct license"),
                            (
                                "written_permission",
                                "Written web-display permission",
                            ),
                            ("known_prohibition", "Known prohibition"),
                            (
                                "permission_revoked",
                                "Permission expired or revoked",
                            ),
                            ("owner_request", "Owner request to withhold"),
                            ("inconclusive", "Inconclusive evidence"),
                        ],
                        max_length=32,
                    ),
                ),
                ("evidence_reference", models.TextField(blank=True)),
                ("explanation", models.TextField(blank=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="current_lyrics_rights_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Lyrics rights provenance",
                "verbose_name_plural": "Lyrics rights provenance",
                "ordering": ["song_uid"],
            },
        ),
        migrations.CreateModel(
            name="LyricsRightsChange",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "previous_status",
                    models.CharField(
                        choices=[
                            ("approved", "Approved"),
                            ("unknown", "Unknown"),
                            ("restricted", "Restricted"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "new_status",
                    models.CharField(
                        choices=[
                            ("approved", "Approved"),
                            ("unknown", "Unknown"),
                            ("restricted", "Restricted"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "basis",
                    models.CharField(
                        choices=[
                            ("public_domain", "Documented public-domain status"),
                            ("direct_license", "Direct license"),
                            (
                                "written_permission",
                                "Written web-display permission",
                            ),
                            ("known_prohibition", "Known prohibition"),
                            (
                                "permission_revoked",
                                "Permission expired or revoked",
                            ),
                            ("owner_request", "Owner request to withhold"),
                            ("inconclusive", "Inconclusive evidence"),
                        ],
                        max_length=32,
                    ),
                ),
                ("evidence_reference", models.TextField()),
                ("explanation", models.TextField()),
                ("decided_at", models.DateTimeField()),
                (
                    "decided_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lyrics_rights_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "rights",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="changes",
                        to="catalog.catalogsongrights",
                    ),
                ),
            ],
            options={"ordering": ["-decided_at", "-pk"]},
        ),
        migrations.RunPython(
            harden_administration_tables,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
