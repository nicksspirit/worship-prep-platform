from typing import NamedTuple

from reactivated import template


class PreviewSlideProps(NamedTuple):
    position: int
    section_label: str
    lines: list[str]


class PreviewSongProps(NamedTuple):
    title: str
    slides: list[PreviewSlideProps]


class PreviewSectionProps(NamedTuple):
    title: str | None
    songs: list[PreviewSongProps]


@template
class SchedulePreviewPage(NamedTuple):
    title: str | None
    sections: list[PreviewSectionProps]
    created_date: str | None
