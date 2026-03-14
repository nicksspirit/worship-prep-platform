import logging
from typing import Annotated

from django.conf import settings
from django.utils.crypto import constant_time_compare
from django_bolt import BoltAPI, JSON
from django_bolt.middleware import Middleware
from django_bolt.openapi import OpenAPIConfig
from django_bolt.param_functions import Header

from apps.schedules.exceptions import (
    DuplicateSubmissionError,
    ScheduleNotFoundError,
)
from apps.schedules.schemas import IntakeResponse, WhatsAppScheduleIntakePayload
from apps.schedules.services.intake import intake_whatsapp_schedule, patch_whatsapp_schedule

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
        version="1.0.0"
    ),
    middleware=[InboundRequestDebugMiddleware],
    prefix="/api/v1",
)


@api.post(
    "/schedules/intake/whatsapp",
    response_model=IntakeResponse,
    status_code=201,
    tags=["schedules"],
    summary="Ingest WhatsApp Sunday schedule",
    description="Creates or updates the target Sunday schedule from a parsed WhatsApp agenda payload.",
)
async def intake_schedule_from_whatsapp(
    payload: WhatsAppScheduleIntakePayload,
    n8n_api_key: Annotated[str | None, Header(alias="X-N8N-Api-Key")] = None,
):
    authorized = authorize_n8n_request(n8n_api_key)
    if authorized is not None:
        return authorized

    try:
        result = await intake_whatsapp_schedule(payload)
    except DuplicateSubmissionError as exc:
        return JSON({"detail": str(exc)}, status_code=409)
    return build_intake_response(result, status_code=201)


@api.patch(
    "/schedules/intake/whatsapp",
    response_model=IntakeResponse,
    status_code=200,
    tags=["schedules"],
    summary="Update WhatsApp Sunday schedule",
    description="Applies a partial update to an existing Sunday schedule using the parsed WhatsApp agenda payload.",
)
async def patch_schedule_from_whatsapp(
    payload: WhatsAppScheduleIntakePayload,
    n8n_api_key: Annotated[str | None, Header(alias="X-N8N-Api-Key")] = None,
):
    authorized = authorize_n8n_request(n8n_api_key)
    if authorized is not None:
        return authorized

    try:
        result = await patch_whatsapp_schedule(payload)
    except ScheduleNotFoundError as exc:
        return JSON({"detail": str(exc)}, status_code=404)
    except DuplicateSubmissionError as exc:
        return JSON({"detail": str(exc)}, status_code=409)

    return build_intake_response(result, status_code=200)


def authorize_n8n_request(n8n_api_key: str | None):
    expected_key = getattr(settings, "N8N_INTAKE_API_KEY", "")
    if not expected_key or not n8n_api_key:
        return JSON({"detail": "Unauthorized"}, status_code=401)

    if not constant_time_compare(n8n_api_key, expected_key):
        return JSON({"detail": "Unauthorized"}, status_code=401)

    return None


def build_intake_response(result, *, status_code: int) -> IntakeResponse:
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
    )

