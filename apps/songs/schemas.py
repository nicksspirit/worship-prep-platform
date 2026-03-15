import datetime as dt

import msgspec


class SongIntakePayload(msgspec.Struct, kw_only=True):
    song_title: str
    raw_lyrics: str
    formatted_lyrics: str
    filename: str
    slide_count: int
    schedule_date: dt.date | None = None
    item_type: str | None = None


class SongIntakeResponse(msgspec.Struct, kw_only=True):
    song_id: str
    song_title: str
    filename: str
    slide_count: int
    linked_to_schedule: bool
    schedule_date: str | None
    is_existing: bool
    preview_url: str | None = None
