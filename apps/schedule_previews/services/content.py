from typing import TypedDict


class PreviewSlide(TypedDict):
    section_label: str
    lines: list[str]


class PreviewSong(TypedDict):
    title: str
    slides: list[PreviewSlide]


class PreviewSection(TypedDict):
    title: str | None
    songs: list[PreviewSong]


class PreviewContent(TypedDict):
    title: str
    sections: list[PreviewSection]


class PublishRequestDetails(TypedDict):
    method: str
    path: str
    source_ip: str | None
    request_id: str | None
