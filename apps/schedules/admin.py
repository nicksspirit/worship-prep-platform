from typing import Callable, Protocol, cast

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action

from apps.schedules.choices import ScheduleItemStatus
from apps.schedules.models import (
    Contact,
    ContentSubmission,
    ScheduleItem,
    ScheduleTemplate,
    ServiceSchedule,
    TemplateItem,
)


class _AdminDisplayCallable(Protocol):
    """Protocol for admin list_display/readonly_fields callables with short_description."""

    short_description: str

    def __call__(self, obj: ScheduleItem | None) -> str: ...


def _admin_display(description: str):
    """Attach short_description to a callable so Django admin shows it; satisfies type checkers."""

    def decorator(
        func: Callable[..., str],
    ) -> _AdminDisplayCallable:
        setattr(func, "short_description", description)
        return cast(_AdminDisplayCallable, func)

    return decorator


class ScheduleItemInline(TabularInline):
    model = ScheduleItem
    extra = 0
    tab = True
    show_change_link = True
    max_num = 0
    readonly_fields = [
        "position",
        "item_type",
        "title",
        "start_time",
        "end_time",
        "status",
        "assigned_contact",
        "quick_actions",
    ]
    fields = [
        "position",
        "item_type",
        "title",
        "start_time",
        "end_time",
        "status",
        "assigned_contact",
        "quick_actions",
    ]

    @_admin_display("Actions")
    def quick_actions(self, obj: ScheduleItem | None) -> str:
        if not obj or not obj.pk:
            return ""

        if obj.status == ScheduleItemStatus.APPROVED:
            return format_html(
                '<span style="color: var(--color-chapel-success-500); font-weight: bold;">Approved</span>'
            )

        url = reverse("admin:schedules_scheduleitem_mark_as_approved", args=[obj.pk])
        # We append a query param to know where to redirect back
        redirect_url = reverse(
            "admin:schedules_serviceschedule_change", args=[obj.schedule.pk]
        )
        return format_html(
            '<a class="button" style="background-color: var(--color-chapel-primary-500); color: white; padding: 1px 2px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold;" href="{}?next={}">Mark Approved</a>',
            url,
            redirect_url,
        )


@admin.register(ServiceSchedule)
class ServiceScheduleAdmin(ModelAdmin):
    list_display = ["date", "title", "status", "updated_on"]
    list_filter = ["status", "date"]
    search_fields = ["title", "notes"]
    ordering = ["-date"]
    inlines = [ScheduleItemInline]
    actions_detail = ["add_schedule_item"]
    readonly_fields = ["updated_on", "deleted_on"]
    fieldsets = (
        (
            None,
            {
                "fields": [
                    "title",
                    "status",
                    "template",
                    "notes",
                ]
            },
        ),
        (
            "Metadata",
            {
                "classes": ["collapse"],
                "fields": [
                    "date",
                    "updated_on",
                    "deleted_on",
                ],
            },
        ),
    )

    @action(description="Add Schedule Item", url_path="add-item")
    def add_schedule_item(self, request, object_id: int):
        base_url = reverse("admin:schedules_scheduleitem_add")
        return redirect(f"{base_url}?schedule={object_id}")


class TemplateItemInline(TabularInline):
    model = TemplateItem
    extra = 0
    tab = True
    fields = ["position", "item_type", "title", "is_required", "default_contact"]


@admin.register(ScheduleTemplate)
class ScheduleTemplateAdmin(ModelAdmin):
    list_display = ["name", "is_default", "updated_on"]
    list_filter = ["is_default"]
    search_fields = ["name", "description"]
    inlines = [TemplateItemInline]


@admin.register(ScheduleItem)
class ScheduleItemAdmin(ModelAdmin):
    list_display = [
        "schedule",
        "position",
        "title",
        "item_type",
        "status",
        "assigned_contact",
    ]
    list_filter = ["item_type", "status", "schedule__date"]
    search_fields = ["title", "notes", "assigned_contact__name"]
    ordering = ["schedule__date", "position"]
    actions_detail = ["mark_as_approved"]
    actions_row = ["mark_as_approved"]
    actions = ["mark_queryset_as_approved"]

    @action(description="Mark as Approved", url_path="mark-approved")
    def mark_as_approved(self, request, object_id: int):
        ScheduleItem.objects.filter(pk=object_id).update(
            status=ScheduleItemStatus.APPROVED
        )
        self.message_user(request, "Schedule item marked as approved.")

        # If 'next' is provided in query params, redirect there (useful for inlines)
        next_url = request.GET.get("next")
        if next_url:
            return redirect(next_url)

        return redirect(
            request.META.get(
                "HTTP_REFERER", reverse("admin:schedules_scheduleitem_changelist")
            )
        )

    @admin.action(description="Mark selected items as Approved")
    def mark_queryset_as_approved(self, request, queryset):
        count = queryset.update(status=ScheduleItemStatus.APPROVED)
        self.message_user(request, f"{count} schedule items marked as approved.")


@admin.register(Contact)
class ContactAdmin(ModelAdmin):
    list_display = ["name", "role", "phone", "email"]
    list_filter = ["role"]
    search_fields = ["name", "phone", "email"]
    ordering = ["name"]


@admin.register(ContentSubmission)
class ContentSubmissionAdmin(ModelAdmin):
    list_display = ["source", "sender_name", "target_date", "status", "created_on"]
    list_filter = ["source", "status", "target_date"]
    search_fields = ["sender_name", "sender_phone", "parsed_title", "raw_content"]
    ordering = ["-created_on"]
