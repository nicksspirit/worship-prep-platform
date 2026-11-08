import json

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.schedule_previews.models import SchedulePreview


@admin.register(SchedulePreview)
class SchedulePreviewAdmin(ModelAdmin):
    list_display = ("title", "created_at", "expires_at", "preview_link")
    search_fields = ("content__title",)
    ordering = ("-expires_at",)
    readonly_fields = fields = (
        *list_display,
        "publish_request",
        "request_id",
        "source_ip",
        "api_key_id",
        "payload",
    )

    @admin.display(description="Title")
    def title(self, obj: SchedulePreview) -> str:
        return str(obj)

    @admin.display(description="Publish request")
    def publish_request(self, obj: SchedulePreview) -> str | None:
        if obj.request_details is None:
            return None
        return f"{obj.request_details['method']} {obj.request_details['path']}"

    @admin.display(description="Request ID")
    def request_id(self, obj: SchedulePreview) -> str | None:
        return (obj.request_details or {}).get("request_id")

    @admin.display(description="Source IP")
    def source_ip(self, obj: SchedulePreview) -> str | None:
        return (obj.request_details or {}).get("source_ip")

    @admin.display(description="API key ID")
    def api_key_id(self, obj: SchedulePreview) -> int | None:
        return obj.publisher_key_id

    @admin.display(description="Payload")
    def payload(self, obj: SchedulePreview) -> str:
        if obj.submitted_payload is None:
            return format_html(
                '<p>{}</p><pre style="white-space: pre-wrap; overflow-wrap: anywhere">{}</pre>',
                "Original request payload was not recorded. Showing the stored preview.",
                json.dumps(obj.content, indent=2, ensure_ascii=False),
            )
        return format_html(
            '<pre style="white-space: pre-wrap; overflow-wrap: anywhere">{}</pre>',
            json.dumps(obj.submitted_payload, indent=2, ensure_ascii=False),
        )

    @admin.display(description="Preview")
    def preview_link(self, obj: SchedulePreview) -> str:
        if obj.expires_at <= timezone.now():
            return "Expired"
        return format_html(
            '<a href="{}">Open preview</a>',
            reverse("schedule_preview", kwargs={"preview_id": obj.pk}),
        )

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
