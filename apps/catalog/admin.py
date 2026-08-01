from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import action

from apps.catalog.forms import CatalogSongRightsAdminForm
from apps.catalog.importer import recover_import_run, rollback_to_snapshot
from apps.catalog.models import (
    CatalogActivation,
    CatalogEntry,
    CatalogImportEvent,
    CatalogImportRun,
    CatalogSnapshot,
    CatalogSongRights,
    CatalogState,
    ImportStatus,
    LyricsRightsChange,
)
from apps.catalog.rights import change_lyrics_rights


class ReadOnlyAdmin(ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CatalogImportEventInline(admin.TabularInline):
    model = CatalogImportEvent
    extra = 0
    can_delete = False
    fields = ("source", "event", "outcome", "occurred_at", "details")
    readonly_fields = fields
    ordering = ("occurred_at", "pk")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CatalogImportRun)
class CatalogImportRunAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "status",
        "trigger",
        "song_count",
        "warning_count",
        "received_at",
    )
    list_filter = ("status", "trigger", "contract_version")
    search_fields = ("id", "exporter_instance_id", "failure_summary")
    inlines = [CatalogImportEventInline]
    actions = ["recover_selected_runs"]
    actions_detail = ["recover_run"]

    @admin.action(description=_("Recover selected failed Catalog Imports"))
    def recover_selected_runs(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request, _("Only Superusers may recover imports."), messages.ERROR
            )
            return
        recovered = 0
        for run in queryset.filter(status=ImportStatus.FAILED):
            try:
                recover_import_run(run, user=request.user)
            except Exception as exc:
                self.message_user(
                    request,
                    _("Catalog Import %(run)s still failed: %(error)s")
                    % {"run": run.pk, "error": exc},
                    messages.ERROR,
                )
            else:
                recovered += 1
        self.message_user(
            request,
            _("Recovered %(count)d Catalog Import(s).") % {"count": recovered},
            messages.SUCCESS,
        )

    @action(description=_("Recover Catalog Import"), url_path="recover")
    def recover_run(self, request, object_id: str):
        run = self.get_object(request, object_id)
        if not request.user.is_superuser or run is None:
            self.message_user(request, _("Recovery is unavailable."), messages.ERROR)
        elif run.status != ImportStatus.FAILED:
            self.message_user(
                request,
                _("Only failed Catalog Imports can be recovered."),
                messages.ERROR,
            )
        else:
            try:
                recover_import_run(run, user=request.user)
            except Exception as exc:
                self.message_user(
                    request,
                    _("Catalog Import still failed: %(error)s") % {"error": exc},
                    messages.ERROR,
                )
            else:
                self.message_user(
                    request, _("Catalog Import recovered."), messages.SUCCESS
                )
        return redirect("admin:catalog_catalogimportrun_changelist")


@admin.register(CatalogImportEvent)
class CatalogImportEventAdmin(ReadOnlyAdmin):
    list_display = ("import_run", "source", "event", "outcome", "occurred_at")
    list_filter = ("source", "outcome")


@admin.register(CatalogSnapshot)
class CatalogSnapshotAdmin(ReadOnlyAdmin):
    list_display = ("id", "status", "entry_count", "is_active", "completed_at")
    actions = ["rollback_selected_snapshot"]
    actions_detail = ["rollback_snapshot"]

    @admin.display(boolean=True, description=_("Active"))
    def is_active(self, obj):
        return CatalogState.objects.filter(pk=1, active_snapshot=obj).exists()

    @admin.action(description=_("Activate selected snapshot as rollback"))
    def rollback_selected_snapshot(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request, _("Only Superusers may roll back."), messages.ERROR
            )
            return
        if queryset.count() != 1:
            self.message_user(
                request, _("Select exactly one snapshot."), messages.ERROR
            )
            return
        rollback_to_snapshot(queryset.get(), user=request.user)
        self.message_user(request, _("Song Catalog rolled back."), messages.SUCCESS)

    @action(description=_("Activate as rollback"), url_path="rollback")
    def rollback_snapshot(self, request, object_id: str):
        snapshot = self.get_object(request, object_id)
        if not request.user.is_superuser or snapshot is None:
            self.message_user(request, _("Rollback is unavailable."), messages.ERROR)
        else:
            rollback_to_snapshot(snapshot, user=request.user)
            self.message_user(request, _("Song Catalog rolled back."), messages.SUCCESS)
        return redirect(reverse("admin:catalog_catalogsnapshot_changelist"))


@admin.register(CatalogEntry)
class CatalogEntryAdmin(ReadOnlyAdmin):
    list_display = ("song_uid", "title", "rights_status", "content_changed_at")
    list_filter = ("rights_status",)
    search_fields = ("song_uid", "title")


class LyricsRightsChangeInline(admin.TabularInline):
    model = LyricsRightsChange
    extra = 0
    can_delete = False
    fields = (
        "previous_status",
        "new_status",
        "basis",
        "evidence_reference",
        "explanation",
        "decided_by",
        "decided_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CatalogSongRights)
class CatalogSongRightsAdmin(ModelAdmin):
    form = CatalogSongRightsAdminForm
    list_display = ("song_uid", "status", "basis", "decided_by", "decided_at")
    list_filter = ("status", "basis")
    search_fields = ("song_uid", "evidence_reference", "explanation")
    readonly_fields = ("song_uid", "decided_by", "decided_at")
    inlines = [LyricsRightsChangeInline]

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            raise PermissionError("Lyrics rights records are created by Catalog Imports.")
        change_lyrics_rights(
            obj,
            status=form.cleaned_data["status"],
            basis=form.cleaned_data["basis"],
            evidence_reference=form.cleaned_data["evidence_reference"],
            explanation=form.cleaned_data["explanation"],
            user=request.user,
        )


@admin.register(LyricsRightsChange)
class LyricsRightsChangeAdmin(ReadOnlyAdmin):
    list_display = (
        "rights",
        "previous_status",
        "new_status",
        "basis",
        "decided_by",
        "decided_at",
    )
    list_filter = ("previous_status", "new_status", "basis")
    search_fields = ("rights__song_uid", "evidence_reference", "explanation")


admin.site.register(CatalogState, ReadOnlyAdmin)
admin.site.register(CatalogActivation, ReadOnlyAdmin)
