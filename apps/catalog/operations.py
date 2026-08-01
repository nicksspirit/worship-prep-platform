"""Operator notifications for Catalog Import automation."""

from __future__ import annotations

import structlog
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import CatalogImportRun

logger = structlog.get_logger(__name__)


def _absolute_admin_url(run: CatalogImportRun) -> str:
    path = reverse("admin:catalog_catalogimportrun_change", args=[run.pk])
    domain = Site.objects.get_current().domain.strip()
    if not domain:
        return path
    scheme = "http" if domain.startswith(("localhost", "127.0.0.1")) else "https"
    return f"{scheme}://{domain}{path}"


def notify_scheduled_import_failure(run: CatalogImportRun) -> None:
    """Email active Superusers about a failed scheduled Catalog Import."""

    recipients = list(
        User.objects.filter(is_active=True, is_superuser=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        return
    body = (
        "A scheduled Catalog Import failed. The active Song Catalog was left "
        "unchanged. The Catalog Exporter will retry this run once after 30 minutes.\n\n"
        f"Catalog Import Run: {run.pk}\n"
        f"Failure: {run.failure_code} — {run.failure_summary}\n"
        f"Catalog Administration: {_absolute_admin_url(run)}\n"
    )
    try:
        EmailMessage(
            subject=f"Worship Prep: scheduled Catalog Import {run.pk} failed",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[],
            bcc=recipients,
        ).send(fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send scheduled Catalog Import alert for run %s", run.pk
        )
