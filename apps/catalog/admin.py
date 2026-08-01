from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.catalog.models import (
    CatalogActivation,
    CatalogEntry,
    CatalogImportEvent,
    CatalogImportRun,
    CatalogSnapshot,
    CatalogState,
)


class ReadOnlyAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CatalogImportRun)
class CatalogImportRunAdmin(ReadOnlyAdmin):
    list_display = ("id", "status", "song_count", "warning_count", "received_at")
    list_filter = ("status", "contract_version")
    search_fields = ("id", "exporter_instance_id", "failure_summary")


@admin.register(CatalogImportEvent)
class CatalogImportEventAdmin(ReadOnlyAdmin):
    list_display = ("import_run", "source", "event", "outcome", "occurred_at")
    list_filter = ("source", "outcome")


@admin.register(CatalogSnapshot)
class CatalogSnapshotAdmin(ReadOnlyAdmin):
    list_display = ("id", "status", "entry_count", "completed_at")


@admin.register(CatalogEntry)
class CatalogEntryAdmin(ReadOnlyAdmin):
    list_display = ("song_uid", "title", "rights_status", "content_changed_at")
    list_filter = ("rights_status",)
    search_fields = ("song_uid", "title")


admin.site.register(CatalogState, ReadOnlyAdmin)
admin.site.register(CatalogActivation, ReadOnlyAdmin)
