from django.urls import path

from apps.catalog.views import CatalogSearchView, SongDetailView, catalog_exporter_install

app_name = "catalog"

urlpatterns = [
    path("install", catalog_exporter_install, name="install_exporter"),
    path("", CatalogSearchView.as_view(), name="search"),
    path("songs/<path:song_uid>/", SongDetailView.as_view(), name="detail"),
]
