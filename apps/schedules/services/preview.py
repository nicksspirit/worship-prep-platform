"""Schedule preview service for the service preview page."""

import datetime as dt
from dataclasses import dataclass

from asgiref.sync import sync_to_async
from django.db.models import Q

from apps.schedules.choices import ServiceScheduleStatus
from apps.schedules.models import ScheduleItem, ServiceSchedule
from apps.schedules.schemas import (
    ScheduleItemDetail,
    SchedulePreviewResponse,
    SongDetail,
)


@dataclass
class PreviewResult:
    schedule: ServiceSchedule | None
    prev_date: str | None
    next_date: str | None


def _get_preview_schedule(
    date: dt.date,
    *,
    include_unpublished: bool = False,
) -> PreviewResult | None:
    """Fetch schedule by date and previous/next visible dates."""
    schedule_filters = {"date": date}
    if not include_unpublished:
        schedule_filters["status__in"] = (
            ServiceScheduleStatus.READY,
            ServiceScheduleStatus.PUBLISHED,
        )

    schedule = (
        ServiceSchedule.objects.filter(**schedule_filters)
        .prefetch_related(
            "schedule_items__song_assignments__song",
            "schedule_items__assigned_contact",
        )
        .first()
    )
    if not schedule:
        return None

    visible = Q(status=ServiceScheduleStatus.READY) | Q(status=ServiceScheduleStatus.PUBLISHED)
    prev = (
        ServiceSchedule.objects.filter(date__lt=date)
        .filter(visible)
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    )
    next_ = (
        ServiceSchedule.objects.filter(date__gt=date)
        .filter(visible)
        .order_by("date")
        .values_list("date", flat=True)
        .first()
    )

    return PreviewResult(
        schedule=schedule,
        prev_date=prev.isoformat() if prev else None,
        next_date=next_.isoformat() if next_ else None,
    )


def _build_preview_response(result: PreviewResult) -> SchedulePreviewResponse:
    schedule = result.schedule
    items: list[ScheduleItemDetail] = []

    for item in schedule.schedule_items.all():
        songs: list[SongDetail] = []
        for assignment in item.song_assignments.all():
            song = assignment.song
            filename = song.lyrics_file.name or ""
            if "/" in filename:
                filename = filename.split("/")[-1]
            songs.append(
                SongDetail(
                    song_id=str(song.pk),
                    title=song.title,
                    formatted_lyrics=song.formatted_lyrics or "",
                    filename=filename,
                    slide_count=song.slide_count,
                    position=assignment.position,
                )
            )

        is_complete = bool(item.assigned_contact and item.start_time)
        items.append(
            ScheduleItemDetail(
                position=item.position,
                item_type=item.item_type,
                title=item.title,
                start_time=item.start_time.strftime("%H:%M") if item.start_time else None,
                end_time=item.end_time.strftime("%H:%M") if item.end_time else None,
                leader_name=item.assigned_contact.name if item.assigned_contact else None,
                notes=item.notes or "",
                status=item.status,
                is_complete=is_complete,
                songs=songs,
            )
        )

    return SchedulePreviewResponse(
        schedule_id=str(schedule.pk),
        date=schedule.date.isoformat(),
        title=schedule.title or "",
        status=schedule.status,
        items=items,
        prev_date=result.prev_date,
        next_date=result.next_date,
    )


def get_schedule_preview(
    date: dt.date,
    *,
    include_unpublished: bool = False,
) -> SchedulePreviewResponse | None:
    """Get schedule preview for a given date, or None if not found."""
    result = _get_preview_schedule(date, include_unpublished=include_unpublished)
    if not result or not result.schedule:
        return None
    return _build_preview_response(result)


async def get_schedule_preview_async(
    date: dt.date,
    *,
    include_unpublished: bool = False,
) -> SchedulePreviewResponse | None:
    return await sync_to_async(get_schedule_preview, thread_sensitive=True)(
        date,
        include_unpublished=include_unpublished,
    )
