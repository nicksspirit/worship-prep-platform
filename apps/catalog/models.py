import uuid

from django.conf import settings
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.catalog.storage import catalog_import_storage


class ImportStatus(models.TextChoices):
    RECEIVED = "received", _("Received")
    VALIDATING = "validating", _("Validating")
    STAGING = "staging", _("Staging")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")


class CatalogImportRun(models.Model):
    """Durable audit record for one exporter-generated run identity."""

    id = models.UUIDField(primary_key=True, editable=False)
    exporter_instance_id = models.UUIDField()
    contract_version = models.CharField(max_length=64)
    exporter_version = models.CharField(max_length=128)
    parser_version = models.CharField(max_length=128)
    source_fingerprint = models.CharField(max_length=71)
    package_sha256 = models.CharField(max_length=71)
    records_fingerprint = models.CharField(max_length=71)
    package_file = models.FileField(
        storage=catalog_import_storage, upload_to="packages/%Y/%m/%d"
    )
    report_file = models.FileField(
        storage=catalog_import_storage,
        upload_to="reports/%Y/%m/%d",
        blank=True,
    )
    status = models.CharField(
        max_length=16, choices=ImportStatus, default=ImportStatus.RECEIVED
    )
    song_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    warnings = models.JSONField(default=list, blank=True)
    failure_code = models.CharField(max_length=64, blank=True)
    failure_summary = models.TextField(blank=True)
    exporter_created_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    previous_import = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="next_imports",
    )

    class Meta:
        ordering = ["-received_at"]


class CatalogImportEvent(models.Model):
    """Append-only timeline event emitted by either side of an import run."""

    class Source(models.TextChoices):
        EXPORTER = "exporter", _("Exporter")
        IMPORTER = "importer", _("Importer")

    import_run = models.ForeignKey(
        CatalogImportRun, on_delete=models.CASCADE, related_name="events"
    )
    source = models.CharField(max_length=16, choices=Source)
    event = models.CharField(max_length=64)
    outcome = models.CharField(max_length=32)
    occurred_at = models.DateTimeField()
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["occurred_at", "pk"]


class SnapshotStatus(models.TextChoices):
    CANDIDATE = "candidate", _("Candidate")
    COMPLETED = "completed", _("Completed")


class CatalogSnapshot(models.Model):
    """Immutable materialized catalog produced by one successful import."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    import_run = models.OneToOneField(
        CatalogImportRun, on_delete=models.PROTECT, related_name="snapshot"
    )
    status = models.CharField(
        max_length=16, choices=SnapshotStatus, default=SnapshotStatus.CANDIDATE
    )
    staged_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    entry_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-completed_at"]


class RightsStatus(models.TextChoices):
    APPROVED = "approved", _("Approved")
    UNKNOWN = "unknown", _("Unknown")
    RESTRICTED = "restricted", _("Restricted")


class CatalogEntry(models.Model):
    """Searchable, non-evidentiary projection of one song in a snapshot."""

    snapshot = models.ForeignKey(
        CatalogSnapshot, on_delete=models.CASCADE, related_name="entries"
    )
    song_uid = models.CharField(max_length=255)
    title = models.CharField(max_length=512)
    authors = models.JSONField(default=list, blank=True)
    copyright_notice = models.TextField(blank=True)
    cleaned_lyrics = models.TextField(blank=True)
    sections = models.JSONField(default=list)
    slide_count = models.PositiveIntegerField(default=0)
    rights_status = models.CharField(
        max_length=16, choices=RightsStatus, default=RightsStatus.UNKNOWN
    )
    fingerprint_version = models.CharField(max_length=64)
    semantic_fingerprint = models.CharField(max_length=71)
    metadata_fingerprint = models.CharField(max_length=71)
    lyrics_fingerprint = models.CharField(max_length=71)
    structure_fingerprint = models.CharField(max_length=71)
    presentation_fingerprint = models.CharField(max_length=71)
    content_changed_at = models.DateTimeField()
    title_search = SearchVectorField(null=True)
    lyrics_search = SearchVectorField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "song_uid"], name="catalog_unique_song_per_snapshot"
            )
        ]
        indexes = [models.Index(fields=["song_uid"])]
        ordering = ["title", "song_uid"]


class CatalogState(models.Model):
    """Singleton pointer to the active immutable snapshot."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    active_snapshot = models.ForeignKey(
        CatalogSnapshot, null=True, blank=True, on_delete=models.PROTECT
    )
    updated_at = models.DateTimeField(auto_now=True)


class CatalogActivation(models.Model):
    """Append-only history of import promotions and rollback pointer changes."""

    class Reason(models.TextChoices):
        IMPORT = "import", _("Import")
        ROLLBACK = "rollback", _("Rollback")

    snapshot_reference = models.UUIDField(editable=False)
    previous_snapshot_reference = models.UUIDField(null=True, editable=False)
    snapshot = models.ForeignKey(
        CatalogSnapshot, null=True, blank=True, on_delete=models.SET_NULL
    )
    previous_snapshot = models.ForeignKey(
        CatalogSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="superseding_activations",
    )
    reason = models.CharField(max_length=16, choices=Reason)
    activated_at = models.DateTimeField()
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["-activated_at", "-pk"]
