from typing import cast

from django.http import HttpResponse
from django.views import View

from apps.catalog_prototype.templates import SongCatalogPrototypePage
from apps.users.templates import RenderableTemplate


class SongCatalogPrototypeView(View):
    """Render the throwaway Song Catalog experience prototype."""

    def get(self, request, *args, **kwargs) -> HttpResponse:
        page = cast(
            RenderableTemplate,
            SongCatalogPrototypePage(title="Song Catalog Prototype"),
        )
        return page.render(request)

