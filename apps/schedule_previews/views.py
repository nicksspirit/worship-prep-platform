from uuid import UUID

from django.http import HttpRequest
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.schedule_previews.services.read import read_preview
from apps.schedule_previews.templates import (
    PreviewSectionProps,
    PreviewSlideProps,
    PreviewSongProps,
    SchedulePreviewPage,
)


@never_cache
@require_safe
def show_schedule_preview(request: HttpRequest, preview_id: UUID) -> TemplateResponse:
    """Render a live preview for anyone who has its link."""

    preview = read_preview(preview_id)
    content, created_at = preview if preview is not None else (None, None)
    sections = (
        [
            PreviewSectionProps(
                title=section["title"],
                songs=[
                    PreviewSongProps(
                        title=song["title"],
                        slides=[
                            PreviewSlideProps(
                                index, slide["section_label"], slide["lines"]
                            )
                            for index, slide in enumerate(song["slides"], start=1)
                        ],
                    )
                    for song in section["songs"]
                ],
            )
            for section in content["sections"]
        ]
        if content is not None
        else []
    )
    response = SchedulePreviewPage(
        title=content["title"] if content is not None else None,
        sections=sections,
        created_date=timezone.localdate(created_at).isoformat() if created_at else None,
    ).render(request)
    if content is None:
        response.status_code = 404
    response["Referrer-Policy"] = "no-referrer"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
