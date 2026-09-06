"""Typed, transport-neutral Song Catalog read use cases."""

from .importing import ExistingCatalogSong, PreparedCatalogEntry, prepare_catalog_entries
from .search import (
    CURSOR_MAX_AGE_SECONDS,
    CatalogAccess,
    CatalogReadError,
    CatalogSearchItem,
    CatalogSearchPage,
    CatalogSong,
    CatalogSongSection,
    GetCatalogSong,
    SearchCatalog,
    SearchRestart,
    get_catalog_song,
    search_catalog,
)

__all__ = [
    "CURSOR_MAX_AGE_SECONDS",
    "ExistingCatalogSong",
    "PreparedCatalogEntry",
    "CatalogAccess",
    "CatalogReadError",
    "CatalogSearchItem",
    "CatalogSearchPage",
    "CatalogSong",
    "CatalogSongSection",
    "GetCatalogSong",
    "SearchCatalog",
    "SearchRestart",
    "get_catalog_song",
    "prepare_catalog_entries",
    "search_catalog",
]
