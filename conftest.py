"""Pytest hooks for CI-provided or local Testcontainers PostgreSQL."""

from __future__ import annotations

import os

import pytest
from pytest_django.lazy_django import skip_if_no_django
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def django_db_modify_db_settings(
    django_db_modify_db_settings_parallel_suffix: None,
    django_test_environment: None,
    request: pytest.FixtureRequest,
) -> None:
    """Point Django at CI PostgreSQL or start a local Testcontainers instance.

    Overrides pytest-django's no-op ``django_db_modify_db_settings`` while preserving
    tox/xdist suffix behavior via ``django_db_modify_db_settings_parallel_suffix``.

    Depends on ``django_test_environment`` so Django settings are loaded before we
    mutate ``DATABASES``.
    """
    skip_if_no_django()
    from django.conf import settings

    ci_postgres_host = os.getenv("WPP_TEST_POSTGRES_HOST")
    if ci_postgres_host:
        settings.DATABASES["default"].update(
            {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": ci_postgres_host,
                "PORT": int(os.environ["WPP_TEST_POSTGRES_PORT"]),
                "NAME": os.environ["WPP_TEST_POSTGRES_DATABASE"],
                "USER": os.environ["WPP_TEST_POSTGRES_USER"],
                "PASSWORD": os.environ["WPP_TEST_POSTGRES_PASSWORD"],
                "OPTIONS": {},
                "CONN_MAX_AGE": 0,
            }
        )
        return

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
