from textwrap import dedent
from typing import cast

from django.http import Http404, HttpRequest, HttpResponse
from django.views import View

from apps.catalog.presentation import (
    PUBLIC_DEFAULT_PAGE_SIZE,
    PUBLIC_MAX_PAGE_SIZE,
    PUBLIC_MAX_QUERY_LENGTH,
    present_search,
    present_song,
)
from apps.catalog.services import (
    CatalogAccess,
    CatalogReadError,
    GetCatalogSong,
    SearchCatalog,
    get_catalog_song,
    search_catalog,
)
from apps.catalog.templates import RenderableTemplate


def _limit(raw: str | None) -> int:
    if raw in {None, ""}:
        return PUBLIC_DEFAULT_PAGE_SIZE
    try:
        limit = int(raw)
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


def catalog_exporter_install(request: HttpRequest) -> HttpResponse:
    """Serve the copy-and-paste bootstrap for the Windows Catalog Exporter."""
    platform_url = request.build_absolute_uri("/").rstrip("/")
    installer_url = request.build_absolute_uri("/static/install-catalog-exporter.ps1")
    quote = lambda value: "'" + value.replace("'", "''") + "'"
    script = dedent(f"""#Requires -Version 5.1
    $ErrorActionPreference = 'Stop'
    $platformUrl = {quote(platform_url)}
    $installerPath = Join-Path ([System.IO.Path]::GetTempPath()) ("install-catalog-exporter-" + [guid]::NewGuid() + ".ps1")
    try {{
        Write-Host 'Downloading the checksum-verified Catalog Exporter installer...'
        Invoke-WebRequest -Uri {quote(installer_url)} -OutFile $installerPath
        & $installerPath -PlatformUrl $platformUrl
    }}
    finally {{
        Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    }}
    """)
    response = HttpResponse(script, content_type="text/plain; charset=utf-8")
    response["Cache-Control"], response["X-Content-Type-Options"] = "no-store", "nosniff"
    return response


class CatalogSearchView(View):
    """Render the public Song Catalog search and stable continuations."""

    def get(self, request: HttpRequest) -> HttpResponse:
        query, mode = request.GET.get("q", ""), request.GET.get("mode", "title")
        continuation = request.GET.get("next") or None
        limit, result, error, status, restart = (
            PUBLIC_DEFAULT_PAGE_SIZE,
            None,
            None,
            200,
            None,
        )
        try:
            limit = _limit(request.GET.get("limit"))
            if len(query.strip()) > PUBLIC_MAX_QUERY_LENGTH:
                raise CatalogReadError(
                    "query_too_long",
                    f"Search terms may contain at most {PUBLIC_MAX_QUERY_LENGTH} characters.",
                    400,
                )
            if mode not in {"title", "lyrics"}:
                raise CatalogReadError(
                    "invalid_mode", "Choose either Title or Lyrics search.", 400
                )
            if not query.strip() and continuation:
                raise CatalogReadError(
                    "cursor_query_mismatch",
                    "This continuation does not belong to an empty search.",
                    400,
                )
            result = search_catalog(
                SearchCatalog(
                    query=query,
                    mode="title" if not query.strip() else mode,
                    limit=limit,
                    continuation=continuation,
                    access=CatalogAccess(True, False),
                )
            )
        except CatalogReadError as exc:
            error, status, restart = exc.message, exc.status_code, exc.restart
        page = cast(
            RenderableTemplate,
            present_search(
                result, query=query, mode=mode, limit=limit, error=error, restart=restart
            ),
        )
        response = page.render(request)
        response.status_code = status
        return response


class SongDetailView(View):
    """Render one active Song Catalog entry with rights-aware lyric fields."""

    def get(self, request: HttpRequest, song_uid: str) -> HttpResponse:
        try:
            song = get_catalog_song(GetCatalogSong(song_uid, CatalogAccess(True, False)))
        except CatalogReadError as exc:
            if exc.status_code == 404:
                raise Http404(exc.message) from exc
            raise
        return cast(RenderableTemplate, present_song(song)).render(request)
