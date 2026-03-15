import datetime as dt

import msgspec


class AgendaItemPayload(msgspec.Struct, kw_only=True):
    position: int | None = None
    time_start: str | None = None
    time_end: str | None = None
    item_type: str | None = None
    title: str
    leader_name: str | None = None
    notes: str | None = None
    is_required: bool = True


class ScheduleIntakePayload(msgspec.Struct, kw_only=True):
    source: str = "unknown"
    target_date: dt.date
    raw_content: str
    sender_name: str
    sender_phone: str | None = None
    sender_email: str | None = None
    source_message_id: str | None = None
    title: str | None = None
    items: list[AgendaItemPayload] = []


class IntakeResponse(msgspec.Struct, kw_only=True):
    schedule_id: str
    date: str
    created_or_updated: str
    items_created: int
    items_updated: int
    confirmation_text: str
    preview_url: str


class SongDetail(msgspec.Struct, kw_only=True):
    song_id: str
    title: str
    formatted_lyrics: str
    filename: str
    slide_count: int | None
    position: int


class ScheduleItemDetail(msgspec.Struct, kw_only=True):
    position: int
    item_type: str
    title: str
    start_time: str | None
    end_time: str | None
    leader_name: str | None
    notes: str
    status: str
    is_complete: bool
    songs: list[SongDetail]


class SchedulePreviewResponse(msgspec.Struct, kw_only=True):
    schedule_id: str
    date: str
    title: str
    status: str
    items: list[ScheduleItemDetail]
    prev_date: str | None
    next_date: str | None
