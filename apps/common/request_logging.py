"""Bounded request correlation shared by the rendered and JSON transports."""

import re
from collections.abc import Mapping
from time import perf_counter
from uuid import uuid4

import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)
REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
TRACE_CONTEXT = re.compile(r"([0-9a-f]{32})/[0-9]{1,20}(?:;o=[01])?")


def correlate_request(headers: Mapping[str, str]) -> dict[str, str | None]:
    """Use validated forwarded identities, or generate a local request identity."""
    request_id = headers.get("x-request-id", "")
    if not REQUEST_ID.fullmatch(request_id):
        request_id = uuid4().hex
    context: dict[str, str | None] = {
        "request_id": request_id,
        "logging.googleapis.com/trace": None,
    }
    trace = TRACE_CONTEXT.fullmatch(headers.get("x-cloud-trace-context", ""))
    project = settings.GCP_PROJECT_ID
    if trace and trace[1] != "0" * 32 and project:
        context["logging.googleapis.com/trace"] = f"projects/{project}/traces/{trace[1]}"
    return context


def finish_request(method: str, path: str, status: int, started: float) -> None:
    """Log HTTP outcome metadata without headers, query strings, or content."""
    logger.log(
        40 if status >= 500 else 30 if status >= 400 else 20,
        "request_finished",
        method=method[:32],
        path=path.split("?", 1)[0][:2048],
        status=status,
        duration_ms=round((perf_counter() - started) * 1000, 2),
    )


class DjangoRequestLogging:
    """Correlate Django requests including framework-generated error responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = perf_counter()
        with structlog.contextvars.bound_contextvars(
            **correlate_request(request.headers)
        ):
            response = self.get_response(request)
            finish_request(request.method, request.path, response.status_code, started)
            return response


class BoltRequestLogging:
    """Log Bolt dispatch and validation outcomes before releasing request context."""

    def __init__(self, get_response):
        self.get_response = get_response

    async def __call__(self, request):
        from django_bolt.error_handlers import handle_exception
        from django_bolt.middleware_response import MiddlewareResponse

        started = perf_counter()
        with structlog.contextvars.bound_contextvars(
            **correlate_request(request.headers)
        ):
            try:
                response = await self.get_response(request)
            except Exception as exc:  # noqa: BLE001 - Bolt maps all exceptions to HTTP.
                response = MiddlewareResponse.from_tuple(
                    handle_exception(exc, request=request)
                )
            finish_request(request.method, request.path, response.status_code, started)
            return response
