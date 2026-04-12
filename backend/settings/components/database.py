from backend.settings import env
from backend.settings.components import BASE_DIR

DATABASES = {
    "default": env.dj_db_url(
        "DATABASE_URL", default="sqlite:///" + str(BASE_DIR / "db.sqlite3")
    ),
}
