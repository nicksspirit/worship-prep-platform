from typing import NamedTuple

from reactivated import template


class EmptyStateData(NamedTuple):
    heading: str
    message: str
    link_url: str | None
    link_label: str | None


class ScheduleSummary(NamedTuple):
    date: str
    display_date: str
    title: str
    item_count: int
    preview_url: str
    status: str
    status_label: str


class SongPreviewData(NamedTuple):
    song_id: str
    title: str
    formatted_lyrics: str
    filename: str
    slide_count: int | None
    position: int


class ScheduleItemPreviewData(NamedTuple):
    position: int
    item_type: str
    item_label: str
    title: str
    time_label: str
    leader_name: str | None
    leader_label: str
    notes: str
    status: str
    status_label: str
    is_complete: bool
    songs: list[SongPreviewData]


class SchedulePreviewData(NamedTuple):
    schedule_id: str
    date: str
    display_date: str
    title: str
    status: str
    status_label: str
    prev_url: str | None
    next_url: str | None
    items: list[ScheduleItemPreviewData]


@template
class ScheduleListPage(NamedTuple):
    title: str
    schedules: list[ScheduleSummary]
    empty_state: EmptyStateData | None


@template
class ServicePreviewPage(NamedTuple):
    title: str
    schedule: SchedulePreviewData | None
    empty_state: EmptyStateData | None
