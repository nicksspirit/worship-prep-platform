from __future__ import annotations

from typing import Any

from backend.settings import env
from backend.settings.components import BASE_DIR

PUBLIC_ASSET_DIR = BASE_DIR / "public"
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
STATIC_ROOT = PUBLIC_ASSET_DIR / "static"
MEDIA_ROOT = PUBLIC_ASSET_DIR / "media"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Vite output (static/dist/index.js) and most other files keep stable names, so they
# use WhiteNoise's short default max-age. Only fonts and images whose filename carries
# a 12-character content hash (name.<hash>.ext) are safe to cache for a year.
WHITENOISE_IMMUTABLE_FILE_TEST = (
    rf"^{STATIC_URL}(?:fonts|images)/[^/]+\.[0-9a-f]{{12}}\.[a-z0-9]+$"
)

# Used in environments/prod.py (guard); optional outside production.
SUPABASE_STORAGE_BUCKET = env.str("SUPABASE_STORAGE_BUCKET", default="")
SUPABASE_CATALOG_IMPORT_BUCKET = env.str(
    "SUPABASE_CATALOG_IMPORT_BUCKET", default=""
)

# Filesystem media + default staticfiles (local / test).
STORAGES_LOCAL: dict[str, dict[str, Any]] = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "catalog_imports": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": BASE_DIR / "var" / "catalog-imports"},
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Skeleton for Supabase (S3) media + Whitenoise staticfiles. Production fills OPTIONS.
STORAGES_SUPABASE: dict[str, dict[str, Any]] = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {},
    },
    "catalog_imports": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {},
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

STORAGES: dict[str, dict[str, Any]] = STORAGES_LOCAL
