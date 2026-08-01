from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode
from uuid import UUID

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
SEARCH_PATH = "/api/v1/catalog/search"
CURSOR_KEYS = {
    "version",
    "snapshot_id",
    "query",
    "mode",
    "limit",
    "strategy",
    "restricted_lyrics",
    "last_title",
    "last_song_uid",
}


class CatalogReadError(ValueError):
    """A read request cannot be fulfilled with the supplied client state."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        restart_url: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.restart_url = restart_url


@dataclass(frozen=True, slots=True)
class SearchPage:
    """One stable page of Song Catalog entries."""

    entries: list[CatalogEntry]
    next_url: str | None
    has_more: bool


def build_search_url(
    *, query: str, mode: str, limit: int, cursor: str | None = None
) -> str:
    """Build a server-owned search or restart URL."""

    parameters = {"q": query, "mode": mode, "limit": str(limit)}
    if cursor:
        parameters["next"] = cursor
    return f"{SEARCH_PATH}?{urlencode(parameters)}"


def _validate_request(query: str, mode: str, limit: int) -> tuple[str, str, int]:
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
    if mode == "lyrics" and len(normalized_query) < 3:
        raise CatalogReadError(
            "lyrics_query_too_short",
            "Lyrics search requires at least three non-whitespace characters.",
            400,
        )
    return normalized_query, mode, limit


def _safe_restart_url(payload) -> str:
    if not isinstance(payload, dict):
        return build_search_url(query="", mode="title", limit=20)
    query = payload.get("query")
    mode = payload.get("mode")
    limit = payload.get("limit")
    if (
        not isinstance(query, str)
        or mode not in {"title", "lyrics"}
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_PAGE_SIZE
    ):
        return build_search_url(query="", mode="title", limit=20)
    return build_search_url(query=query, mode=mode, limit=limit)


def _validate_cursor_payload(payload) -> dict:
    if not isinstance(payload, dict) or set(payload) != CURSOR_KEYS:
        raise CatalogReadError(
            "invalid_cursor",
            "The continuation URL is malformed or has been tampered with.",
            400,
        )
    if (
        payload["version"] != CURSOR_VERSION
        or payload["mode"] not in {"title", "lyrics"}
        or payload["strategy"] not in {"all", "fts", "trigram"}
        or not isinstance(payload["query"], str)
        or not isinstance(payload["limit"], int)
        or not isinstance(payload["restricted_lyrics"], bool)
        or not isinstance(payload["last_title"], str)
        or not isinstance(payload["last_song_uid"], str)
    ):
        raise CatalogReadError(
            "invalid_cursor",
            "The continuation URL is malformed or has been tampered with.",
            400,
        )
    try:
        UUID(str(payload["snapshot_id"]))
    except (TypeError, ValueError) as exc:
        raise CatalogReadError(
            "invalid_cursor",
            "The continuation URL is malformed or has been tampered with.",
            400,
        ) from exc
    return payload


def _decode_cursor(token: str) -> dict:
    if not token or len(token) > 4096:
        raise CatalogReadError(
            "invalid_cursor",
            "The continuation URL is malformed or has been tampered with.",
            400,
        )
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
            restart_url=_safe_restart_url(expired_payload),
        ) from exc
    except signing.BadSignature as exc:
        raise CatalogReadError(
            "invalid_cursor",
            "The continuation URL is malformed or has been tampered with.",
            400,
        ) from exc
    return _validate_cursor_payload(payload)


def _active_snapshot() -> CatalogSnapshot | None:
    state = CatalogState.objects.select_related("active_snapshot").filter(pk=1).first()
    return state.active_snapshot if state else None


def _snapshot_for_cursor(payload: dict) -> CatalogSnapshot:
    snapshot = CatalogSnapshot.objects.filter(
        pk=payload["snapshot_id"],
        status=SnapshotStatus.COMPLETED,
    ).first()
    if snapshot is None:
        raise CatalogReadError(
            "cursor_expired",
            "The catalog snapshot for this continuation is no longer retained.",
            410,
            restart_url=_safe_restart_url(payload),
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


def search_catalog(
    *,
    query: str = "",
    mode: str = "title",
    limit: int = 20,
    continuation: str | None = None,
    include_restricted_lyrics: bool = False,
) -> SearchPage:
    """Search one pinned Song Catalog snapshot with stable keyset pagination."""

    query, mode, limit = _validate_request(query, mode, limit)
    include_restricted_lyrics = mode == "lyrics" and include_restricted_lyrics
    payload = _decode_cursor(continuation) if continuation else None
    if payload:
        if (
            payload["query"] != query
            or payload["mode"] != mode
            or payload["limit"] != limit
            or payload["restricted_lyrics"] != include_restricted_lyrics
        ):
            raise CatalogReadError(
                "cursor_query_mismatch",
                "The continuation does not belong to this query, mode, and limit.",
                400,
            )
        snapshot = _snapshot_for_cursor(payload)
        strategy = payload["strategy"]
    else:
        snapshot = _active_snapshot()
        strategy = "all" if not query else "fts"

    if snapshot is None:
        return SearchPage(entries=[], next_url=None, has_more=False)

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
            Q(normalized_title__gt=payload["last_title"])
            | Q(
                normalized_title=payload["last_title"],
                song_uid__gt=payload["last_song_uid"],
            )
        )

    page_entries = list(entries.order_by("normalized_title", "song_uid")[: limit + 1])
    has_more = len(page_entries) > limit
    page_entries = page_entries[:limit]
    next_url = None
    if has_more:
        last_entry = page_entries[-1]
        next_payload = {
            "version": CURSOR_VERSION,
            "snapshot_id": str(snapshot.pk),
            "query": query,
            "mode": mode,
            "limit": limit,
            "strategy": strategy,
            "restricted_lyrics": include_restricted_lyrics,
            "last_title": last_entry.normalized_title,
            "last_song_uid": last_entry.song_uid,
        }
        token = signing.dumps(next_payload, salt=CURSOR_SALT, compress=True)
        next_url = build_search_url(
            query=query,
            mode=mode,
            limit=limit,
            cursor=token,
        )
    return SearchPage(entries=page_entries, next_url=next_url, has_more=has_more)


def get_active_entry(song_uid: str) -> CatalogEntry:
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
