import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import apps.common.db.fields


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("invitations", "0004_auto_20230328_1430"),
    ]

    operations = [
        migrations.CreateModel(
            name="InvitationRequest",
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
                ("created_on", models.DateTimeField(auto_now_add=True)),
                (
                    "updated_on",
                    apps.common.db.fields.AutoDateTimeField(
                        default=django.utils.timezone.now
                    ),
                ),
                ("deleted_on", models.DateTimeField(blank=True, null=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("first_name", models.CharField(max_length=150)),
                ("last_name", models.CharField(max_length=150)),
                ("message", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "access_level",
                    models.CharField(
                        blank=True,
                        choices=[("catalog_admin", "Catalog Administrator")],
                        default="",
                        max_length=20,
                    ),
                ),
                (
                    "invitation",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invitation_request",
                        to="invitations.invitation",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invitation_requests_reviewed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Invitation request",
                "verbose_name_plural": "Invitation requests",
            },
        )
    ]
