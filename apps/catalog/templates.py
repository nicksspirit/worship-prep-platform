from typing import NamedTuple, Protocol

from django.http import HttpRequest
from django.template.response import TemplateResponse
from reactivated import template


class RenderableTemplate(Protocol):
    """Protocol for Reactivated template classes with a runtime render method."""

    def render(self, request: HttpRequest) -> TemplateResponse: ...


class FreshnessProps(NamedTuple):
    iso: str
    absolute: str
    relative: str


class SearchItemProps(NamedTuple):
    song_uid: str
    url: str
    title: str
    author: str
    lyric_preview: list[str]
    lyrics_available: bool
    rights_status: str
    song_freshness: FreshnessProps


@template
class CatalogSearchPage(NamedTuple):
    title: str
    query: str
    mode: str
    limit: int
    searched: bool
    results: list[SearchItemProps]
    catalog_freshness: FreshnessProps | None
    next_url: str | None
    has_more: bool
    error: str | None
    restart_url: str | None
    prototype_variant: str | None


class SectionProps(NamedTuple):
    position: int
    label: str
    text: str


class SlideProps(NamedTuple):
    position: int
    section_label: str
    lines: list[str]


@template
class SongDetailPage(NamedTuple):
    title: str
    author: str
    copyright_notice: str
    rights_status: str
    lyrics_available: bool
    sections: list[SectionProps]
    slides: list[SlideProps]
    slide_count: int
    song_freshness: FreshnessProps
    catalog_freshness: FreshnessProps | None
    catalog_url: str
