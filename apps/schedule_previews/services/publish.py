from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.api_keys.models import APIKeyScope
from apps.api_keys.services import (
    AuthorizationDenied,
    authorize_api_key,
    check_rate_limit,
)
from apps.schedule_previews.models import SchedulePreview
from apps.schedule_previews.services.content import PreviewContent, PublishRequestDetails


@dataclass(frozen=True, slots=True)
class PublishedPreview:
    id: UUID
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PublishRateLimited:
    retry_after: int


def publish_preview(
    content: PreviewContent,
    authorization: str,
    request_details: PublishRequestDetails,
    submitted_payload: dict[str, object],
) -> PublishedPreview | AuthorizationDenied | PublishRateLimited:
    """Save a new snapshot after verifying the Integration Client may publish."""

    auth = authorize_api_key(
        authorization, required_scopes=[APIKeyScope.SCHEDULE_PREVIEW_PUBLISH]
    )
    if isinstance(auth, AuthorizationDenied):
        return auth
    rate = check_rate_limit(auth.api_key, bucket="schedule.preview.publish", limit=12)
    if not rate.allowed:
        return PublishRateLimited(rate.retry_after)

    now = timezone.now()
    expires_at = now + timedelta(hours=settings.SCHEDULE_PREVIEW_TTL_HOURS)
    with transaction.atomic():
        preview = SchedulePreview.objects.create(
            content=content,
            created_at=now,
            expires_at=expires_at,
            request_details=request_details,
            submitted_payload=submitted_payload,
            publisher_key_id=auth.api_key.pk,
        )
        # shortcut: idle sites retain expired data until the next publish, add a job if needed.
        SchedulePreview.objects.filter(expires_at__lte=now).delete()
    return PublishedPreview(preview.id, expires_at)
