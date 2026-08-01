from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlsplit

from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince

from apps.catalog.models import CatalogEntry, CatalogSnapshot, CatalogState, RightsStatus
from apps.catalog.search import CatalogReadError, get_active_entry, search_catalog

PUBLIC_DEFAULT_PAGE_SIZE = 20
PUBLIC_MAX_PAGE_SIZE = 50
PUBLIC_MAX_QUERY_LENGTH = 128
LYRIC_PREVIEW_LINES = 3
LYRIC_PREVIEW_CHARACTERS = 180


@dataclass(frozen=True, slots=True)
class Freshness:
    """Human- and machine-readable presentation of catalog recency."""

    iso: str
    absolute: str
    relative: str


@dataclass(frozen=True, slots=True)
class PublicSearchItem:
    """Rights-filtered catalog result safe to serialize into a public page."""

    song_uid: str
    url: str
    title: str
    author: str
    lyric_preview: list[str]
    lyrics_available: bool
    rights_status: str
    song_freshness: Freshness


@dataclass(frozen=True, slots=True)
class PublicSearchResult:
    """One snapshot-pinned public result page."""

    items: list[PublicSearchItem]
    catalog_freshness: Freshness | None
    next_url: str | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class PublicSection:
    """One source-ordered Song Section for readable Song Detail."""

    position: int
    label: str
    text: str


@dataclass(frozen=True, slots=True)
class PublicSlide:
    """One source-ordered projection slide."""

    position: int
    section_label: str
    lines: list[str]


@dataclass(frozen=True, slots=True)
class PublicSongDetail:
    """Rights-filtered detail presentation for a Catalog Visitor."""

    song_uid: str
    title: str
    authors: list[str]
    author: str
    copyright_notice: str
    rights_status: str
    lyrics_available: bool
    sections: list[PublicSection]
    slides: list[PublicSlide]
    slide_count: int
    song_freshness: Freshness
    catalog_freshness: Freshness | None


def _freshness(value: datetime | None) -> Freshness | None:
    if value is None:
        return None
    local_value = timezone.localtime(value)
    elapsed = timesince(value, timezone.now(), depth=1)
    return Freshness(
        iso=value.isoformat(),
        absolute=local_value.strftime("%B %-d, %Y at %-I:%M %p %Z"),
        relative=(
            "just now" if not elapsed or elapsed.startswith("0") else f"{elapsed} ago"
        ),
    )


def _active_snapshot() -> CatalogSnapshot | None:
    state = CatalogState.objects.select_related("active_snapshot").filter(pk=1).first()
    return state.active_snapshot if state else None


def _author(entry: CatalogEntry) -> str:
    authors = [str(author).strip() for author in entry.authors if str(author).strip()]
    return ", ".join(authors) if authors else "N/A"


def _preview(lyrics: str) -> list[str]:
    lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
    preview: list[str] = []
    remaining = LYRIC_PREVIEW_CHARACTERS
    for line in lines[:LYRIC_PREVIEW_LINES]:
        if remaining <= 0:
            break
        if len(line) > remaining:
            line = f"{line[: max(remaining - 1, 1)].rstrip()}…"
        preview.append(line)
        remaining -= len(line)
    return preview


def _public_search_url(
    *, query: str, mode: str, limit: int, continuation: str | None = None
) -> str:
    parameters = {"q": query, "mode": mode}
    if limit != PUBLIC_DEFAULT_PAGE_SIZE:
        parameters["limit"] = str(limit)
    if continuation:
        parameters["next"] = continuation
    return f"{reverse('catalog:search')}?{urlencode(parameters)}"


def _continuation(next_url: str | None) -> str | None:
    if not next_url:
        return None
    values = parse_qs(urlsplit(next_url).query)
    return values.get("next", [None])[0]


def parse_public_limit(raw_limit: str | None) -> int:
    """Validate a public page size without leaking ORM coercion errors."""

    if raw_limit in {None, ""}:
        return PUBLIC_DEFAULT_PAGE_SIZE
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise CatalogReadError(
            "invalid_limit",
            f"Results per page must be between 1 and {PUBLIC_MAX_PAGE_SIZE}.",
            400,
        ) from exc
    if not 1 <= limit <= PUBLIC_MAX_PAGE_SIZE:
        raise CatalogReadError(
            "invalid_limit",
            f"Results per page must be between 1 and {PUBLIC_MAX_PAGE_SIZE}.",
            400,
        )
    return limit


def search_public_catalog(
    *,
    query: str,
    mode: str,
    limit: int,
    continuation: str | None,
) -> PublicSearchResult:
    """Search the public catalog while enforcing browser-specific constraints."""

    normalized_query = query.strip()
    if len(normalized_query) > PUBLIC_MAX_QUERY_LENGTH:
        raise CatalogReadError(
            "query_too_long",
            f"Search terms may contain at most {PUBLIC_MAX_QUERY_LENGTH} characters.",
            400,
        )
    if mode not in {"title", "lyrics"}:
        raise CatalogReadError(
            "invalid_mode",
            "Choose either Title or Lyrics search.",
            400,
        )
    if not normalized_query:
        if continuation:
            raise CatalogReadError(
                "cursor_query_mismatch",
                "This continuation does not belong to an empty search.",
                400,
            )
        snapshot = _active_snapshot()
        return PublicSearchResult(
            items=[],
            catalog_freshness=_freshness(snapshot.completed_at) if snapshot else None,
            next_url=None,
            has_more=False,
        )

    page = search_catalog(
        query=normalized_query,
        mode=mode,
        limit=limit,
        continuation=continuation,
        minimum_lyrics_query_length=1,
    )
    items = []
    for entry in page.entries:
        lyrics_available = entry.rights_status != RightsStatus.RESTRICTED
        song_freshness = _freshness(entry.content_changed_at)
        assert song_freshness is not None
        items.append(
            PublicSearchItem(
                song_uid=entry.song_uid,
                url=reverse("catalog:detail", kwargs={"song_uid": entry.song_uid}),
                title=entry.title,
                author=_author(entry),
                lyric_preview=_preview(entry.cleaned_lyrics) if lyrics_available else [],
                lyrics_available=lyrics_available,
                rights_status=entry.rights_status,
                song_freshness=song_freshness,
            )
        )
    token = _continuation(page.next_url)
    return PublicSearchResult(
        items=items,
        catalog_freshness=(
            _freshness(page.snapshot.completed_at) if page.snapshot else None
        ),
        next_url=(
            _public_search_url(
                query=normalized_query,
                mode=mode,
                limit=limit,
                continuation=token,
            )
            if token
            else None
        ),
        has_more=page.has_more,
    )


def public_restart_url(*, query: str, mode: str, limit: int) -> str:
    """Return a safe browser restart URL after a stale continuation."""

    safe_mode = mode if mode in {"title", "lyrics"} else "title"
    safe_query = query.strip()[:PUBLIC_MAX_QUERY_LENGTH]
    safe_limit = limit if 1 <= limit <= PUBLIC_MAX_PAGE_SIZE else PUBLIC_DEFAULT_PAGE_SIZE
    return _public_search_url(query=safe_query, mode=safe_mode, limit=safe_limit)


def _display_label(label: object) -> str:
    value = str(label or "").strip()
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
    return common.get(value.casefold(), value or "Section")


def _song_structure(entry: CatalogEntry) -> tuple[list[PublicSection], list[PublicSlide]]:
    sections: list[PublicSection] = []
    slides: list[PublicSlide] = []
    for section_index, raw_section in enumerate(entry.sections, start=1):
        if not isinstance(raw_section, dict):
            continue
        label = _display_label(raw_section.get("label"))
        raw_slides = raw_section.get("slides", [])
        section_lines: list[str] = []
        if not isinstance(raw_slides, list):
            raw_slides = []
        for raw_slide in raw_slides:
            if not isinstance(raw_slide, dict):
                continue
            raw_lines = raw_slide.get("lines", [])
            lines = (
                [str(line).strip() for line in raw_lines if str(line).strip()]
                if isinstance(raw_lines, list)
                else []
            )
            if not lines:
                continue
            section_lines.extend(lines)
            slides.append(
                PublicSlide(
                    position=len(slides) + 1,
                    section_label=label,
                    lines=lines,
                )
            )
        sections.append(
            PublicSection(
                position=int(raw_section.get("position") or section_index),
                label=label,
                text="\n".join(section_lines),
            )
        )
    if not slides and entry.cleaned_lyrics.strip():
        fallback_lines = [
            line.strip() for line in entry.cleaned_lyrics.splitlines() if line.strip()
        ]
        slides = [PublicSlide(position=1, section_label="Song", lines=fallback_lines)]
        sections = [
            PublicSection(position=1, label="Song", text="\n".join(fallback_lines))
        ]
    return sections, slides


def get_public_song(song_uid: str) -> PublicSongDetail:
    """Return a public Song Detail with restricted lyric fields removed."""

    entry = get_active_entry(song_uid)
    lyrics_available = entry.rights_status != RightsStatus.RESTRICTED
    sections, slides = _song_structure(entry) if lyrics_available else ([], [])
    return PublicSongDetail(
        song_uid=entry.song_uid,
        title=entry.title,
        authors=[str(author) for author in entry.authors if str(author).strip()],
        author=_author(entry),
        copyright_notice=entry.copyright_notice,
        rights_status=entry.rights_status,
        lyrics_available=lyrics_available,
        sections=sections,
        slides=slides,
        slide_count=len(slides),
        song_freshness=_freshness(entry.content_changed_at),
        catalog_freshness=_freshness(entry.snapshot.completed_at),
    )
