import logging
from typing import Annotated

from django.conf import settings
from django.utils.crypto import constant_time_compare
from django_bolt import BoltAPI, JSON, Request
from django_bolt.openapi import OpenAPIConfig
from django_bolt.param_functions import Header

from apps.schedules.api import build_preview_url
from apps.songs.schemas import SongIntakePayload, SongIntakeResponse
from apps.songs.services.intake import intake_song

logger = logging.getLogger("apps.songs.inbound")


api = BoltAPI(
    openapi_config=OpenAPIConfig(
        title="Worship Prep Platform API",
        description="Song lyrics intake and schedule endpoints.",
        version="1.0.0",
    ),
    prefix="/api/v1",
)


def _authorize_n8n_request(n8n_api_key: str | None):
    expected_key = getattr(settings, "N8N_INTAKE_API_KEY", "")
    if not expected_key or not n8n_api_key:
        return JSON({"detail": "Unauthorized"}, status_code=401)
    if not constant_time_compare(n8n_api_key, expected_key):
        return JSON({"detail": "Unauthorized"}, status_code=401)
    return None


@api.post(
    "/songs/intake",
    status_code=201,
    tags=["songs"],
    summary="Ingest song lyrics",
    description="Creates or dedup-matches a Song with formatted lyrics, optionally linking to a ScheduleItem.",
)
async def intake_song_endpoint(
    payload: SongIntakePayload,
    request: Request | None = None,
    n8n_api_key: Annotated[str | None, Header(alias="X-N8N-Api-Key")] = None,
):
    authorized = _authorize_n8n_request(n8n_api_key)
    if authorized is not None:
        return authorized

    result = await intake_song(payload)
    filename = result.song.lyrics_file.name
    if filename and "/" in filename:
        filename = filename.split("/")[-1]
    elif not filename:
        filename = payload.filename

    preview_url = None
    if payload.schedule_date is not None:
        preview_url = build_preview_url(payload.schedule_date, request=request)

    return SongIntakeResponse(
        song_id=str(result.song.pk),
        song_title=result.song.title,
        filename=filename,
        slide_count=result.song.slide_count or 0,
        linked_to_schedule=result.linked_to_schedule,
        schedule_date=result.schedule_date,
        is_existing=result.is_existing,
        preview_url=preview_url,
    )
