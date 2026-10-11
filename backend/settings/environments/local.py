"""Local development: filesystem media under MEDIA_ROOT, default staticfiles backend."""

from __future__ import annotations

from backend.settings import env
from backend.settings.components.storage import STORAGES_LOCAL

STORAGES = STORAGES_LOCAL
EMAIL_BACKEND = env.str("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
