import json
from typing import Annotated

from django.conf import settings
from django.urls import reverse
from django_bolt import BoltAPI, OpenAPIConfig, Request, Response
from django_bolt.param_functions import Header
from structlog.contextvars import get_contextvars

from apps.api_keys.services import AuthorizationDenied
from apps.common.bolt_database import call_bolt_database
from apps.common.request_logging import BoltRequestLogging
from apps.schedule_previews.schema import (
    PublishSchedulePreviewInput,
    PublishSchedulePreviewResponse,
    SchedulePreviewErrorDetail,
    SchedulePreviewErrorResponse,
)
from apps.schedule_previews.services.content import PreviewContent, PublishRequestDetails
from apps.schedule_previews.services.publish import PublishRateLimited, publish_preview

api = BoltAPI(
    prefix="/api/v1",
    middleware=[BoltRequestLogging],
    enable_logging=False,
    openapi_config=OpenAPIConfig(
        title="Schedule Previews", version="1.0.0", enabled=False
    ),
)


@api.post(
    "/schedule-previews",
    status_code=201,
    response_model=PublishSchedulePreviewResponse,
    tags=["schedule previews"],
    summary="Publish a schedule preview",
    description=(
        "Requires `schedule.preview.publish`. Include Call to Worship, Praise, and Worship "
        "with an optional Special Song section. Each publish creates a new unlisted URL. Anyone with it "
        "can view the submitted lyrics until the server-set expiry."
    ),
)
async def publish_schedule_preview(
    request: Request,
    payload: PublishSchedulePreviewInput,
    authorization: Annotated[str, Header(alias="Authorization")] = "",
):
    """Publish the submitted song slides and return the browser link."""

    sections = payload.sections
    content: PreviewContent = {
        "title": payload.title,
        "sections": [
            {
                "title": title,
                "songs": [
                    {
                        "title": song.title,
                        "slides": [
                            {"section_label": slide.section_label, "lines": slide.lines}
                            for slide in song.slides
                        ],
                    }
                    for song in songs
                ],
            }
            for title, songs in (
                ("Call to Worship", sections.call_to_worship),
                ("Praise", sections.praise),
                ("Worship", sections.worship),
                ("Special Song", sections.special_song),
            )
            if songs
        ],
    }
    request_details: PublishRequestDetails = {
        "method": request.method,
        "path": request.path,
        "source_ip": getattr(request, "META", {}).get("REMOTE_ADDR") or None,
        "request_id": get_contextvars().get("request_id"),
    }
    outcome = await call_bolt_database(
        publish_preview, content, authorization, request_details, json.loads(request.body)
    )
    if isinstance(outcome, AuthorizationDenied):
        return Response(
            SchedulePreviewErrorResponse(
                error=SchedulePreviewErrorDetail(
                    code=outcome.code, message=outcome.message
                )
            ),
            status_code=401 if outcome.code == "invalid_api_key" else 403,
        )
    if isinstance(outcome, PublishRateLimited):
        return Response(
            SchedulePreviewErrorResponse(
                error=SchedulePreviewErrorDetail(
                    code="rate_limited", message="Try publishing again in a moment."
                )
            ),
            status_code=429,
            headers={"Retry-After": str(outcome.retry_after)},
        )

    path = reverse("schedule_preview", kwargs={"preview_id": outcome.id})
    return Response(
        PublishSchedulePreviewResponse(
            preview_url=f"{settings.SCHEDULE_PREVIEW_APP_ORIGIN.rstrip('/')}{path}",
            expires_at=outcome.expires_at,
        ),
        status_code=201,
        headers={"Cache-Control": "no-store"},
    )
