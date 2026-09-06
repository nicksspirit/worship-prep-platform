from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

import msgspec
from django.contrib.postgres.search import SearchQuery
from django.core import signing
from django.db.models import Q, QuerySet

from apps.catalog.models import (
    CatalogEntry,
    CatalogSnapshot,
    CatalogState,
    RightsStatus,
    SnapshotStatus,
)
from apps.catalog.text import SEARCH_CONFIG, normalize_title

CURSOR_MAX_AGE_SECONDS = 24 * 60 * 60
CURSOR_SALT = "worship-prep-platform.catalog-search.v1"
CURSOR_VERSION = 1
MAX_QUERY_LENGTH = 200
MAX_PAGE_SIZE = 100
SearchMode = Literal["title", "lyrics"]
SearchStrategy = Literal["all", "fts", "trigram"]


class CatalogAccess(msgspec.Struct, frozen=True):
    """Lyrics capabilities established by the calling adapter."""

    may_read_lyrics: bool
    may_read_restricted_lyrics: bool


class SearchCatalog(msgspec.Struct, frozen=True):
    """Request one stable Song Catalog search page."""

    query: str = ""
    mode: SearchMode = "title"
    limit: int = 20
    continuation: str | None = None
    access: CatalogAccess = CatalogAccess(True, False)


class CatalogSearchItem(msgspec.Struct, frozen=True):
    """A rights-safe item from a Song Catalog search."""

    song_uid: str
    title: str
    authors: list[str]
    copyright_notice: str
    slide_count: int
    content_changed_at: datetime
    rights_status: str
    lyrics_available: bool
    cleaned_lyrics: str | None


class CatalogSearchPage(msgspec.Struct, frozen=True):
    """One stable, typed page of Song Catalog search results."""

    items: list[CatalogSearchItem]
    snapshot_completed_at: datetime | None
    continuation: str | None
    has_more: bool


class SearchRestart(msgspec.Struct, frozen=True):
    """Safe state from which an adapter can build a restart link."""

    query: str
    mode: SearchMode
    limit: int


class GetCatalogSong(msgspec.Struct, frozen=True):
    """Request one active Song Catalog entry."""

    song_uid: str
    access: CatalogAccess


class CatalogSongSection(msgspec.Struct, frozen=True):
    position: int
    label: str
    slides: list[list[str]]


class CatalogSong(msgspec.Struct, frozen=True):
    song_uid: str
    title: str
    authors: list[str]
    copyright_notice: str
    slide_count: int
    content_changed_at: datetime
    snapshot_completed_at: datetime | None
    rights_status: str
    lyrics_available: bool
    cleaned_lyrics: str | None
    sections: list[CatalogSongSection]


class _CursorPayloadV1(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    version: Literal[1]
    snapshot_id: UUID
    query: str
    mode: SearchMode
    limit: int
    strategy: SearchStrategy
    restricted_lyrics: bool
    last_title: str
    last_song_uid: str


class CatalogReadError(ValueError):
    """A read request cannot be fulfilled with the supplied client state."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        restart: SearchRestart | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.restart = restart


def _validate_request(
    query: str,
    mode: str,
    limit: int,
) -> tuple[str, str, int]:
    normalized_query = str(query or "").strip()
    if len(normalized_query) > MAX_QUERY_LENGTH:
        raise CatalogReadError(
            "query_too_long",
            f"Search queries may contain at most {MAX_QUERY_LENGTH} characters.",
            400,
        )
    if mode not in {"title", "lyrics"}:
        raise CatalogReadError(
            "invalid_mode",
            "Search mode must be either 'title' or 'lyrics'.",
            400,
        )
    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise CatalogReadError(
            "invalid_limit",
            f"Search limit must be between 1 and {MAX_PAGE_SIZE}.",
            400,
        )
    if mode == "lyrics" and len(normalized_query) < 1:
        raise CatalogReadError(
            "lyrics_query_too_short",
            "Lyrics search requires at least 1 non-whitespace character.",
            400,
        )
    return normalized_query, mode, limit


def _safe_restart(payload: object) -> SearchRestart:
    if not isinstance(payload, dict):
        return SearchRestart(query="", mode="title", limit=20)
    query = payload.get("query")
    mode = payload.get("mode")
    limit = payload.get("limit")
    if (
        not isinstance(query, str)
        or mode not in {"title", "lyrics"}
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_PAGE_SIZE
    ):
        return SearchRestart(query="", mode="title", limit=20)
    return SearchRestart(query=query, mode=mode, limit=limit)


def _invalid_cursor() -> CatalogReadError:
    return CatalogReadError(
        "invalid_cursor",
        "The continuation URL is malformed or has been tampered with.",
        400,
    )


def _decode_cursor(token: str) -> _CursorPayloadV1:
    if not token or len(token) > 4096:
        raise _invalid_cursor()
    try:
        payload = signing.loads(
            token,
            salt=CURSOR_SALT,
            max_age=CURSOR_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        try:
            expired_payload = signing.loads(token, salt=CURSOR_SALT)
        except signing.BadSignature:
            expired_payload = None
        raise CatalogReadError(
            "cursor_expired",
            "This continuation has expired; restart the search.",
            410,
            restart=_safe_restart(expired_payload),
        ) from exc
    except signing.BadSignature as exc:
        raise _invalid_cursor() from exc
    try:
        return msgspec.convert(payload, type=_CursorPayloadV1, strict=True)
    except (msgspec.ValidationError, TypeError) as exc:
        raise _invalid_cursor() from exc


def _active_snapshot() -> CatalogSnapshot | None:
    state = CatalogState.objects.select_related("active_snapshot").filter(pk=1).first()
    return state.active_snapshot if state else None


def _snapshot_for_cursor(payload: _CursorPayloadV1) -> CatalogSnapshot:
    snapshot = CatalogSnapshot.objects.filter(
        pk=payload.snapshot_id,
        status=SnapshotStatus.COMPLETED,
    ).first()
    if snapshot is None:
        raise CatalogReadError(
            "cursor_expired",
            "The catalog snapshot for this continuation is no longer retained.",
            410,
            restart=_safe_restart(msgspec.to_builtins(payload)),
        )
    return snapshot


def _filter_search(
    entries: QuerySet[CatalogEntry],
    *,
    query: str,
    mode: str,
    strategy: str,
    include_restricted_lyrics: bool,
) -> QuerySet[CatalogEntry]:
    if strategy == "all":
        return entries
    if mode == "lyrics":
        if not include_restricted_lyrics:
            entries = entries.exclude(rights_status=RightsStatus.RESTRICTED)
        return entries.filter(
            lyrics_search=SearchQuery(
                query,
                config=SEARCH_CONFIG,
                search_type="plain",
            )
        )
    if strategy == "fts":
        return entries.filter(
            title_search=SearchQuery(
                query,
                config=SEARCH_CONFIG,
                search_type="plain",
            )
        )
    return entries.filter(
        normalized_title__trigram_similar=normalize_title(query)
    )


def search_catalog(request: SearchCatalog) -> CatalogSearchPage:
    """Search one pinned Song Catalog snapshot with stable keyset pagination."""

    query, mode, limit = _validate_request(request.query, request.mode, request.limit)
    include_restricted_lyrics = (
        mode == "lyrics" and request.access.may_read_restricted_lyrics
    )
    payload = _decode_cursor(request.continuation) if request.continuation else None
    if payload:
        if (
            payload.query != query
            or payload.mode != mode
            or payload.limit != limit
            or payload.restricted_lyrics != include_restricted_lyrics
        ):
            raise CatalogReadError(
                "cursor_query_mismatch",
                "The continuation does not belong to this query, mode, and limit.",
                400,
            )
        snapshot = _snapshot_for_cursor(payload)
        strategy = payload.strategy
    else:
        snapshot = _active_snapshot()
        strategy = "all" if not query else "fts"

    if snapshot is None:
        return CatalogSearchPage(
            items=[],
            snapshot_completed_at=None,
            continuation=None,
            has_more=False,
        )

    entries = CatalogEntry.objects.filter(snapshot=snapshot)
    entries = _filter_search(
        entries,
        query=query,
        mode=mode,
        strategy=strategy,
        include_restricted_lyrics=include_restricted_lyrics,
    )
    if not payload and mode == "title" and query and not entries.exists():
        strategy = "trigram"
        entries = _filter_search(
            CatalogEntry.objects.filter(snapshot=snapshot),
            query=query,
            mode=mode,
            strategy=strategy,
            include_restricted_lyrics=include_restricted_lyrics,
        )
    if payload:
        entries = entries.filter(
            Q(normalized_title__gt=payload.last_title)
            | Q(
                normalized_title=payload.last_title,
                song_uid__gt=payload.last_song_uid,
            )
        )

    page_entries = list(entries.order_by("normalized_title", "song_uid")[: limit + 1])
    has_more = len(page_entries) > limit
    page_entries = page_entries[:limit]
    continuation = None
    if has_more:
        last_entry = page_entries[-1]
        next_payload = _CursorPayloadV1(
            version=CURSOR_VERSION,
            snapshot_id=snapshot.pk,
            query=query,
            mode=mode,
            limit=limit,
            strategy=strategy,
            restricted_lyrics=include_restricted_lyrics,
            last_title=last_entry.normalized_title,
            last_song_uid=last_entry.song_uid,
        )
        continuation = signing.dumps(
            msgspec.to_builtins(next_payload), salt=CURSOR_SALT, compress=True
        )
    return CatalogSearchPage(
        items=[_search_item(entry) for entry in page_entries],
        snapshot_completed_at=snapshot.completed_at,
        continuation=continuation,
        has_more=has_more,
    )


def _search_item(entry: CatalogEntry) -> CatalogSearchItem:
    return CatalogSearchItem(
        song_uid=entry.song_uid,
        title=entry.title,
        authors=[str(author) for author in entry.authors if str(author).strip()],
        copyright_notice=entry.copyright_notice,
        slide_count=entry.slide_count,
        content_changed_at=entry.content_changed_at,
        rights_status=entry.rights_status,
        lyrics_available=entry.rights_status != RightsStatus.RESTRICTED,
        cleaned_lyrics=(
            entry.cleaned_lyrics
            if entry.rights_status != RightsStatus.RESTRICTED
            else None
        ),
    )


def _find_active_entry(song_uid: str) -> CatalogEntry:
    """Resolve a stable song identity through the active Song Catalog pointer."""

    snapshot = _active_snapshot()
    entry = (
        CatalogEntry.objects.filter(snapshot=snapshot, song_uid=song_uid).first()
        if snapshot
        else None
    )
    if entry is None:
        raise CatalogReadError(
            "song_not_found",
            "No song with that identity exists in the active Song Catalog.",
            404,
        )
    return entry


def get_catalog_song(request: GetCatalogSong) -> CatalogSong:
    """Return one active Song Catalog entry with rights-safe lyric fields."""

    entry = _find_active_entry(request.song_uid)
    lyrics_available = entry.rights_status != RightsStatus.RESTRICTED or (
        request.access.may_read_restricted_lyrics
    )
    may_return_lyrics = request.access.may_read_lyrics and lyrics_available
    return CatalogSong(
        song_uid=entry.song_uid,
        title=entry.title,
        authors=[str(author) for author in entry.authors if str(author).strip()],
        copyright_notice=entry.copyright_notice,
        slide_count=entry.slide_count,
        content_changed_at=entry.content_changed_at,
        snapshot_completed_at=entry.snapshot.completed_at,
        rights_status=entry.rights_status,
        lyrics_available=may_return_lyrics,
        cleaned_lyrics=entry.cleaned_lyrics if may_return_lyrics else None,
        sections=_sections(entry) if may_return_lyrics else [],
    )


def _sections(entry: CatalogEntry) -> list[CatalogSongSection]:
    sections = []
    for index, section in enumerate(entry.sections, start=1):
        if not isinstance(section, dict):
            continue
        raw_slides = section.get("slides", [])
        slides = []
        if isinstance(raw_slides, list):
            for slide in raw_slides:
                if not isinstance(slide, dict):
                    continue
                raw_lines = slide.get("lines", [])
                if not isinstance(raw_lines, list):
                    continue
                lines = [str(line).strip() for line in raw_lines if str(line).strip()]
                if lines:
                    slides.append(lines)
        sections.append(
            CatalogSongSection(
                position=int(section.get("position") or index),
                label=str(section.get("label") or ""),
                slides=slides,
            )
        )
    return sections
