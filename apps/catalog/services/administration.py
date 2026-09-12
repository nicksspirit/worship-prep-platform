"""Catalog administration use cases."""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import (
    CatalogEntry,
    CatalogSongRights,
    LyricsRightsChange,
    RightsBasis,
    RightsStatus,
)

logger = structlog.get_logger(__name__)

ALLOWED_BASES = {
    RightsStatus.APPROVED: {
        RightsBasis.PUBLIC_DOMAIN,
        RightsBasis.DIRECT_LICENSE,
        RightsBasis.WRITTEN_PERMISSION,
    },
    RightsStatus.RESTRICTED: {
        RightsBasis.KNOWN_PROHIBITION,
        RightsBasis.PERMISSION_REVOKED,
        RightsBasis.OWNER_REQUEST,
    },
    RightsStatus.UNKNOWN: {RightsBasis.INCONCLUSIVE},
}


@dataclass(frozen=True)
class ScheduledImportFailure:
    """Facts needed to notify operators about a failed scheduled import."""

    run_id: str
    failure_code: str
    failure_summary: str


@transaction.atomic
def change_lyrics_rights(
    rights: CatalogSongRights,
    *,
    status: str,
    basis: str,
    evidence_reference: str,
    explanation: str,
    user,
) -> LyricsRightsChange:
    """Apply one evidence-backed Superuser decision across retained snapshots."""
    if not user or not user.is_superuser:
        raise PermissionDenied("Only Superusers may change Lyrics Rights Status.")
    evidence_reference = evidence_reference.strip()
    explanation = explanation.strip()
    if status not in RightsStatus.values:
        raise ValidationError({"status": "Select a valid Lyrics Rights Status."})
    if basis not in ALLOWED_BASES[status]:
        raise ValidationError({"basis": "The evidence basis does not establish the selected status."})
    if not evidence_reference:
        raise ValidationError({"evidence_reference": "An evidence reference is required."})
    if not explanation:
        raise ValidationError({"explanation": "An explanatory note is required."})
    locked = CatalogSongRights.objects.select_for_update().get(pk=rights.pk)
    decided_at = timezone.now()
    change = LyricsRightsChange.objects.create(rights=locked, previous_status=locked.status, new_status=status, basis=basis, evidence_reference=evidence_reference, explanation=explanation, decided_by=user, decided_at=decided_at)
    locked.status = status
    locked.basis = basis
    locked.evidence_reference = evidence_reference
    locked.explanation = explanation
    locked.decided_by = user
    locked.decided_at = decided_at
    locked.save(
        update_fields=[
            "status",
            "basis",
            "evidence_reference",
            "explanation",
            "decided_by",
            "decided_at",
        ]
    )
    CatalogEntry.objects.filter(song_uid=locked.song_uid).update(rights_status=status)
    return change


def notify_scheduled_import_failure(failure: ScheduledImportFailure) -> None:
    """Email active Superusers about a failed scheduled Catalog Import."""
    recipients = list(User.objects.filter(is_active=True, is_superuser=True).exclude(email="").values_list("email", flat=True))
    if not recipients:
        return
    path = reverse("admin:catalog_catalogimportrun_change", args=[failure.run_id])
    domain = Site.objects.get_current().domain.strip()
    scheme = "http" if domain.startswith(("localhost", "127.0.0.1")) else "https"
    url = path if not domain else f"{scheme}://{domain}{path}"
    body = (
        "A scheduled Catalog Import failed. The active Song Catalog was left "
        "unchanged. The Catalog Exporter will retry this run once after 30 minutes.\n\n"
        f"Catalog Import Run: {failure.run_id}\n"
        f"Failure: {failure.failure_code} — {failure.failure_summary}\n"
        f"Catalog Administration: {url}\n"
    )
    try:
        EmailMessage(
            subject=f"Worship Prep: scheduled Catalog Import {failure.run_id} failed",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[],
            bcc=recipients,
        ).send(fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send scheduled Catalog Import alert for run %s", failure.run_id
        )
