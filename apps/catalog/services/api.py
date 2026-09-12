from __future__ import annotations

from dataclasses import dataclass

from apps.api_keys.models import APIKeyScope
from apps.api_keys.services import (
    AuthorizationDenied,
    RateLimitOutcome,
    authorize_api_key,
    check_rate_limit,
)

from .importing import ImportRejected, ImportResult, import_package
from .search import (
    CatalogAccess,
    CatalogReadError,
    CatalogSearchPage,
    CatalogSong,
    GetCatalogSong,
    SearchCatalog,
    SearchRestart,
    get_catalog_song,
    search_catalog,
)

SEARCH_RATE_LIMIT = 60


@dataclass(frozen=True, slots=True)
class SearchCatalogRequest:
    """Input bound from an Integration Client search request."""

    query: str
    mode: str
    limit: int
    continuation: str | None
    authorization: str
    rate_limit: int = SEARCH_RATE_LIMIT


@dataclass(frozen=True, slots=True)
class CatalogAPIError:
    """A transport-neutral Catalog API failure."""

    code: str
    message: str
    restart: SearchRestart | None = None
    rate: RateLimitOutcome | None = None


@dataclass(frozen=True, slots=True)
class SearchCatalogResult:
    """A search result and its rate-limit facts."""

    page: CatalogSearchPage
    limit: int
    remaining: int
    reset_at: int
    may_read_restricted_lyrics: bool


@dataclass(frozen=True, slots=True)
class ReadCatalogSongRequest:
    song_uid: str
    authorization: str
    include_lyrics: bool
    rate_limit: int


@dataclass(frozen=True, slots=True)
class ReadCatalogSongResult:
    song: CatalogSong
    limit: int
    remaining: int
    reset_at: int
    may_read_restricted_lyrics: bool


@dataclass(frozen=True, slots=True)
class ImportCatalogRequest:
    """Input bound from an Integration Client import request."""

    package: bytes
    events: bytes
    trigger: str
    authorization: str


@dataclass(frozen=True, slots=True)
class ImportCatalogResult:
    """A completed or idempotent Catalog Import outcome."""

    result: ImportResult


def search_for_client(
    request: SearchCatalogRequest,
) -> SearchCatalogResult | CatalogAPIError:
    """Authorize, rate-limit, and execute one Integration Client search."""

    scopes = [APIKeyScope.CATALOG_SEARCH]
    if request.mode == "lyrics":
        scopes.append(APIKeyScope.LYRICS_READ)
    authorized = authorize_api_key(request.authorization, required_scopes=scopes)
    if isinstance(authorized, AuthorizationDenied):
        return CatalogAPIError(authorized.code, authorized.message)

    rate = check_rate_limit(
        authorized.api_key,
        bucket="catalog.search",
        limit=request.rate_limit,
    )
    if not rate.allowed:
        return CatalogAPIError(
            "rate_limited",
            "The Integration Client rate limit has been reached.",
            rate=rate,
        )
    if request.mode == "lyrics" and len(request.query.strip()) < 3:
        return CatalogAPIError(
            "lyrics_query_too_short",
            "Lyrics search requires at least 3 non-whitespace characters.",
        )
    try:
        page = search_catalog(
            SearchCatalog(
                query=request.query,
                mode=request.mode,
                limit=request.limit,
                continuation=request.continuation,
                access=CatalogAccess(
                    may_read_lyrics=True,
                    may_read_restricted_lyrics=(
                        APIKeyScope.RESTRICTED_LYRICS_READ in authorized.api_key.scopes
                    ),
                ),
            )
        )
    except CatalogReadError as exc:
        return CatalogAPIError(exc.code, exc.message, exc.restart)
    return SearchCatalogResult(
        page,
        rate.limit,
        rate.remaining,
        rate.reset_at,
        APIKeyScope.RESTRICTED_LYRICS_READ in authorized.api_key.scopes,
    )


def read_song_for_client(
    request: ReadCatalogSongRequest,
) -> ReadCatalogSongResult | CatalogAPIError:
    """Authorize, rate-limit, and read one Integration Client song resource."""

    scope = APIKeyScope.LYRICS_READ if request.include_lyrics else APIKeyScope.SONG_READ
    authorized = authorize_api_key(request.authorization, required_scopes=[scope])
    if isinstance(authorized, AuthorizationDenied):
        return CatalogAPIError(authorized.code, authorized.message)
    rate = check_rate_limit(
        authorized.api_key,
        bucket="catalog.lyrics" if request.include_lyrics else "catalog.song",
        limit=request.rate_limit,
    )
    if not rate.allowed:
        return CatalogAPIError(
            "rate_limited",
            "The Integration Client rate limit has been reached.",
            rate=rate,
        )
    restricted = APIKeyScope.RESTRICTED_LYRICS_READ in authorized.api_key.scopes
    try:
        song = get_catalog_song(
            GetCatalogSong(
                request.song_uid, CatalogAccess(request.include_lyrics, restricted)
            )
        )
    except CatalogReadError as exc:
        return CatalogAPIError(exc.code, exc.message)
    if request.include_lyrics and song.rights_status == "restricted" and not restricted:
        return CatalogAPIError(
            "restricted_lyrics_forbidden",
            "This key is not permitted to read restricted lyrics.",
        )
    return ReadCatalogSongResult(
        song, rate.limit, rate.remaining, rate.reset_at, restricted
    )


def import_for_client(
    request: ImportCatalogRequest,
) -> ImportCatalogResult | CatalogAPIError:
    """Authorize and process one Integration Client Catalog Import."""

    authorized = authorize_api_key(
        request.authorization, required_scopes=[APIKeyScope.CATALOG_IMPORT]
    )
    if isinstance(authorized, AuthorizationDenied):
        return CatalogAPIError(authorized.code, authorized.message)
    try:
        result = import_package(
            request.package, exporter_events=request.events, trigger=request.trigger
        )
    except ImportRejected as exc:
        return CatalogAPIError(exc.code, exc.summary)
    return ImportCatalogResult(result)
