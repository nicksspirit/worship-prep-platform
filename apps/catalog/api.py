from typing import Annotated

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import connections
from django_bolt import (
    JSON,
    BoltAPI,
    OpenAPIConfig,
    RedocRenderPlugin,
    Response,
    SwaggerRenderPlugin,
    UploadFile,
)
from django_bolt.openapi.spec import Components, SecurityScheme
from django_bolt.param_functions import File, Header, Path, Query

from apps.api_keys.models import APIKeyScope
from apps.api_keys.services import (
    APIKeyAccessError,
    authorize_api_key,
    check_rate_limit,
)
from apps.catalog.importer import MAX_PACKAGE_BYTES, ImportRejected, import_package
from apps.catalog.models import CatalogEntry, RightsStatus
from apps.catalog.schema import (
    APIErrorDetail,
    APIErrorResponse,
    CatalogImportResponse,
    CatalogSearchResponse,
    CatalogSearchSong,
    SongLyricsResponse,
    SongLyricsSection,
    SongMetadataResponse,
)
from apps.catalog.search import CatalogReadError, get_active_entry, search_catalog

SEARCH_RATE_LIMIT = 60
LYRICS_RATE_LIMIT = 30
SONG_RATE_LIMIT = 60

documentation_plugins = (
    [SwaggerRenderPlugin(path="/swagger")]
    if settings.ENV == "local"
    else [RedocRenderPlugin(path="/redoc")]
)
api = BoltAPI(
    prefix="/api/v1/catalog",
    openapi_config=OpenAPIConfig(
        title="Worship Prep Song Catalog API",
        version="1.0.0",
        path="/api/v1/docs",
        description=(
            "Versioned read resources for Integration Clients. Send one-time-issued "
            "credentials as `Authorization: Bearer <key>`. Each operation documents "
            "its required scopes; restricted lyrics require the exceptional "
            "`catalog.lyrics.restricted` scope. Errors use "
            '`{"error": {"code": "...", "message": "..."}}`.'
        ),
        components=Components(
            security_schemes={
                "BearerAuth": SecurityScheme(
                    type="http",
                    scheme="bearer",
                    bearer_format="WPP Integration Client key",
                    description=(
                        "Hashed, scoped Integration Client key. Plaintext is shown only "
                        "when the key is issued."
                    ),
                )
            }
        ),
        security=[{"BearerAuth": []}],
        render_plugins=documentation_plugins,
    ),
)


def _raw_error(
    code: str,
    message: str,
    status_code: int,
    *,
    headers: dict[str, str] | None = None,
    restart_url: str | None = None,
):
    response = APIErrorResponse(
        error=APIErrorDetail(
            code=code,
            message=message,
            restart=restart_url,
        )
    )
    body = response.dump(exclude_none=True)
    response_headers = [("content-type", "application/json")]
    response_headers.extend((headers or {}).items())
    return status_code, response_headers, JSON(body).to_bytes()


def _authorize(authorization: str, *scopes: str):
    try:
        return authorize_api_key(authorization, required_scopes=scopes)
    except APIKeyAccessError as exc:
        return _raw_error(exc.code, exc.message, exc.status_code)


def _consume_rate(api_key, *, bucket: str, limit: int):
    rate = check_rate_limit(api_key, bucket=bucket, limit=limit)
    if not rate.allowed:
        return _raw_error(
            "rate_limited",
            "The Integration Client rate limit has been reached.",
            429,
            headers=rate.headers,
        )
    return rate


def _lyrics_access(entry: CatalogEntry, scopes: list[str]) -> str:
    if entry.rights_status != RightsStatus.RESTRICTED:
        return "available"
    if APIKeyScope.RESTRICTED_LYRICS_READ in scopes:
        return "available"
    return "restricted"


def _section_text(section: dict) -> str:
    slides = []
    for slide in section.get("slides", []):
        slides.append("\n".join(slide.get("lines", [])))
    return "\n\n".join(slides)


def _run_database_call(service, *args, **kwargs):
    """Run a sync Django service without retaining its worker-thread connection."""

    try:
        return service(*args, **kwargs)
    finally:
        # Bolt owns the async request loop; Django connections opened in its
        # thread-sensitive worker are otherwise invisible to request_finished.
        connections.close_all()


async def _database_call(service, *args, **kwargs):
    return await sync_to_async(_run_database_call, thread_sensitive=True)(
        service,
        *args,
        **kwargs,
    )


@api.post(
    "/imports",
    response_model=CatalogImportResponse,
    tags=["catalog imports"],
    summary="Import a catalog package",
    description=(
        "Requires `catalog.import`. The Catalog Importer privately retains and validates "
        "the complete package before atomically promoting an immutable snapshot."
    ),
)
async def catalog_import(
    package: Annotated[
        UploadFile,
        File(
            alias="package",
            max_size=MAX_PACKAGE_BYTES,
            allowed_types=["application/zip", "application/x-zip-compressed"],
        ),
    ],
    authorization: Annotated[str, Header(alias="Authorization")] = "",
):
    """Receive a Catalog Import Package from an import-scoped client."""

    authorized = await _database_call(
        _authorize,
        authorization,
        APIKeyScope.CATALOG_IMPORT,
    )
    if isinstance(authorized, tuple):
        return authorized

    try:
        result = await _database_call(import_package, package.file.read())
    except ImportRejected as exc:
        status = 409 if exc.code == "run_id_conflict" else 422
        return _raw_error(exc.code, exc.summary, status)
    return Response(
        CatalogImportResponse(
            run_id=str(result.run.pk),
            status=result.run.status,
        ),
        status_code=201 if result.created else 200,
    )


@api.get(
    "/search",
    response_model=CatalogSearchResponse,
    tags=["catalog reads"],
    summary="Search the active Song Catalog",
    description=(
        "Requires `catalog.search`. Lyrics mode also requires `catalog.lyrics.read`; "
        "restricted entries participate only when the key has "
        "`catalog.lyrics.restricted`. Empty title search returns the first alphabetical "
        "page. Follow the opaque `next` URL unchanged. Search is limited to 60 requests "
        "per key per minute. Malformed continuations return 400; expired or pruned "
        "snapshot continuations return 410 with an error `restart` URL."
    ),
)
async def catalog_search(
    q: Annotated[str, Query(description="Plain title or lyric words")] = "",
    mode: Annotated[str, Query(description="`title` or `lyrics`")] = "title",
    limit: Annotated[int, Query(description="Page size from 1 through 100")] = 20,
    continuation: Annotated[
        str | None,
        Query(alias="next", description="Opaque server-provided continuation"),
    ] = None,
    authorization: Annotated[
        str,
        Header(alias="Authorization", description="Bearer Integration Client key"),
    ] = "",
):
    required_scopes = [APIKeyScope.CATALOG_SEARCH]
    if mode == "lyrics":
        required_scopes.append(APIKeyScope.LYRICS_READ)
    authorized = await _database_call(
        _authorize,
        authorization,
        *required_scopes,
    )
    if isinstance(authorized, tuple):
        return authorized
    rate = await _database_call(
        _consume_rate,
        authorized,
        bucket="catalog.search",
        limit=SEARCH_RATE_LIMIT,
    )
    if isinstance(rate, tuple):
        return rate

    try:
        page = await _database_call(
            search_catalog,
            query=q,
            mode=mode,
            limit=limit,
            continuation=continuation,
            include_restricted_lyrics=(
                APIKeyScope.RESTRICTED_LYRICS_READ in authorized.scopes
            ),
        )
    except CatalogReadError as exc:
        return _raw_error(
            exc.code,
            exc.message,
            exc.status_code,
            headers=rate.headers,
            restart_url=exc.restart_url,
        )

    results = [
        CatalogSearchSong(
            song_uid=entry.song_uid,
            title=entry.title,
            authors=entry.authors,
            slide_count=entry.slide_count,
            content_changed_at=entry.content_changed_at,
            rights_status=entry.rights_status,
            lyrics_access=_lyrics_access(entry, authorized.scopes),
        )
        for entry in page.entries
    ]
    return Response(
        CatalogSearchResponse(
            results=results,
            next=page.next_url,
            has_more=page.has_more,
        ),
        headers=rate.headers,
    )


@api.get(
    "/songs/{song_uid}",
    response_model=SongMetadataResponse,
    tags=["catalog reads"],
    summary="Read Song Catalog metadata",
    description=(
        "Requires `catalog.song.read`. This resource never returns cleaned lyrics or "
        "structured Song Sections. It is limited to 60 requests per key per minute."
    ),
)
async def song_metadata(
    song_uid: Annotated[str, Path(description="Stable EasyWorship song identity")],
    authorization: Annotated[
        str,
        Header(alias="Authorization", description="Bearer Integration Client key"),
    ] = "",
):
    authorized = await _database_call(
        _authorize,
        authorization,
        APIKeyScope.SONG_READ,
    )
    if isinstance(authorized, tuple):
        return authorized
    rate = await _database_call(
        _consume_rate,
        authorized,
        bucket="catalog.song",
        limit=SONG_RATE_LIMIT,
    )
    if isinstance(rate, tuple):
        return rate
    try:
        entry = await _database_call(get_active_entry, song_uid)
    except CatalogReadError as exc:
        return _raw_error(
            exc.code,
            exc.message,
            exc.status_code,
            headers=rate.headers,
        )
    return Response(
        SongMetadataResponse(
            song_uid=entry.song_uid,
            title=entry.title,
            authors=entry.authors,
            copyright_notice=entry.copyright_notice,
            slide_count=entry.slide_count,
            content_changed_at=entry.content_changed_at,
            rights_status=entry.rights_status,
            lyrics_access=_lyrics_access(entry, authorized.scopes),
        ),
        headers=rate.headers,
    )


@api.get(
    "/songs/{song_uid}/lyrics",
    response_model=SongLyricsResponse,
    tags=["catalog reads"],
    summary="Read structured song lyrics",
    description=(
        "Requires `catalog.lyrics.read`. A restricted song additionally requires "
        "`catalog.lyrics.restricted`; without it, the resource returns 403 and no lyric "
        "content. Sections preserve source order and expose position, label, and text. "
        "This resource is limited to 30 requests per key per minute."
    ),
)
async def song_lyrics(
    song_uid: Annotated[str, Path(description="Stable EasyWorship song identity")],
    authorization: Annotated[
        str,
        Header(alias="Authorization", description="Bearer Integration Client key"),
    ] = "",
):
    authorized = await _database_call(
        _authorize,
        authorization,
        APIKeyScope.LYRICS_READ,
    )
    if isinstance(authorized, tuple):
        return authorized
    rate = await _database_call(
        _consume_rate,
        authorized,
        bucket="catalog.lyrics",
        limit=LYRICS_RATE_LIMIT,
    )
    if isinstance(rate, tuple):
        return rate
    try:
        entry = await _database_call(get_active_entry, song_uid)
    except CatalogReadError as exc:
        return _raw_error(
            exc.code,
            exc.message,
            exc.status_code,
            headers=rate.headers,
        )
    if (
        entry.rights_status == RightsStatus.RESTRICTED
        and APIKeyScope.RESTRICTED_LYRICS_READ not in authorized.scopes
    ):
        return _raw_error(
            "restricted_lyrics_forbidden",
            "This key is not permitted to read restricted lyrics.",
            403,
            headers=rate.headers,
        )

    sections = [
        SongLyricsSection(
            position=section["position"],
            label=section["label"],
            text=_section_text(section),
        )
        for section in entry.sections
    ]
    return Response(
        SongLyricsResponse(
            song_uid=entry.song_uid,
            title=entry.title,
            content_changed_at=entry.content_changed_at,
            rights_status=entry.rights_status,
            sections=sections,
        ),
        headers=rate.headers,
    )
