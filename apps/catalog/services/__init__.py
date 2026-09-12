"""Public interfaces for Song Catalog use cases."""

from .administration import ALLOWED_BASES, ScheduledImportFailure, change_lyrics_rights
from .catalog_text import SEARCH_CONFIG, normalize_title
from .importing import (
    ImportRejected,
    ImportResult,
    import_package,
    recover_import_run,
    rollback_to_snapshot,
)
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
    "ALLOWED_BASES",
    "CURSOR_MAX_AGE_SECONDS",
    "CatalogAccess",
    "CatalogReadError",
    "CatalogSearchItem",
    "CatalogSearchPage",
    "CatalogSong",
    "CatalogSongSection",
    "GetCatalogSong",
    "ImportRejected",
    "ImportResult",
    "ScheduledImportFailure",
    "SEARCH_CONFIG",
    "SearchCatalog",
    "SearchRestart",
    "change_lyrics_rights",
    "get_catalog_song",
    "import_package",
    "normalize_title",
    "recover_import_run",
    "rollback_to_snapshot",
    "search_catalog",
]
