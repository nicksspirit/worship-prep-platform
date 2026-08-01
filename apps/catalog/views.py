from typing import cast

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.urls import reverse
from django.views import View

from apps.catalog.presentation import (
    PUBLIC_DEFAULT_PAGE_SIZE,
    Freshness,
    PublicSearchItem,
    get_public_song,
    parse_public_limit,
    public_restart_url,
    search_public_catalog,
)
from apps.catalog.search import CatalogReadError
from apps.catalog.templates import (
    CatalogSearchPage,
    FreshnessProps,
    RenderableTemplate,
    SearchItemProps,
    SectionProps,
    SlideProps,
    SongDetailPage,
)


def _freshness(value: Freshness | None) -> FreshnessProps | None:
    if value is None:
        return None
    return FreshnessProps(value.iso, value.absolute, value.relative)


def _search_item(item: PublicSearchItem) -> SearchItemProps:
    freshness = _freshness(item.song_freshness)
    assert freshness is not None
    return SearchItemProps(
        song_uid=item.song_uid,
        url=item.url,
        title=item.title,
        author=item.author,
        lyric_preview=item.lyric_preview,
        lyrics_available=item.lyrics_available,
        rights_status=item.rights_status,
        song_freshness=freshness,
    )


class CatalogSearchView(View):
    """Render the public Song Catalog search and stable continuations."""

    def get(self, request: HttpRequest) -> HttpResponse:
        query = request.GET.get("q", "")
        mode = request.GET.get("mode", "title")
        continuation = request.GET.get("next") or None
        limit = PUBLIC_DEFAULT_PAGE_SIZE
        result = None
        error = None
        status_code = 200
        restart_url = None
        requested_variant = request.GET.get("variant")
        prototype_variant = (
            requested_variant
            if settings.DEBUG and requested_variant in {"A", "B", "C"}
            else None
        )
        try:
            limit = parse_public_limit(request.GET.get("limit"))
            result = search_public_catalog(
                query=query,
                mode=mode,
                limit=limit,
                continuation=continuation,
            )
        except CatalogReadError as exc:
            error = exc.message
            status_code = exc.status_code
            if exc.status_code == 410:
                restart_url = public_restart_url(
                    query=query,
                    mode=mode,
                    limit=limit,
                )

        page = cast(
            RenderableTemplate,
            CatalogSearchPage(
                title="Song Catalog",
                query=query,
                mode=mode if mode in {"title", "lyrics"} else "title",
                limit=limit,
                searched=bool(query.strip()),
                results=[_search_item(item) for item in result.items] if result else [],
                catalog_freshness=(
                    _freshness(result.catalog_freshness) if result else None
                ),
                next_url=result.next_url if result else None,
                has_more=result.has_more if result else False,
                error=error,
                restart_url=restart_url,
                prototype_variant=prototype_variant,
            ),
        )
        response = page.render(request)
        response.status_code = status_code
        return response


class SongDetailView(View):
    """Render one active Song Catalog entry with rights-aware lyric fields."""

    def get(self, request: HttpRequest, song_uid: str) -> HttpResponse:
        try:
            song = get_public_song(song_uid)
        except CatalogReadError as exc:
            if exc.status_code == 404:
                raise Http404(exc.message) from exc
            raise
        song_freshness = _freshness(song.song_freshness)
        assert song_freshness is not None
        page = cast(
            RenderableTemplate,
            SongDetailPage(
                title=song.title,
                author=song.author,
                copyright_notice=song.copyright_notice,
                rights_status=song.rights_status,
                lyrics_available=song.lyrics_available,
                sections=[
                    SectionProps(section.position, section.label, section.text)
                    for section in song.sections
                ],
                slides=[
                    SlideProps(slide.position, slide.section_label, slide.lines)
                    for slide in song.slides
                ],
                slide_count=song.slide_count,
                song_freshness=song_freshness,
                catalog_freshness=_freshness(song.catalog_freshness),
                catalog_url=reverse("catalog:search"),
            ),
        )
        return page.render(request)
