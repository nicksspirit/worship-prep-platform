import datetime as dt
from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from apps.schedules.choices import ScheduleItemStatus, ScheduleItemType, ServiceScheduleStatus
from apps.schedules.models import ServiceSchedule
from apps.schedules.services.preview import get_schedule_preview
from apps.schedules.templates import (
    EmptyStateData,
    ScheduleItemPreviewData,
    ScheduleListPage,
    SchedulePreviewData,
    ScheduleSummary,
    ServicePreviewPage,
    SongPreviewData,
)
from apps.users.templates import RenderableTemplate

VISIBLE_SCHEDULE_STATUSES = (
    ServiceScheduleStatus.READY,
    ServiceScheduleStatus.PUBLISHED,
)
SCHEDULE_STATUS_LABELS = dict(ServiceScheduleStatus.choices)
ITEM_STATUS_LABELS = dict(ScheduleItemStatus.choices)
ITEM_TYPE_LABELS = dict(ScheduleItemType.choices)


def format_service_date(value: dt.date) -> str:
    return f"{value.strftime('%A, %B')} {value.day}, {value.year}"


def format_time_window(start_time: str | None, end_time: str | None) -> str:
    if start_time and end_time:
        return f"{start_time} - {end_time}"
    if start_time:
        return start_time
    return "--"


def build_empty_state(date_label: str | None = None) -> EmptyStateData:
    heading = "No schedule yet"
    if date_label:
        heading = f"No schedule for {date_label} yet"

    return EmptyStateData(
        heading=heading,
        message=(
            "Once a service schedule is available, it will appear here "
            "with the full order of service and any linked songs."
        ),
        link_url=reverse("schedule_landing"),
        link_label="Back to schedule list",
    )


def build_schedule_preview_page(schedule_date: dt.date) -> SchedulePreviewData | None:
    preview = get_schedule_preview(schedule_date, include_unpublished=True)
    if preview is None:
        return None

    items: list[ScheduleItemPreviewData] = []
    for item in preview.items:
        songs = [
            SongPreviewData(
                song_id=song.song_id,
                title=song.title,
                formatted_lyrics=song.formatted_lyrics,
                filename=song.filename,
                slide_count=song.slide_count,
                position=song.position,
            )
            for song in item.songs
        ]
        items.append(
            ScheduleItemPreviewData(
                position=item.position,
                item_type=item.item_type,
                item_label=ITEM_TYPE_LABELS.get(item.item_type, item.item_type.replace("_", " ").title()),
                title=item.title,
                time_label=format_time_window(item.start_time, item.end_time),
                leader_name=item.leader_name,
                leader_label=item.leader_name or "TBD",
                notes=item.notes,
                status=item.status,
                status_label=ITEM_STATUS_LABELS.get(
                    item.status,
                    item.status.replace("_", " ").title(),
                ),
                is_complete=item.is_complete,
                songs=songs,
            )
        )

    return SchedulePreviewData(
        schedule_id=preview.schedule_id,
        date=preview.date,
        display_date=format_service_date(schedule_date),
        title=preview.title or "Sunday Service",
        status=preview.status,
        status_label=SCHEDULE_STATUS_LABELS.get(
            preview.status,
            preview.status.replace("_", " ").title(),
        ),
        prev_url=(
            reverse("service_preview", kwargs={"date": preview.prev_date})
            if preview.prev_date
            else None
        ),
        next_url=(
            reverse("service_preview", kwargs={"date": preview.next_date})
            if preview.next_date
            else None
        ),
        items=items,
    )


class ScheduleLandingView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs) -> HttpResponse:
        upcoming_schedule = (
            ServiceSchedule.objects.filter(
                status__in=VISIBLE_SCHEDULE_STATUSES,
                date__gte=dt.date.today(),
            )
            .order_by("date")
            .first()
        )
        if upcoming_schedule is not None:
            return redirect(
                "service_preview",
                date=upcoming_schedule.date.isoformat(),
            )

        schedules = (
            ServiceSchedule.objects.filter(status__in=VISIBLE_SCHEDULE_STATUSES)
            .annotate(item_count=Count("schedule_items"))
            .order_by("-date")
        )
        summaries = [
            ScheduleSummary(
                date=schedule.date.isoformat(),
                display_date=format_service_date(schedule.date),
                title=schedule.title or "Sunday Service",
                item_count=schedule.item_count,
                preview_url=reverse(
                    "service_preview",
                    kwargs={"date": schedule.date.isoformat()},
                ),
                status=schedule.status,
                status_label=schedule.get_status_display(),
            )
            for schedule in schedules
        ]
        page = cast(
            RenderableTemplate,
            ScheduleListPage(
                title="Service Schedules",
                schedules=summaries,
                empty_state=(
                    None
                    if summaries
                    else EmptyStateData(
                        heading="No published schedules yet",
                        message=(
                            "Published and ready services will appear here once the worship "
                            "team has finalized them."
                        ),
                        link_url=None,
                        link_label=None,
                    )
                ),
            ),
        )
        return page.render(request)


class ServicePreviewView(LoginRequiredMixin, View):
    def get(self, request, date: str, *args, **kwargs) -> HttpResponse:
        try:
            parsed_date = dt.date.fromisoformat(date)
        except ValueError:
            parsed_date = None

        schedule = build_schedule_preview_page(parsed_date) if parsed_date else None
        empty_state = None
        title = "Service Preview"

        if schedule is None:
            date_label = format_service_date(parsed_date) if parsed_date else date
            empty_state = build_empty_state(date_label)
            title = empty_state.heading
        else:
            title = f"Service Preview | {schedule.display_date}"

        page = cast(
            RenderableTemplate,
            ServicePreviewPage(
                title=title,
                schedule=schedule,
                empty_state=empty_state,
            ),
        )
        return page.render(request)
