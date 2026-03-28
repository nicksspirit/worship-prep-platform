import datetime as dt
from typing import Annotated

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import connections
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse
from django_bolt import BoltAPI, JSON, Request
from django_bolt.auth import IsAuthenticated
from django_bolt.health import add_health_check, register_health_checks
from django_bolt.logging import LoggingConfig
from django_bolt.middleware import CompressionConfig
from django_bolt.openapi import OpenAPIConfig
from django_bolt.param_functions import Header, Query

from apps.schedules.exceptions import (
    DuplicateScheduleItemTypeError,
    DuplicateSubmissionError,
    ScheduleNotFoundError,
)
from apps.schedules.schemas import (
    IntakeResponse,
    PreviewUrlHeaders,
    ScheduleIntakePayload,
    ScheduleListQuery,
)
from apps.schedules.services.intake import intake_schedule, patch_schedule
from apps.schedules.services.preview import (
    get_schedule_preview_async,
    get_upcoming_schedule_date,
    list_recent_schedule_summaries_async,
)
from apps.users.api_keys import API_KEY_HEADER, authorize_api_key
from apps.users.models import APIKeyScope

DJANGO_ENV = getattr(settings, "DJANGO_ENV", "local")

BOLT_HEALTH_PREFIX = "/api/v1"


def _check_database_sync() -> tuple[bool, str]:
    try:
        connection = connections["default"]
        connection.ensure_connection()
        return True, "Database OK"
    except Exception as exc:
        return False, f"Database error: {exc}"


def _check_storage_sync() -> tuple[bool, str]:
    filename = "__healthcheck__/bolt-storage-check.txt"
    try:
        saved_name = default_storage.save(filename, ContentFile(b"ok"))
        exists = default_storage.exists(saved_name)
        default_storage.delete(saved_name)
        if not exists:
            return False, "Storage write/read failed"
        return True, "Storage OK"
    except Exception as exc:
        return False, f"Storage error: {exc}"


async def check_database() -> tuple[bool, str]:
    return await sync_to_async(_check_database_sync)()


async def check_storage() -> tuple[bool, str]:
    return await sync_to_async(_check_storage_sync)()


add_health_check(check_database)
add_health_check(check_storage)

bolt_logging_config = LoggingConfig(
    logger_name="django_bolt.logging",
    skip_paths={
        f"{BOLT_HEALTH_PREFIX}/health",
        f"{BOLT_HEALTH_PREFIX}/ready",
    },
    request_log_fields={"method", "path", "client_ip", "user_agent"},
    response_log_fields={"status_code", "duration"},
    obfuscate_headers={"authorization", "cookie", "x-api-key", "x-n8n-api-key"},
    sample_rate=1.0 if DJANGO_ENV in ("local", "test") else 0.1,
    min_duration_ms=0 if DJANGO_ENV in ("local", "test") else 100,
)

api = BoltAPI(
    openapi_config=OpenAPIConfig(
        title="Worship Prep Platform API",
        description="Inbound schedule intake and workflow automation endpoints.",
        version="1.0.0",
    ),
    django_middleware=True,
    enable_logging=True,
    logging_config=bolt_logging_config,
    compression=CompressionConfig(backend="gzip", minimum_size=500),
    prefix=BOLT_HEALTH_PREFIX,
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
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
    preview_headers: Annotated[PreviewUrlHeaders, Header()] = PreviewUrlHeaders(),
):
    authorized = await authorize_api_key(
        api_key,
        request=request,
        required_scopes=(APIKeyScope.SCHEDULES_WRITE,),
    )
    if isinstance(authorized, JSON):
        return authorized

    try:
        result = await intake_schedule(payload)
    except DuplicateScheduleItemTypeError as exc:
        return JSON({"detail": str(exc)}, status_code=409)
    except DuplicateSubmissionError as exc:
        return JSON({"detail": str(exc)}, status_code=409)
    return build_intake_response(result, preview_headers=preview_headers, status_code=201)


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
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
    preview_headers: Annotated[PreviewUrlHeaders, Header()] = PreviewUrlHeaders(),
):
    authorized = await authorize_api_key(
        api_key,
        request=request,
        required_scopes=(APIKeyScope.SCHEDULES_WRITE,),
    )
    if isinstance(authorized, JSON):
        return authorized

    try:
        result = await patch_schedule(payload)
    except DuplicateScheduleItemTypeError as exc:
        return JSON({"detail": str(exc)}, status_code=409)
    except ScheduleNotFoundError as exc:
        return JSON({"detail": str(exc)}, status_code=404)
    except DuplicateSubmissionError as exc:
        return JSON({"detail": str(exc)}, status_code=409)

    return build_intake_response(result, preview_headers=preview_headers, status_code=200)


@api.get(
    "/schedules",
    status_code=200,
    tags=["schedules"],
    summary="List schedules",
    description=(
        "Returns recent visible schedules, or the next Sunday's schedule detail when "
        "`upcoming=true` is provided."
    ),
)
async def schedule_lookup_list_endpoint(
    schedule_list_query: Annotated[ScheduleListQuery, Query()],
    request: Request | None = None,
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
):
    authorized = await authorize_api_key(
        api_key,
        request=request,
        required_scopes=(APIKeyScope.SCHEDULES_READ,),
    )

    if isinstance(authorized, JSON):
        return authorized

    if schedule_list_query.upcoming:
        upcoming_date = get_upcoming_schedule_date()
        preview = await get_schedule_preview_async(
            upcoming_date, include_unpublished=True
        )

        if not preview:
            return JSON(
                {"detail": f"No schedule found for {upcoming_date.isoformat()}."},
                status_code=404,
            )
        return preview

    return await list_recent_schedule_summaries_async(limit=5)


@api.get(
    "/schedules/{date}",
    status_code=200,
    tags=["schedules"],
    summary="Get schedule by date",
    description="Returns schedule detail for the given date using n8n API key authentication.",
)
async def schedule_lookup_detail_endpoint(
    date: str,
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
):
    authorized = await authorize_api_key(
        api_key,
        required_scopes=(APIKeyScope.SCHEDULES_READ,),
    )
    if isinstance(authorized, JSON):
        return authorized

    try:
        parsed = dt.date.fromisoformat(date)
    except ValueError:
        return JSON({"detail": "Invalid date format. Use YYYY-MM-DD."}, status_code=400)

    preview = await get_schedule_preview_async(parsed, include_unpublished=True)
    if not preview:
        return JSON({"detail": f"No schedule found for {date}."}, status_code=404)

    return preview


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
        return JSON(
            {"detail": f"No published or ready schedule for {date}."}, status_code=404
        )

    return preview


def build_preview_url(
    schedule_date: dt.date, *, preview_headers: PreviewUrlHeaders | None = None
) -> str:
    preview_path = reverse(
        "service_preview",
        kwargs={"date": schedule_date.isoformat()},
    )
    if preview_headers is None:
        return preview_path

    forwarded_proto = preview_headers.x_forwarded_proto or "https"
    host = preview_headers.x_forwarded_host or preview_headers.host
    if not host:
        return preview_path

    return f"{forwarded_proto}://{host}{preview_path}"


def build_intake_response(
    result,
    *,
    preview_headers: PreviewUrlHeaders | None = None,
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
        preview_url=build_preview_url(
            result.schedule.date, preview_headers=preview_headers
        ),
    )


register_health_checks(api)
