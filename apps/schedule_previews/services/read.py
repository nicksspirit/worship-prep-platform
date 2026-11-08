from datetime import datetime
from typing import TypedDict, cast
from uuid import UUID

from django.utils import timezone

from apps.schedule_previews.models import SchedulePreview
from apps.schedule_previews.services.content import PreviewContent, PreviewSong


class _UngroupedPreview(TypedDict):
    title: str
    songs: list[PreviewSong]


def read_preview(preview_id: UUID) -> tuple[PreviewContent, datetime | None] | None:
    """Return the published content only while the link is live."""

    row = cast(
        tuple[PreviewContent | _UngroupedPreview, datetime | None] | None,
        SchedulePreview.objects.filter(pk=preview_id, expires_at__gt=timezone.now())
        .values_list("content", "created_at")
        .first(),
    )
    if row is None:
        return None
    content, created_at = row
    if "sections" in content:
        return content, created_at
    return {
        "title": content["title"],
        "sections": [{"title": None, "songs": content["songs"]}],
    }, created_at
