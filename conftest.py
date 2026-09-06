"""Pytest hooks for CI-provided or local Testcontainers PostgreSQL."""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import TextIO

import pytest
from pytest_django.lazy_django import skip_if_no_django
from testcontainers.postgres import PostgresContainer


def _read_output(
    stream: TextIO,
    output: list[str],
    ready: queue.Queue[str] | None = None,
) -> None:
    """Collect one renderer output stream without blocking test-session setup."""

    while chunk := stream.read(1):
        output.append(chunk)
        if ready is not None:
            ready.put(chunk)


def _build_reactivated_renderer(project_root: Path) -> None:
    """Generate the template registry and renderer bundle used by SSR tests."""

    from reactivated.apps import generate_schema

    generate_schema(skip_cache=True)
    build = subprocess.run(
        ["npm", "exec", "build.client"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if build.returncode:
        raise RuntimeError(
            "Could not build the Reactivated renderer. "
            f"stdout: {build.stdout!r}; stderr: {build.stderr!r}"
        )


def _start_reactivated_renderer() -> tuple[
    subprocess.Popen[str], str, list[str], list[str]
]:
    """Start the bundled SSR renderer and return its ready Unix-socket address."""

    project_root = Path(__file__).parent
    renderer_path = project_root / "node_modules" / "_reactivated" / "renderer.js"
    _build_reactivated_renderer(project_root)
    if not renderer_path.is_file():
        raise RuntimeError("Reactivated renderer bundle was not produced by the build.")

    process = subprocess.Popen(
        ["node", str(renderer_path)],
        cwd=project_root,
        env={**os.environ, "NODE_ENV": "production"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stdout: list[str] = []
    stderr: list[str] = []
    ready_output: queue.Queue[str] = queue.Queue()
    assert process.stdout is not None
    assert process.stderr is not None
    threading.Thread(
        target=_read_output,
        args=(process.stdout, stdout, ready_output),
        daemon=True,
    ).start()
    threading.Thread(
        target=_read_output,
        args=(process.stderr, stderr),
        daemon=True,
    ).start()

    marker = "RENDERER:"
    output = ""
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None and ready_output.empty():
            break
        try:
            output += ready_output.get(timeout=0.1)
        except queue.Empty:
            continue
        if marker in output and ":LISTENING" in output:
            address = output.split(marker, 1)[1].split(":LISTENING", 1)[0]
            return process, address, stdout, stderr

    process.terminate()
    process.wait(timeout=5)
    raise RuntimeError(
        "Reactivated renderer did not become ready. "
        f"stdout: {''.join(stdout)!r}; stderr: {''.join(stderr)!r}"
    )


@pytest.fixture(scope="session", autouse=True)
def reactivated_renderer() -> None:
    """Provide one fresh Reactivated SSR renderer for the complete pytest session."""

    process, address, stdout, stderr = _start_reactivated_renderer()
    previous_address = os.environ.get("REACTIVATED_RENDERER")
    os.environ["REACTIVATED_RENDERER"] = address
    try:
        yield
    finally:
        if previous_address is None:
            os.environ.pop("REACTIVATED_RENDERER", None)
        else:
            os.environ["REACTIVATED_RENDERER"] = previous_address
        if process.poll() is not None:
            raise RuntimeError(
                "Reactivated renderer exited during pytest. "
                f"stdout: {''.join(stdout)!r}; stderr: {''.join(stderr)!r}"
            )
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


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
