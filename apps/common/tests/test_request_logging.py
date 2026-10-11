"""Request log contracts through Django's HTTP client."""

import http.client
import io
import json
import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from importlib.util import find_spec
from unittest import skipUnless

from django.test import SimpleTestCase
from django.urls import path
from structlog.processors import JSONRenderer
from structlog.stdlib import ProcessorFormatter

from backend.settings.components.logging import JSON_PROCESSORS


@contextmanager
def capture_logs():
    """Capture the configured application handlers as production JSON."""
    stream = io.StringIO()
    formatter = ProcessorFormatter(
        processor=JSONRenderer(), foreign_pre_chain=JSON_PROCESSORS
    )
    handlers = {
        handler
        for logger in [
            logging.getLogger(),
            *[
                item
                for item in logging.Logger.manager.loggerDict.values()
                if isinstance(item, logging.Logger)
            ],
        ]
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
    }
    previous = [(handler, handler.stream, handler.formatter) for handler in handlers]
    for handler in handlers:
        handler.setStream(stream)
        handler.setFormatter(formatter)
    try:
        yield stream
    finally:
        for handler, old_stream, old_formatter in previous:
            handler.setStream(old_stream)
            handler.setFormatter(old_formatter)


def fail_request(_request):
    raise ValueError("private-exception-song-lyrics")


urlpatterns = [path("fail/", fail_request)]


class DjangoRequestLogTests(SimpleTestCase):
    def test_request_log_correlates_cloud_trace_without_logging_secrets(self):
        with self.settings(GCP_PROJECT_ID="wpp-test-project"), capture_logs() as logs:
            response = self.client.get(
                "/health/?lyrics=private-lyrics",
                HTTP_X_REQUEST_ID="request-123",
                HTTP_X_CLOUD_TRACE_CONTEXT="0123456789abcdef0123456789abcdef/42;o=1",
                HTTP_AUTHORIZATION="Bearer private-key",
                HTTP_USER_AGENT='private-agent"\\\n',
            )
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in logs.getvalue().splitlines()]
        event = next(item for item in events if item["event"] == "request_finished")
        self.assertEqual(event["request_id"], "request-123")
        self.assertEqual(
            event["logging.googleapis.com/trace"],
            "projects/wpp-test-project/traces/0123456789abcdef0123456789abcdef",
        )
        self.assertEqual((event["method"], event["status"]), ("GET", 200))
        self.assertGreaterEqual(event["duration_ms"], 0)
        for secret in ("private-lyrics", "private-key", "private-agent"):
            self.assertNotIn(secret, logs.getvalue())

    def test_bolt_validation_failure_has_safe_correlated_json(self):
        from django_bolt.testing import TestClient

        from apps.catalog.api import api

        with (
            self.settings(GCP_PROJECT_ID="wpp-test-project"),
            capture_logs() as logs,
            TestClient(api, read_django_settings=False) as client,
        ):
            response = client.post(
                "/api/v1/catalog/imports?key=private-query",
                headers={
                    "x-request-id": "bolt-123",
                    "x-cloud-trace-context": "0123456789abcdef0123456789abcdef/42;o=1",
                    "authorization": "Bearer private-key",
                },
                files={"notes": ("catalog.txt", b"private-source", "text/plain")},
            )
        self.assertGreaterEqual(response.status_code, 400)
        events = [json.loads(line) for line in logs.getvalue().splitlines()]
        event = next(item for item in events if item["event"] == "request_finished")
        self.assertEqual(
            (event["request_id"], event["status"]), ("bolt-123", response.status_code)
        )
        self.assertEqual(
            event["logging.googleapis.com/trace"],
            "projects/wpp-test-project/traces/0123456789abcdef0123456789abcdef",
        )
        for secret in ("private-query", "private-key", "private-source"):
            self.assertNotIn(secret, logs.getvalue())

    def test_server_error_does_not_log_exception_content_or_locals(self):
        with self.settings(ROOT_URLCONF=__name__), capture_logs() as logs:
            self.client.raise_request_exception = False
            response = self.client.get(
                "/fail/?key=private-query", HTTP_X_REQUEST_ID="failed-123"
            )
        self.assertEqual(response.status_code, 500)
        events = [json.loads(line) for line in logs.getvalue().splitlines()]
        self.assertTrue(
            any(item.get("exception_type") == "ValueError" for item in events)
        )
        self.assertNotIn("private-exception-song-lyrics", logs.getvalue())
        self.assertNotIn("private-query", logs.getvalue())

    def test_untrusted_identity_is_bounded_and_does_not_inherit_another_trace(self):
        import structlog

        with (
            structlog.contextvars.bound_contextvars(
                **{"logging.googleapis.com/trace": "private-inherited-trace"}
            ),
            capture_logs() as logs,
        ):
            response = self.client.get(
                "/health/",
                HTTP_X_REQUEST_ID='bad"\\\n' * 1000,
                HTTP_X_CLOUD_TRACE_CONTEXT="bad-trace",
            )
        self.assertEqual(response.status_code, 200)
        outcome = next(
            json.loads(line)
            for line in logs.getvalue().splitlines()
            if json.loads(line)["event"] == "request_finished"
        )
        self.assertRegex(outcome["request_id"], r"^[0-9a-f]{32}$")
        self.assertNotIn("logging.googleapis.com/trace", outcome)
        self.assertNotIn("private-inherited-trace", logs.getvalue())

    def test_concurrent_requests_keep_separate_identities(self):
        from concurrent.futures import ThreadPoolExecutor

        from django.test import Client

        def request(number):
            return (
                Client()
                .get("/health/", HTTP_X_REQUEST_ID=f"concurrent-{number}")
                .status_code
            )

        with capture_logs() as logs, ThreadPoolExecutor(max_workers=4) as executor:
            statuses = list(executor.map(request, range(8)))
        self.assertEqual(statuses, [200] * 8)
        events = [json.loads(line) for line in logs.getvalue().splitlines()]
        self.assertEqual(
            sorted(
                event["request_id"]
                for event in events
                if event["event"] == "request_finished"
            ),
            [f"concurrent-{number}" for number in range(8)],
        )

    @skipUnless(
        find_spec("gunicorn") and find_spec("storages"), "Requires production runtime"
    )
    def test_gunicorn_production_events_are_json_and_requests_keep_the_trace(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with tempfile.TemporaryFile(mode="w+") as logs:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "gunicorn",
                    "backend.wsgi:application",
                    "--config",
                    "python:backend.gunicorn",
                    "--bind",
                    f"127.0.0.1:{port}",
                    "--workers",
                    "1",
                ],
                stdout=logs,
                stderr=logs,
                env={
                    **os.environ,
                    "DJANGO_SETTINGS_MODULE": "backend.settings",
                    "DJANGO_ENV": "prod",
                    "DATABASE_URL": "sqlite:///:memory:",
                    "SUPABASE_STORAGE_BUCKET": "test-only",
                    "SUPABASE_CATALOG_IMPORT_BUCKET": "test-only-imports",
                    "SUPABASE_S3_ENDPOINT": "https://unused.example.invalid",
                    "SUPABASE_S3_ACCESS_KEY": "test-only",
                    "SUPABASE_S3_SECRET_KEY": "test-only",
                    "GCP_PROJECT_ID": "wpp-test-project",
                    "ALLOWED_HOSTS": "127.0.0.1",
                    "PYTHONWARNINGS": "ignore:No directory at:UserWarning",
                },
            )
            try:
                for attempt in range(100):
                    try:
                        connection = http.client.HTTPConnection(
                            "127.0.0.1", port, timeout=2
                        )
                        connection.request(
                            "GET",
                            "/health/?key=private-query",
                            headers={
                                "Authorization": "Bearer private-key",
                                "X-Request-ID": "gunicorn-123",
                                "X-Cloud-Trace-Context": "0123456789abcdef0123456789abcdef/42;o=1",
                            },
                        )
                        response = connection.getresponse()
                        status = response.status
                        response.read()
                        connection.close()
                        break
                    except OSError:
                        if process.poll() is not None:
                            break
                        time.sleep(0.05)
                else:
                    self.fail("Gunicorn did not start")
            finally:
                process.terminate()
                process.wait(timeout=10)
            logs.seek(0)
            output = logs.read()
        self.assertEqual(process.returncode, 0, output)
        self.assertEqual(status, 200)
        events = [json.loads(line) for line in output.splitlines()]
        self.assertTrue(any(event["logger"] == "gunicorn.error" for event in events))
        outcome = next(event for event in events if event["event"] == "request_finished")
        self.assertEqual(
            (outcome["request_id"], outcome["logging.googleapis.com/trace"]),
            (
                "gunicorn-123",
                "projects/wpp-test-project/traces/0123456789abcdef0123456789abcdef",
            ),
        )
        self.assertNotIn("private-query", output)
        self.assertNotIn("private-key", output)
