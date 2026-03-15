"""Song intake service with fuzzy title deduplication."""

import difflib
from dataclasses import dataclass

from asgiref.sync import sync_to_async
from django.db import transaction

from apps.schedules.choices import ScheduleItemType
from apps.schedules.models import ScheduleItem, ServiceSchedule
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


def _get_or_create_schedule_item(
    schedule_date,
    item_type: str | None,
) -> ScheduleItem | None:
    """Get the matching ScheduleItem for worship_song or hymn type."""
    if not schedule_date or not item_type:
        return None

    raw_type = (item_type or "").strip().lower()
    if raw_type not in (ScheduleItemType.WORSHIP_SONG, ScheduleItemType.HYMN):
        return None

    schedule = ServiceSchedule.objects.filter(date=schedule_date).first()
    if not schedule:
        return None

    return (
        ScheduleItem.objects.filter(
            schedule=schedule,
            item_type=raw_type,
        )
        .order_by("position")
        .first()
    )


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
                defaults={"position": schedule_item.song_assignments.count()},
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
            position=schedule_item.song_assignments.count(),
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
