"""Production-only overrides. Runtime values come from the split-settings scope."""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from backend.settings import env
from backend.settings.components.database import DATABASES
from backend.settings.components.storage import (
    STORAGES_SUPABASE,
    SUPABASE_CATALOG_IMPORT_BUCKET,
    SUPABASE_STORAGE_BUCKET,
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

if not SUPABASE_STORAGE_BUCKET:
    raise ImproperlyConfigured("SUPABASE_STORAGE_BUCKET must be set in production.")

if not SUPABASE_CATALOG_IMPORT_BUCKET:
    raise ImproperlyConfigured(
        "SUPABASE_CATALOG_IMPORT_BUCKET must be set in production."
    )

STORAGES = STORAGES_SUPABASE
STORAGES["default"]["OPTIONS"] = {
    "bucket_name": env.str("SUPABASE_STORAGE_BUCKET"),
    "endpoint_url": env.str("SUPABASE_S3_ENDPOINT"),
    "access_key": env.str("SUPABASE_S3_ACCESS_KEY"),
    "secret_key": env.str("SUPABASE_S3_SECRET_KEY"),
    "region_name": env.str("SUPABASE_S3_REGION", default="us-east-1"),
    "default_acl": None,
    "querystring_auth": False,
}
STORAGES["catalog_imports"]["OPTIONS"] = {
    **STORAGES["default"]["OPTIONS"],
    "bucket_name": env.str("SUPABASE_CATALOG_IMPORT_BUCKET"),
    "querystring_auth": True,
}
