from backend.settings import env
from backend.settings.components import BASE_DIR

DATABASES = {
    "default": env.dj_db_url(
        "DATABASE_URL", default="sqlite:///" + str(BASE_DIR / "db.sqlite3")
    ),
}

if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    options = DATABASES["default"].setdefault("OPTIONS", {})
    # Resolve app tables in public and search operators in extensions.
    options["options"] = "-c search_path=public,extensions"
