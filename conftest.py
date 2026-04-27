"""Pytest hooks: disposable Postgres via Testcontainers for the test session."""

from __future__ import annotations

import pytest
from pytest_django.lazy_django import skip_if_no_django
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def django_db_modify_db_settings(
    django_db_modify_db_settings_parallel_suffix: None,
    django_test_environment: None,
    request: pytest.FixtureRequest,
) -> None:
    """Start Postgres in Docker and point Django at it before the test DB is created.

    Overrides pytest-django's no-op ``django_db_modify_db_settings`` while preserving
    tox/xdist suffix behavior via ``django_db_modify_db_settings_parallel_suffix``.

    Depends on ``django_test_environment`` so Django settings are loaded before we
    mutate ``DATABASES``.
    """
    skip_if_no_django()
    from django.conf import settings

    container = PostgresContainer("postgres:16-alpine", driver=None)
    container.start()
    request.addfinalizer(container.stop)

    host = container.get_container_host_ip()
    port = int(container.get_exposed_port(5432))
    settings.DATABASES["default"].update(
        {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": host,
            "PORT": port,
            "NAME": container.dbname,
            "USER": container.username,
            "PASSWORD": container.password,
            # Drop sslmode etc. from the developer's DATABASE_URL; the container is local.
            "OPTIONS": {},
            "CONN_MAX_AGE": 0,
        }
    )
