from django.urls import path

from apps.catalog.views import CatalogSearchView, SongDetailView

app_name = "catalog"

urlpatterns = [
    path("", CatalogSearchView.as_view(), name="search"),
    path("songs/<path:song_uid>/", SongDetailView.as_view(), name="detail"),
]
