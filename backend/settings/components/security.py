from backend.settings import DJANGO_ENV, env

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str(
    "SECRET_KEY",
    default="django-insecure-y@oe&%+ay#9-@hvkt7azp^6&dnr(^z(onxxjhp@#8t5oyr1upf",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=DJANGO_ENV == "local")

DEFAULT_ALLOWED_HOSTS = [
    ".run.app",
    ".rccgcm.org",
    "localhost",
    "127.0.0.1",
]
DEFAULT_CSRF_TRUSTED_ORIGINS = [
    "https://*.run.app",
    "https://*.rccgcm.org",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=DEFAULT_ALLOWED_HOSTS)
CSRF_TRUSTED_ORIGINS: list[str] = env.list(
    "CSRF_TRUSTED_ORIGINS", default=DEFAULT_CSRF_TRUSTED_ORIGINS
)
