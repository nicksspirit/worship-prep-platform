from django.urls import path

from apps.catalog_prototype.views import SongCatalogPrototypeView

urlpatterns = [
    path(
        "prototype/song-catalog/",
        SongCatalogPrototypeView.as_view(),
        name="song_catalog_prototype",
    ),
]

