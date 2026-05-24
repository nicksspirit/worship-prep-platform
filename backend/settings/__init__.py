"""
Django settings for the backend project (django-split-settings).

https://github.com/sobolevn/django-split-settings
"""

import django_stubs_ext
from environs import Env
from split_settings.tools import include, optional

# Monkeypatching Django so stubs work for generics (django-stubs)
django_stubs_ext.monkeypatch()

env = Env()
env.read_env()

DJANGO_ENV = env.str("DJANGO_ENV", default="local")
ENV = DJANGO_ENV

_base_settings = [
    # Explicit order: bootstrap BASE_DIR before other components; logging last among components.
    "components/__init__.py",
    "components/common.py",
    "components/security.py",
    "components/database.py",
    "components/storage.py",
    "components/auth.py",
    "components/admin_unfold.py",
    "components/logging.py",
    f"environments/{DJANGO_ENV}.py",
    optional("environments/.local.py"),
]

include(*_base_settings)
