from datetime import datetime
from typing import Annotated

from django_bolt.serializers import Meta, Serializer, model_validator

TITLE_PATTERN = r"^[^\x00-\x1f\x7f]*[^\s\x00-\x1f\x7f][^\x00-\x1f\x7f]*$"
LINE_PATTERN = r"^[^\x00-\x1f\x7f]*$"

Title = Annotated[str, Meta(min_length=1, max_length=160, pattern=TITLE_PATTERN)]
Line = Annotated[str, Meta(max_length=160, pattern=LINE_PATTERN)]


class SchedulePreviewSlideInput(Serializer, forbid_unknown_fields=True):
    lines: Annotated[list[Line], Meta(max_length=10)]
    section_label: Annotated[str, Meta(max_length=80, pattern=LINE_PATTERN)] = ""


class SchedulePreviewSongInput(Serializer, forbid_unknown_fields=True):
    title: Title
    slides: Annotated[list[SchedulePreviewSlideInput], Meta(min_length=1, max_length=50)]


SectionSongs = Annotated[
    list[SchedulePreviewSongInput], Meta(min_length=1, max_length=30)
]


class SchedulePreviewSectionsInput(Serializer, forbid_unknown_fields=True):
    call_to_worship: SectionSongs
    praise: SectionSongs
    worship: SectionSongs
    special_song: SectionSongs | None = None


class PublishSchedulePreviewInput(Serializer, forbid_unknown_fields=True):
    title: Title
    sections: SchedulePreviewSectionsInput

    @model_validator
    def validate_song_count(self) -> None:
        """Limit the total across the service order."""

        sections = self.sections
        if (
            sum(
                map(
                    len,
                    (
                        sections.call_to_worship,
                        sections.praise,
                        sections.worship,
                        sections.special_song or [],
                    ),
                )
            )
            > 30
        ):
            raise ValueError("A schedule preview can contain at most 30 songs in total.")


class PublishSchedulePreviewResponse(Serializer):
    preview_url: str
    expires_at: datetime


class SchedulePreviewErrorDetail(Serializer):
    code: str
    message: str


class SchedulePreviewErrorResponse(Serializer):
    error: SchedulePreviewErrorDetail
