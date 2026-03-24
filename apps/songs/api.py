import logging
from typing import Annotated

from django_bolt import BoltAPI, JSON, Request
from django_bolt.openapi import OpenAPIConfig
from django_bolt.param_functions import Header

from apps.schedules.api import build_preview_url
from apps.songs.schemas import SongIntakePayload, SongIntakeResponse
from apps.songs.services.intake import intake_song
from apps.users.api_keys import API_KEY_HEADER, authorize_api_key
from apps.users.models import APIKeyScope

logger = logging.getLogger("apps.songs.inbound")


api = BoltAPI(
    openapi_config=OpenAPIConfig(
        title="Worship Prep Platform API",
        description="Song lyrics intake and schedule endpoints.",
        version="1.0.0",
    ),
    prefix="/api/v1",
)


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
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
):
    authorized = await authorize_api_key(
        api_key,
        request=request,
        required_scopes=(APIKeyScope.SONGS_WRITE,),
    )
    if isinstance(authorized, JSON):
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
