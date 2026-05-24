"""Local development: filesystem media under MEDIA_ROOT, default staticfiles backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.settings.components.storage import STORAGES_LOCAL

STORAGES = STORAGES_LOCAL
