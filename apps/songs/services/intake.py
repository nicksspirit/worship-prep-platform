"""Song intake service with fuzzy title deduplication."""

import difflib
from dataclasses import dataclass

from asgiref.sync import sync_to_async
from django.db import transaction

from apps.schedules.choices import ScheduleItemType, ServiceScheduleStatus
from apps.schedules.models import ScheduleItem, ServiceSchedule
from apps.schedules.services.intake import default_schedule_title
from apps.songs.models import Song, SongAssignment
from apps.songs.schemas import SongIntakePayload

SIMILARITY_THRESHOLD = 0.85


@dataclass
class SongIntakeResult:
    song: Song
    is_existing: bool
    linked_to_schedule: bool
    schedule_date: str | None


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().strip().split())


def _find_similar_song(title: str) -> Song | None:
    """Find an existing song with similar normalized title."""
    normalized = _normalize_title(title)
    if not normalized:
        return None

    candidates = Song.objects.all()
    best_match: Song | None = None
    best_ratio = 0.0

    for song in candidates:
        ratio = difflib.SequenceMatcher(None, normalized, _normalize_title(song.title)).ratio()
        if ratio >= SIMILARITY_THRESHOLD and ratio > best_ratio:
            best_ratio = ratio
            best_match = song

    return best_match


def _normalize_song_item_type(item_type: str | None) -> str | None:
    raw_type = (item_type or "").strip().lower()
    if raw_type in (ScheduleItemType.WORSHIP_SONG, ScheduleItemType.HYMN):
        return raw_type
    if not raw_type:
        return ScheduleItemType.WORSHIP_SONG
    return None


def _default_schedule_item_title(item_type: str) -> str:
    if item_type == ScheduleItemType.HYMN:
        return "Congregational Hymn"
    return "Praise & Worship"


def _get_or_create_schedule_item(
    schedule_date,
    item_type: str | None,
) -> ScheduleItem | None:
    """Get or create the matching schedule context for worship songs or hymns."""
    if not schedule_date:
        return None

    raw_type = _normalize_song_item_type(item_type)
    if raw_type is None:
        return None

    schedule, created = ServiceSchedule.objects.get_or_create(
        date=schedule_date,
        defaults={
            "title": default_schedule_title(schedule_date),
            "status": ServiceScheduleStatus.IN_PROGRESS,
        },
    )
    if not created and schedule.status == ServiceScheduleStatus.DRAFT:
        schedule.status = ServiceScheduleStatus.IN_PROGRESS
        schedule.save(update_fields=["status", "updated_on"])

    schedule_item = (
        ScheduleItem.objects.filter(schedule=schedule, item_type=raw_type)
        .order_by("position")
        .first()
    )
    if schedule_item is not None:
        return schedule_item

    next_position = (
        ScheduleItem.objects.filter(schedule=schedule)
        .order_by("-position")
        .values_list("position", flat=True)
        .first()
    )
    return ScheduleItem.objects.create(
        schedule=schedule,
        position=1 if next_position is None else next_position + 1,
        item_type=raw_type,
        title=_default_schedule_item_title(raw_type),
    )


def _next_song_assignment_position(schedule_item: ScheduleItem) -> int:
    last_position = (
        schedule_item.song_assignments.order_by("-position")
        .values_list("position", flat=True)
        .first()
    )
    if last_position is None:
        return 1
    return last_position + 1


def _resolve_song_assignment_position(
    schedule_item: ScheduleItem,
    explicit_position: int | None,
) -> int:
    if explicit_position is not None and explicit_position > 0:
        return explicit_position
    return _next_song_assignment_position(schedule_item)


@transaction.atomic
def _intake_song_sync(payload: SongIntakePayload) -> SongIntakeResult:
    existing = _find_similar_song(payload.song_title)
    linked_to_schedule = False
    schedule_date_str = payload.schedule_date.isoformat() if payload.schedule_date else None

    if existing:
        content_changed = (
            existing.formatted_lyrics != payload.formatted_lyrics
            or existing.raw_lyrics != payload.raw_lyrics
        )
        if content_changed:
            existing.raw_lyrics = payload.raw_lyrics
            existing.formatted_lyrics = payload.formatted_lyrics
            existing.slide_count = payload.slide_count
            existing.save()

        schedule_item = _get_or_create_schedule_item(
            payload.schedule_date,
            payload.item_type,
        )
        if schedule_item:
            SongAssignment.objects.get_or_create(
                schedule_item=schedule_item,
                song=existing,
                defaults={
                    "position": _resolve_song_assignment_position(
                        schedule_item,
                        payload.position,
                    )
                },
            )
            linked_to_schedule = True

        return SongIntakeResult(
            song=existing,
            is_existing=True,
            linked_to_schedule=linked_to_schedule,
            schedule_date=schedule_date_str,
        )

    song = Song.objects.create(
        title=payload.song_title,
        raw_lyrics=payload.raw_lyrics,
        formatted_lyrics=payload.formatted_lyrics,
        slide_count=payload.slide_count,
    )

    schedule_item = _get_or_create_schedule_item(
        payload.schedule_date,
        payload.item_type,
    )
    if schedule_item:
        SongAssignment.objects.create(
            schedule_item=schedule_item,
            song=song,
            position=_resolve_song_assignment_position(
                schedule_item,
                payload.position,
            ),
        )
        linked_to_schedule = True

    return SongIntakeResult(
        song=song,
        is_existing=False,
        linked_to_schedule=linked_to_schedule,
        schedule_date=schedule_date_str,
    )


async def intake_song(payload: SongIntakePayload) -> SongIntakeResult:
    return await sync_to_async(_intake_song_sync, thread_sensitive=True)(payload)
