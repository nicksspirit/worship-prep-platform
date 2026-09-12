from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

from apps.catalog.services import CatalogSearchPage, CatalogSong, SearchRestart
from apps.catalog.templates import (
    CatalogSearchPage as CatalogSearchTemplate,
)
from apps.catalog.templates import (
    FreshnessProps,
    SearchItemProps,
    SectionProps,
    SlideProps,
    SongDetailPage,
)

PUBLIC_DEFAULT_PAGE_SIZE = 20
PUBLIC_MAX_PAGE_SIZE = 50
PUBLIC_MAX_QUERY_LENGTH = 128
LYRIC_PREVIEW_LINES = 3
LYRIC_PREVIEW_CHARACTERS = 180
SEARCH_WORD_PATTERN = re.compile(r"[\w]+", re.UNICODE)


def _freshness(value: datetime | None) -> FreshnessProps | None:
    if value is None:
        return None
    local_value = timezone.localtime(value)
    elapsed = timesince(value, timezone.now(), depth=1)
    return FreshnessProps(
        value.isoformat(),
        local_value.strftime("%B %-d, %Y at %-I:%M %p %Z"),
        "just now" if not elapsed or elapsed.startswith("0") else f"{elapsed} ago",
    )


def _author(authors: list[str]) -> str:
    return ", ".join(author.strip() for author in authors if author.strip()) or "N/A"


def _search_word(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(
        char for char in decomposed if not unicodedata.combining(char)
    ).casefold()


def _matching_span(line: str, terms: set[str]) -> tuple[int, int] | None:
    for match in SEARCH_WORD_PATTERN.finditer(line):
        if _search_word(match.group()) in terms:
            return match.span()
    return None


def _excerpt(line: str, limit: int, terms: set[str]) -> str:
    if len(line) <= limit:
        return line
    match = _matching_span(line, terms)
    if match is None:
        return f"{line[: max(limit - 1, 1)].rstrip()}…"
    start, end = match
    content_limit = max(limit - 2, end - start)
    start = max(0, start - max((content_limit - (end - start)) // 2, 0))
    end = min(len(line), start + content_limit)
    if end == len(line):
        start = max(0, end - content_limit)
    prefix, suffix = ("…" if start else ""), ("…" if end < len(line) else "")
    excerpt = line[start:end].strip()
    while len(prefix) + len(excerpt) + len(suffix) > limit and excerpt:
        excerpt = excerpt[:-1].rstrip()
    return f"{prefix}{excerpt}{suffix}"


def _preview(lyrics: str, query: str) -> list[str]:
    lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
    terms = {_search_word(match.group()) for match in SEARCH_WORD_PATTERN.finditer(query)}
    if terms:
        matched = [
            index for index, line in enumerate(lines) if _matching_span(line, terms)
        ]
        selected = matched[:LYRIC_PREVIEW_LINES]
        if selected:
            nearby = sorted(
                (index for index in range(len(lines)) if index not in selected),
                key=lambda index: (min(abs(index - found) for found in matched), index),
            )
            lines = [
                lines[index]
                for index in sorted(
                    selected + nearby[: LYRIC_PREVIEW_LINES - len(selected)]
                )
            ]
    preview, remaining = [], LYRIC_PREVIEW_CHARACTERS
    for line in lines[:LYRIC_PREVIEW_LINES]:
        if remaining <= 0:
            break
        limit = (
            remaining // (min(LYRIC_PREVIEW_LINES, len(lines)) - len(preview))
            if terms
            else remaining
        )
        line = _excerpt(line, limit, terms)
        preview.append(line)
        remaining -= len(line)
    return preview


def _search_url(
    *, query: str, mode: str, limit: int, continuation: str | None = None
) -> str:
    parameters = {"q": query, "mode": mode}
    if limit != PUBLIC_DEFAULT_PAGE_SIZE:
        parameters["limit"] = str(limit)
    if continuation:
        parameters["next"] = continuation
    return f"{reverse('catalog:search')}?{urlencode(parameters)}"


def restart_url(restart: SearchRestart | None) -> str | None:
    if restart is None:
        return None
    return _search_url(query=restart.query, mode=restart.mode, limit=restart.limit)


def present_search(
    result: CatalogSearchPage | None,
    *,
    query: str,
    mode: str,
    limit: int,
    error: str | None = None,
    restart: SearchRestart | None = None,
) -> CatalogSearchTemplate:
    """Map a typed Catalog search result to Reactivated props."""

    normalized_query = query.strip()
    safe_mode = mode if mode in {"title", "lyrics"} else "title"
    items = []
    if result and normalized_query:
        items = [
            SearchItemProps(
                song_uid=item.song_uid,
                url=reverse("catalog:detail", kwargs={"song_uid": item.song_uid}),
                title=item.title,
                author=_author(item.authors),
                lyric_preview=_preview(item.cleaned_lyrics or "", normalized_query)
                if item.lyrics_available and safe_mode == "lyrics"
                else [],
                lyrics_available=item.lyrics_available,
                rights_status=item.rights_status,
                song_freshness=_freshness(item.content_changed_at),
            )
            for item in result.items
        ]
    return CatalogSearchTemplate(
        title="Song Catalog",
        query=query,
        mode=safe_mode,
        limit=limit,
        searched=bool(normalized_query),
        results=items,
        catalog_freshness=_freshness(result.snapshot_completed_at) if result else None,
        next_url=_search_url(
            query=normalized_query,
            mode=safe_mode,
            limit=limit,
            continuation=result.continuation,
        )
        if result and normalized_query and result.continuation
        else None,
        has_more=bool(result and normalized_query and result.has_more),
        error=error,
        restart_url=restart_url(restart),
    )


def _display_label(label: str) -> str:
    common = {
        "verse": "Verse",
        "chorus": "Chorus",
        "bridge": "Bridge",
        "pre-chorus": "Pre-Chorus",
        "intro": "Intro",
        "interlude": "Interlude",
        "tag": "Tag",
        "ending": "Ending",
    }
    return common.get(label.strip().casefold(), label.strip() or "Section")


def present_song(song: CatalogSong) -> SongDetailPage:
    """Map a typed Catalog song to Reactivated props."""

    sections, slides = [], []
    for section in song.sections:
        label = _display_label(section.label)
        lines = [line for slide in section.slides for line in slide]
        sections.append(SectionProps(section.position, label, "\n".join(lines)))
        slides.extend(
            SlideProps(len(slides) + 1, label, slide) for slide in section.slides
        )
    if not slides and song.cleaned_lyrics:
        lines = [
            line.strip() for line in song.cleaned_lyrics.splitlines() if line.strip()
        ]
        sections, slides = (
            [SectionProps(1, "Song", "\n".join(lines))],
            [SlideProps(1, "Song", lines)],
        )
    freshness = _freshness(song.content_changed_at)
    assert freshness is not None
    return SongDetailPage(
        song.title,
        _author(song.authors),
        song.copyright_notice,
        song.rights_status,
        song.lyrics_available,
        sections,
        slides,
        len(slides),
        freshness,
        _freshness(song.snapshot_completed_at),
        reverse("catalog:search"),
    )
