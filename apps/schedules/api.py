import datetime as dt
import logging
from typing import Annotated

from django.conf import settings
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django_bolt import BoltAPI, JSON, Request
from django_bolt.auth import IsAuthenticated
from django_bolt.middleware import Middleware
from django_bolt.openapi import OpenAPIConfig
from django_bolt.param_functions import Header

from apps.schedules.exceptions import (
    DuplicateScheduleItemTypeError,
    DuplicateSubmissionError,
    ScheduleNotFoundError,
)
from apps.schedules.schemas import IntakeResponse, ScheduleIntakePayload, SchedulePreviewResponse
from apps.schedules.services.intake import intake_schedule, patch_schedule
from apps.schedules.services.preview import get_schedule_preview_async

logger = logging.getLogger("apps.schedules.inbound")


class InboundRequestDebugMiddleware(Middleware):
    """Logs inbound request data for debugging integrations."""

    async def process_request(self, request):
        debug_enabled = getattr(settings, "LOG_INBOUND_SCHEDULE_REQUESTS", False)
        if not debug_enabled:
            return await self.get_response(request)

        body_preview = ""
        if request.body:
            try:
                body_preview = request.body.decode("utf-8")[:500]
            except UnicodeDecodeError:
                body_preview = "<non-utf8-body>"

        log_payload = {
            "method": request.method,
            "path": request.path,
            "query": dict(request.query) if request.query else {},
            "headers": dict(request.headers),
            "body_preview": body_preview,
        }
        logger.info("Inbound schedule intake request: %s", log_payload)

        response = await self.get_response(request)
        logger.info(
            "Inbound schedule intake response: %s %s %s",
            request.method,
            request.path,
            response.status_code,
        )
        return response


api = BoltAPI(
    openapi_config=OpenAPIConfig(
        title="Worship Prep Platform API",
        description="Inbound schedule intake and workflow automation endpoints.",
        version="1.0.0",
    ),
    middleware=[InboundRequestDebugMiddleware],
    django_middleware=True,
    prefix="/api/v1",
)


@api.post(
    "/schedules/intake",
    status_code=201,
    tags=["schedules"],
    summary="Ingest Sunday schedule",
    description="Creates or updates the target Sunday schedule from a parsed agenda payload.",
)
async def intake_schedule_endpoint(
    payload: ScheduleIntakePayload,
    request: Request | None = None,
    n8n_api_key: Annotated[str | None, Header(alias="X-N8N-Api-Key")] = None,
):
    authorized = authorize_n8n_request(n8n_api_key)
    if authorized is not None:
        return authorized

    try:
        result = await intake_schedule(payload)
    except DuplicateScheduleItemTypeError as exc:
        return JSON({"detail": str(exc)}, status_code=409)
    except DuplicateSubmissionError as exc:
        return JSON({"detail": str(exc)}, status_code=409)
    return build_intake_response(result, request=request, status_code=201)


@api.patch(
    "/schedules/intake",
    status_code=200,
    tags=["schedules"],
    summary="Update Sunday schedule",
    description="Applies a partial update to an existing Sunday schedule using the parsed agenda payload.",
)
async def patch_schedule_endpoint(
    payload: ScheduleIntakePayload,
    request: Request | None = None,
    n8n_api_key: Annotated[str | None, Header(alias="X-N8N-Api-Key")] = None,
):
    authorized = authorize_n8n_request(n8n_api_key)
    if authorized is not None:
        return authorized

    try:
        result = await patch_schedule(payload)
    except DuplicateScheduleItemTypeError as exc:
        return JSON({"detail": str(exc)}, status_code=409)
    except ScheduleNotFoundError as exc:
        return JSON({"detail": str(exc)}, status_code=404)
    except DuplicateSubmissionError as exc:
        return JSON({"detail": str(exc)}, status_code=409)

    return build_intake_response(result, request=request, status_code=200)


@api.get(
    "/schedules/{date}/preview",
    status_code=200,
    tags=["schedules"],
    summary="Get schedule preview",
    description="Returns schedule with items and linked song data for a given date. Requires authentication.",
    guards=[IsAuthenticated],
)
async def schedule_preview_endpoint(date: str):
    try:
        parsed = dt.date.fromisoformat(date)
    except ValueError:
        return JSON({"detail": "Invalid date format. Use YYYY-MM-DD."}, status_code=400)

    preview = await get_schedule_preview_async(parsed)
    if not preview:
        return JSON({"detail": f"No published or ready schedule for {date}."}, status_code=404)

    return preview


def authorize_n8n_request(n8n_api_key: str | None):
    expected_key = getattr(settings, "N8N_INTAKE_API_KEY", "")
    if not expected_key or not n8n_api_key:
        return JSON({"detail": "Unauthorized"}, status_code=401)

    if not constant_time_compare(n8n_api_key, expected_key):
        return JSON({"detail": "Unauthorized"}, status_code=401)

    return None


def build_preview_url(
    schedule_date: dt.date,
    *,
    request: Request | None = None,
) -> str:
    preview_path = reverse(
        "service_preview",
        kwargs={"date": schedule_date.isoformat()},
    )
    if request is None:
        return preview_path

    forwarded_proto = (
        request.headers.get("x-forwarded-proto")
        or request.headers.get("X-Forwarded-Proto")
        or "https"
    )
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("X-Forwarded-Host")
        or request.headers.get("host")
        or request.headers.get("Host")
    )
    if not host:
        return preview_path

    return f"{forwarded_proto}://{host}{preview_path}"


def build_intake_response(
    result,
    *,
    request: Request | None = None,
    status_code: int,
) -> IntakeResponse:
    confirmation_text = (
        f"Schedule for {result.schedule.date.isoformat()} received and "
        f"{result.created_or_updated} successfully."
    )
    return IntakeResponse(
        schedule_id=str(result.schedule.pk),
        date=result.schedule.date.isoformat(),
        created_or_updated=result.created_or_updated,
        items_created=result.items_created,
        items_updated=result.items_updated,
        confirmation_text=confirmation_text,
        preview_url=build_preview_url(result.schedule.date, request=request),
    )

