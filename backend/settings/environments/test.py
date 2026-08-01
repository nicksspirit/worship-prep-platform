"""Tests: same storage preset as local (filesystem) unless overridden in .local.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.settings.components.database import DATABASES

if TYPE_CHECKING:
    from backend.settings.components.storage import STORAGES_LOCAL

STORAGES = STORAGES_LOCAL
STORAGES["catalog_imports"] = {
    "BACKEND": "django.core.files.storage.InMemoryStorage"
}

# Explicit test DB name when not using Testcontainers (e.g. manage.py test on host Postgres).
DATABASES["default"]["TEST"] = {"NAME": "wpp_testdb"}
