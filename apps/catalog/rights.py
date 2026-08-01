"""Audited Lyrics Rights Status decisions and catalog-wide projection updates."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import (
    CatalogEntry,
    CatalogSongRights,
    LyricsRightsChange,
    RightsBasis,
    RightsStatus,
)

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
        raise ValidationError(
            {"basis": "The evidence basis does not establish the selected status."}
        )
    if not evidence_reference:
        raise ValidationError(
            {"evidence_reference": "An evidence reference is required."}
        )
    if not explanation:
        raise ValidationError({"explanation": "An explanatory note is required."})

    locked = CatalogSongRights.objects.select_for_update().get(pk=rights.pk)
    decided_at = timezone.now()
    change = LyricsRightsChange.objects.create(
        rights=locked,
        previous_status=locked.status,
        new_status=status,
        basis=basis,
        evidence_reference=evidence_reference,
        explanation=explanation,
        decided_by=user,
        decided_at=decided_at,
    )
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

    # Snapshot content stays immutable; this column is the deliberately denormalized
    # administrative policy overlay used by every read surface and retained snapshot.
    CatalogEntry.objects.filter(song_uid=locked.song_uid).update(rights_status=status)
    return change
