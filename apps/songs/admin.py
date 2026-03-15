from django.contrib import admin
from unfold.admin import TabularInline, ModelAdmin

from apps.songs.models import Song, SongAssignment


class SongAssignmentInline(TabularInline):
    model = SongAssignment
    extra = 0
    autocomplete_fields = ["schedule_item"]
    ordering = ["position"]


@admin.register(Song)
class SongAdmin(ModelAdmin):
    list_display = ["title", "slide_count", "updated_on"]
    inlines = [SongAssignmentInline]
    list_filter = ["updated_on"]
    search_fields = ["title", "raw_lyrics", "formatted_lyrics"]
    ordering = ["title"]
    readonly_fields = ["lyrics_file", "updated_on", "deleted_on"]
    fieldsets = (
        (
            None,
            {
                "fields": ["title", "raw_lyrics", "formatted_lyrics", "lyrics_file", "slide_count"],
            },
        ),
        (
            "Metadata",
            {
                "classes": ["collapse"],
                "fields": ["updated_on", "deleted_on"],
            },
        ),
    )


@admin.register(SongAssignment)
class SongAssignmentAdmin(ModelAdmin):
    list_display = ["schedule_item", "song", "position"]
    list_filter = ["schedule_item__schedule__date"]
    search_fields = ["song__title", "schedule_item__title"]
    autocomplete_fields = ["schedule_item", "song"]
    ordering = ["schedule_item", "position"]
