from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.schedules.models import (
    Contact,
    ContentSubmission,
    ScheduleItem,
    ScheduleTemplate,
    ServiceSchedule,
    TemplateItem,
)


class ScheduleItemInline(TabularInline):
    model = ScheduleItem
    extra = 0
    tab = True
    fields = [
        "position",
        "item_type",
        "title",
        "start_time",
        "end_time",
        "status",
        "assigned_contact",
    ]


@admin.register(ServiceSchedule)
class ServiceScheduleAdmin(ModelAdmin):
    list_display = ["date", "title", "status", "updated_on"]
    list_filter = ["status", "date"]
    search_fields = ["title", "notes"]
    ordering = ["-date"]
    inlines = [ScheduleItemInline]


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
    list_display = ["schedule", "position", "title", "item_type", "status", "assigned_contact"]
    list_filter = ["item_type", "status", "schedule__date"]
    search_fields = ["title", "notes", "assigned_contact__name"]
    ordering = ["schedule__date", "position"]


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
