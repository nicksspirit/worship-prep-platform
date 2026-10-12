from backend.settings import env
from backend.settings.components import BASE_DIR

SITE_ID = env.int("SITE_ID", default=1)
CATALOG_EXPORTER_API_URL = env.str(
    "CATALOG_EXPORTER_API_URL", default="https://api.rccgcm.org"
)
# Allow the 128 MiB package, 1 MiB events, and multipart overhead; match Nginx.
BOLT_MAX_UPLOAD_SIZE = 130 * 1024 * 1024

INSTALLED_APPS = [
    # 3rd party apps (unfold must be before django.contrib.admin)
    "unfold.apps.DefaultAppConfig",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "invitations",  # must come after allauth
    "reactivated",
    "django_structlog",
    "health_check",
    "django_bolt",
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 1st party apps
    "apps.common",
    "apps.accounts",
    "apps.api_keys",
    "apps.catalog",
    "apps.song_carts",
]

MIDDLEWARE = [
    "apps.common.request_logging.DjangoRequestLogging",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.common.middleware.CsrfBypassApiMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
    {
        "BACKEND": "reactivated.backend.JSX",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "apps.common.context_processors.auth",
                "apps.song_carts.context_processors.song_cart",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csrf",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
            ]
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
