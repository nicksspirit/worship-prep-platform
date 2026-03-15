import re

from django.db import models
from django.core.files.base import ContentFile
from django_stubs_ext.db.models import TypedModelMeta

from apps.common.models import BaseModel


def sanitize_filename(title: str) -> str:
    """Sanitize a song title for use as a filename."""
    safe = re.sub(r'[^\w\s\-]', '', title)
    safe = re.sub(r'\s+', '_', safe.strip())
    return (safe or "untitled") + ".txt"


class Song(BaseModel):
    title = models.CharField(max_length=255)
    raw_lyrics = models.TextField(blank=True)
    formatted_lyrics = models.TextField(blank=True)
    lyrics_file = models.FileField(upload_to="songs/", blank=True)
    slide_count = models.PositiveIntegerField(null=True, blank=True)

    class Meta(TypedModelMeta):
        verbose_name = "Song"
        verbose_name_plural = "Songs"

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if self.formatted_lyrics:
            prev = None
            if self.pk:
                try:
                    prev = Song.objects.only("formatted_lyrics").get(pk=self.pk)
                except Song.DoesNotExist:
                    pass
            if prev is None or prev.formatted_lyrics != self.formatted_lyrics:
                filename = sanitize_filename(self.title)
                self.lyrics_file.save(
                    filename,
                    ContentFile(self.formatted_lyrics.encode("utf-8")),
                    save=False,
                )
        return super().save(*args, **kwargs)


class SongAssignment(BaseModel):
    schedule_item = models.ForeignKey(
        "schedules.ScheduleItem",
        on_delete=models.CASCADE,
        related_name="song_assignments",
    )
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    position = models.PositiveIntegerField(default=0)

    class Meta(TypedModelMeta):
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule_item", "song"], name="unique_song_per_item"
            ),
            models.UniqueConstraint(
                fields=["schedule_item", "position"], name="unique_song_position"
            ),
        ]
        verbose_name = "Song Assignment"
        verbose_name_plural = "Song Assignments"

    def __str__(self) -> str:
        return f"{self.schedule_item} ← {self.song}"
