from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TypedDict, cast
from uuid import UUID

from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from jsonschema import Draft202012Validator, FormatChecker

from apps.catalog.models import (
    CatalogActivation,
    CatalogEntry,
    CatalogImportEvent,
    CatalogImportRun,
    CatalogSnapshot,
    CatalogSongRights,
    CatalogState,
    ImportStatus,
    ImportTrigger,
    SnapshotStatus,
)
from apps.catalog.services.importing import (
    CatalogSongRecord,
    ExistingCatalogSong,
    prepare_catalog_entries,
)
from apps.catalog.text import SEARCH_CONFIG

MAX_PACKAGE_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_RECORDS_BYTES = 120 * 1024 * 1024
MAX_EXPORTER_EVENTS_BYTES = 1024 * 1024
RETAIN_PRIOR_SNAPSHOTS = 7
ARCHIVE_FILES = {"manifest.json", "songs.ndjson"}
EXPORTER_EVENT_DETAIL_KEYS = {
    "error",
    "exporter_version",
    "package_sha256",
    "scheduled",
    "songs",
    "warnings",
}


class ImportRejected(ValueError):
    """A package violates the importer contract and cannot be staged."""

    def __init__(self, code: str, summary: str):
        super().__init__(summary)
        self.code = code
        self.summary = summary


@dataclass(frozen=True, slots=True)
class ImportResult:
    run: CatalogImportRun
    created: bool


class ManifestSource(TypedDict):
    fingerprint: str


class ManifestRecords(TypedDict):
    bytes: int
    sha256: str
    fingerprint: str


class ManifestCounts(TypedDict):
    songs: int
    warnings: int


class ImportManifest(TypedDict):
    run_id: str
    exporter_instance_id: str
    contract_version: str
    exporter_version: str
    parser_version: str
    source: ManifestSource
    records: ManifestRecords
    counts: ManifestCounts
    warnings: list[object]
    created_at: str


@dataclass(frozen=True, slots=True)
class InspectedPackage:
    """Archive contents that passed package-shape and manifest validation."""

    manifest: ImportManifest
    records_bytes: bytes


@dataclass(frozen=True, slots=True)
class ValidatedPackage:
    """An inspected package whose song records are safe to prepare."""

    manifest: ImportManifest
    records: tuple[CatalogSongRecord, ...]


def _sha256(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _load_json(content: bytes, *, label: str) -> object:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ImportRejected(
                    "duplicate_json_key", f"{label} repeats key {key!r}."
                )
            result[key] = value
        return result

    try:
        return json.loads(content, object_pairs_hook=reject_duplicates)
    except ImportRejected:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportRejected("invalid_json", f"{label} is not valid UTF-8 JSON.") from exc


@cache
def _validator(name: str) -> Draft202012Validator:
    schema_path = (
        Path(settings.BASE_DIR) / "contracts" / "catalog-import" / "v1" / name
    )
    schema = json.loads(schema_path.read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate_schema(value, *, name: str, label: str) -> None:
    errors = sorted(
        _validator(name).iter_errors(value), key=lambda error: list(error.path)
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "root"
        raise ImportRejected(
            "schema_validation_failed",
            f"{label} violates {name} at {location}: {errors[0].message}",
        )


def _read_archive(package: bytes) -> InspectedPackage:
    if not package or len(package) > MAX_PACKAGE_BYTES:
        raise ImportRejected(
            "invalid_package_size", "Package is empty or exceeds 128 MiB."
        )
    try:
        archive = zipfile.ZipFile(io.BytesIO(package))
    except zipfile.BadZipFile as exc:
        raise ImportRejected(
            "invalid_zip", "Package is not a valid ZIP archive."
        ) from exc
    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or set(names) != ARCHIVE_FILES:
            raise ImportRejected(
                "invalid_archive_members",
                "Package must contain exactly manifest.json and songs.ndjson.",
            )
        if any(
            info.is_dir()
            or info.flag_bits & 0x1
            or (info.external_attr >> 16) & 0o170000 == 0o120000
            for info in infos
        ):
            raise ImportRejected(
                "unsafe_archive",
                "Directories, links, and encrypted members are forbidden.",
            )
        manifest_info = archive.getinfo("manifest.json")
        records_info = archive.getinfo("songs.ndjson")
        if (
            manifest_info.file_size > MAX_MANIFEST_BYTES
            or records_info.file_size > MAX_RECORDS_BYTES
        ):
            raise ImportRejected(
                "expanded_package_too_large", "Expanded package exceeds limits."
            )
        manifest_bytes = archive.read(manifest_info)
        records_bytes = archive.read(records_info)
    manifest = _load_json(manifest_bytes, label="manifest.json")
    _validate_schema(manifest, name="manifest.schema.json", label="manifest.json")
    return InspectedPackage(cast(ImportManifest, manifest), records_bytes)


def _validate_records(
    manifest: ImportManifest, records_bytes: bytes
) -> ValidatedPackage:
    expected = manifest["records"]
    if expected["bytes"] != len(records_bytes) or expected["sha256"] != _sha256(
        records_bytes
    ):
        raise ImportRejected(
            "records_integrity_failed", "songs.ndjson size or checksum differs."
        )
    if expected["fingerprint"] != expected["sha256"]:
        raise ImportRejected(
            "records_fingerprint_mismatch",
            "V1 records fingerprint must equal its checksum.",
        )

    records = []
    song_uids = set()
    song_item_uids = set()
    for line_number, line in enumerate(records_bytes.splitlines(), start=1):
        if not line.strip():
            raise ImportRejected(
                "blank_record", f"songs.ndjson line {line_number} is blank."
            )
        record = _load_json(line, label=f"songs.ndjson line {line_number}")
        _validate_schema(
            record, name="song.schema.json", label=f"song line {line_number}"
        )
        source = record["source"]
        if (
            source["song_uid"] in song_uids
            or source["song_item_uid"] in song_item_uids
        ):
            raise ImportRejected(
                "duplicate_song_identity",
                f"Duplicate song identity at line {line_number}.",
            )
        song_uids.add(source["song_uid"])
        song_item_uids.add(source["song_item_uid"])
        records.append(cast(CatalogSongRecord, record))
    if len(records) != manifest["counts"]["songs"]:
        raise ImportRejected(
            "song_count_mismatch", "Manifest song count differs from records."
        )
    if len(manifest["warnings"]) != manifest["counts"]["warnings"]:
        raise ImportRejected(
            "warning_count_mismatch", "Manifest warning count differs from warnings."
        )
    return ValidatedPackage(manifest=manifest, records=tuple(records))


def _read_exporter_events(content: bytes, *, run_id: UUID) -> list[dict]:
    if not content:
        return []
    if len(content) > MAX_EXPORTER_EVENTS_BYTES:
        raise ImportRejected(
            "exporter_events_too_large", "Exporter events exceed 1 MiB."
        )

    events = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        event = _load_json(line, label=f"exporter events line {line_number}")
        if not isinstance(event, dict) or str(event.get("run_id")) != str(run_id):
            raise ImportRejected(
                "invalid_exporter_event",
                f"Exporter event {line_number} does not belong to this run.",
            )
        occurred_at = parse_datetime(str(event.get("occurred_at", "")))
        details = event.get("details", {})
        if (
            not occurred_at
            or not isinstance(event.get("type"), str)
            or not event["type"]
            or len(event["type"]) > 64
            or not isinstance(details, dict)
            or not set(details).issubset(EXPORTER_EVENT_DETAIL_KEYS)
        ):
            raise ImportRejected(
                "invalid_exporter_event",
                f"Exporter event {line_number} is malformed.",
            )
        events.append(
            {
                "event": event["type"],
                "outcome": str(
                    event.get("outcome")
                    or (
                        "failed"
                        if event["type"] in {"failed", "run_identity_conflict"}
                        else "skipped"
                        if event["type"].startswith("skipped_")
                        else "completed"
                    )
                )[:32],
                "occurred_at": occurred_at,
                "details": details,
            }
        )
    return events


def _event(run, event: str, outcome: str, *, details=None, occurred_at=None):
    return CatalogImportEvent.objects.create(
        import_run=run,
        source=CatalogImportEvent.Source.IMPORTER,
        event=event,
        outcome=outcome,
        occurred_at=occurred_at or timezone.now(),
        details=details or {},
    )


def _store_exporter_events(run: CatalogImportRun, events: list[dict]) -> None:
    for event in events:
        CatalogImportEvent.objects.get_or_create(
            import_run=run,
            source=CatalogImportEvent.Source.EXPORTER,
            event=event["event"],
            outcome=event["outcome"],
            occurred_at=event["occurred_at"],
            defaults={"details": event["details"]},
        )


def _write_report(run: CatalogImportRun) -> None:
    report = {
        "run_id": str(run.pk),
        "status": run.status,
        "song_count": run.song_count,
        "warnings": run.warnings,
        "failure": (
            {"code": run.failure_code, "summary": run.failure_summary}
            if run.failure_code
            else None
        ),
    }
    run.report_file.save(
        f"{run.pk}.json",
        ContentFile(json.dumps(report, sort_keys=True).encode()),
        save=False,
    )
    run.save(update_fields=["report_file"])


def _try_write_report(run: CatalogImportRun) -> None:
    """Persist diagnostics without changing the already-decided import outcome."""

    try:
        _write_report(run)
    except Exception:  # Storage failure must not turn a completed import into a retry.
        _event(run, "report_storage", "failed")


def _stage_and_promote(
    run: CatalogImportRun, records: tuple[CatalogSongRecord, ...]
) -> None:
    promoted_at = timezone.now()
    with transaction.atomic():
        state, _ = CatalogState.objects.select_for_update().get_or_create(pk=1)
        previous = state.active_snapshot
        previous_entries: dict[str, ExistingCatalogSong] = {}
        if previous:
            previous_entries = {
                entry.song_uid: ExistingCatalogSong(
                    semantic_fingerprint=entry.semantic_fingerprint,
                    content_changed_at=entry.content_changed_at,
                )
                for entry in previous.entries.only(
                    "song_uid", "semantic_fingerprint", "content_changed_at"
                )
            }
        song_uids = [record["source"]["song_uid"] for record in records]
        rights_by_uid = {
            rights.song_uid: rights.status
            for rights in CatalogSongRights.objects.filter(song_uid__in=song_uids)
        }
        CatalogSongRights.objects.bulk_create(
            [
                CatalogSongRights(song_uid=song_uid)
                for song_uid in song_uids
                if song_uid not in rights_by_uid
            ],
            ignore_conflicts=True,
        )
        rights_by_uid.update(
            CatalogSongRights.objects.filter(song_uid__in=song_uids).values_list(
                "song_uid", "status"
            )
        )
        snapshot = CatalogSnapshot.objects.create(
            import_run=run, staged_at=promoted_at, entry_count=len(records)
        )
        prepared_entries = prepare_catalog_entries(
            records,
            previous_songs=previous_entries,
            rights_by_song_uid=rights_by_uid,
            promoted_at=promoted_at,
        )
        entries = [
            CatalogEntry(
                snapshot=snapshot,
                song_uid=entry.song_uid,
                title=entry.title,
                normalized_title=entry.normalized_title,
                authors=list(entry.authors),
                copyright_notice=entry.copyright_notice,
                cleaned_lyrics=entry.cleaned_lyrics,
                sections=entry.sections,
                slide_count=entry.slide_count,
                rights_status=entry.rights_status,
                fingerprint_version=entry.fingerprint_version,
                semantic_fingerprint=entry.semantic_fingerprint,
                metadata_fingerprint=entry.metadata_fingerprint,
                lyrics_fingerprint=entry.lyrics_fingerprint,
                structure_fingerprint=entry.structure_fingerprint,
                presentation_fingerprint=entry.presentation_fingerprint,
                content_changed_at=entry.content_changed_at,
            )
            for entry in prepared_entries
        ]
        CatalogEntry.objects.bulk_create(entries, batch_size=500)
        snapshot.entries.update(
            title_search=SearchVector("title", config=SEARCH_CONFIG),
            lyrics_search=SearchVector("cleaned_lyrics", config=SEARCH_CONFIG),
        )
        _event(
            run,
            "staging",
            "completed",
            details={"snapshot_id": str(snapshot.pk)},
        )
        snapshot.status = SnapshotStatus.COMPLETED
        snapshot.completed_at = promoted_at
        snapshot.save(update_fields=["status", "completed_at"])
        state.active_snapshot = snapshot
        state.save(update_fields=["active_snapshot", "updated_at"])
        CatalogActivation.objects.create(
            snapshot=snapshot,
            snapshot_reference=snapshot.pk,
            previous_snapshot=previous,
            previous_snapshot_reference=previous.pk if previous else None,
            reason=CatalogActivation.Reason.IMPORT,
            activated_at=promoted_at,
        )
        run.status = ImportStatus.COMPLETED
        run.completed_at = promoted_at
        run.song_count = len(records)
        run.save(update_fields=["status", "completed_at", "song_count"])
        _event(run, "promotion", "completed", details={"snapshot_id": str(snapshot.pk)})

        retained = list(
            CatalogSnapshot.objects.filter(status=SnapshotStatus.COMPLETED)
            .exclude(pk=snapshot.pk)
            .order_by("-completed_at")
            .values_list("pk", flat=True)[:RETAIN_PRIOR_SNAPSHOTS]
        )
        CatalogSnapshot.objects.filter(status=SnapshotStatus.COMPLETED).exclude(
            pk__in=[snapshot.pk, *retained]
        ).delete()


def _mark_run_failed(run: CatalogImportRun, *, code: str, summary: str) -> None:
    """Record the terminal failure state shared by validation and staging failures."""

    run.status = ImportStatus.FAILED
    run.failure_code = code
    run.failure_summary = summary
    run.completed_at = timezone.now()
    run.save(
        update_fields=["status", "failure_code", "failure_summary", "completed_at"]
    )
    _event(run, "import", "failed", details={"code": code})


def _finish_failed_run(
    run: CatalogImportRun, *, code: str, summary: str, notify_scheduled_failure: bool
) -> None:
    """Persist a terminal failure and its diagnostics without masking its cause."""

    _mark_run_failed(run, code=code, summary=summary)
    _try_write_report(run)
    if notify_scheduled_failure and run.trigger == ImportTrigger.SCHEDULED:
        from apps.catalog.operations import notify_scheduled_import_failure

        notify_scheduled_import_failure(run)


def _process_run(
    run: CatalogImportRun,
    inspected: InspectedPackage,
    *,
    notify_scheduled_failure: bool = True,
) -> None:
    try:
        run.status = ImportStatus.VALIDATING
        run.failure_code = ""
        run.failure_summary = ""
        run.completed_at = None
        run.save(
            update_fields=[
                "status",
                "failure_code",
                "failure_summary",
                "completed_at",
            ]
        )
        validated = _validate_records(inspected.manifest, inspected.records_bytes)
        _event(
            run,
            "validation",
            "completed",
            details={"song_count": len(validated.records)},
        )
        run.status = ImportStatus.STAGING
        run.save(update_fields=["status"])
        _event(run, "staging", "started")
        _stage_and_promote(run, validated.records)
    except ImportRejected as exc:
        _finish_failed_run(
            run,
            code=exc.code,
            summary=exc.summary,
            notify_scheduled_failure=notify_scheduled_failure,
        )
        raise
    except Exception:
        _finish_failed_run(
            run,
            code="staging_failed",
            summary="The candidate snapshot could not be staged or promoted.",
            notify_scheduled_failure=notify_scheduled_failure,
        )
        raise


def import_package(
    package: bytes,
    *,
    exporter_events: bytes = b"",
    trigger: str = ImportTrigger.MANUAL,
) -> ImportResult:
    """Validate, privately retain, stage, and atomically promote one package."""

    inspected = _read_archive(package)
    manifest = inspected.manifest
    run_id = UUID(manifest["run_id"])
    if trigger not in ImportTrigger.values:
        raise ImportRejected("invalid_import_trigger", "Import trigger is invalid.")
    events = _read_exporter_events(exporter_events, run_id=run_id)
    package_sha = _sha256(package)
    existing = CatalogImportRun.objects.filter(pk=run_id).first()
    if existing:
        if existing.package_sha256 != package_sha:
            raise ImportRejected(
                "run_id_conflict", "Run ID already belongs to another package."
            )
        _store_exporter_events(existing, events)
        if existing.status == ImportStatus.FAILED and trigger == ImportTrigger.SCHEDULED:
            _event(existing, "retry", "requested")
            _process_run(existing, inspected)
            _try_write_report(existing)
        return ImportResult(existing, created=False)

    previous = CatalogImportRun.objects.filter(status=ImportStatus.COMPLETED).first()
    created_at = parse_datetime(manifest["created_at"])
    assert created_at is not None
    run = CatalogImportRun(
        id=run_id,
        exporter_instance_id=UUID(manifest["exporter_instance_id"]),
        contract_version=manifest["contract_version"],
        exporter_version=manifest["exporter_version"],
        parser_version=manifest["parser_version"],
        source_fingerprint=manifest["source"]["fingerprint"],
        package_sha256=package_sha,
        records_fingerprint=manifest["records"]["fingerprint"],
        exporter_created_at=created_at,
        warning_count=manifest["counts"]["warnings"],
        warnings=manifest["warnings"],
        previous_import=previous,
        trigger=trigger,
    )
    run.package_file.save(f"{run_id}.zip", ContentFile(package), save=False)
    run.save()
    _store_exporter_events(run, events)
    CatalogImportEvent.objects.create(
        import_run=run,
        source=CatalogImportEvent.Source.EXPORTER,
        event="package_created",
        outcome="completed",
        occurred_at=created_at,
        details={"exporter_version": run.exporter_version},
    )
    _event(run, "package_received", "completed")
    _process_run(run, inspected)
    _try_write_report(run)
    return ImportResult(run, created=True)


def recover_import_run(run: CatalogImportRun, *, user) -> CatalogImportRun:
    """Reprocess one privately retained failed package under its original identity."""

    if not user or not user.is_superuser:
        raise PermissionError("Only Superusers may recover a Catalog Import Run.")
    run = CatalogImportRun.objects.get(pk=run.pk)
    if run.status != ImportStatus.FAILED:
        raise ValueError("Only failed Catalog Import Runs can be recovered.")
    with run.package_file.open("rb") as package_file:
        package = package_file.read()
    if _sha256(package) != run.package_sha256:
        raise ImportRejected(
            "stored_package_integrity_failed",
            "The retained package no longer matches its recorded checksum.",
        )
    inspected = _read_archive(package)
    manifest = inspected.manifest
    if UUID(manifest["run_id"]) != run.pk:
        raise ImportRejected(
            "stored_package_identity_failed",
            "The retained package no longer matches its Catalog Import Run.",
        )
    _event(run, "recovery", "requested", details={"user_id": user.pk})
    _process_run(
        run,
        inspected,
        notify_scheduled_failure=False,
    )
    _try_write_report(run)
    return run


@transaction.atomic
def rollback_to_snapshot(snapshot: CatalogSnapshot, *, user=None) -> CatalogActivation:
    """Atomically repoint the active catalog to a retained completed snapshot."""

    if snapshot.status != SnapshotStatus.COMPLETED:
        raise ValueError("Only completed snapshots can be activated.")
    state, _ = CatalogState.objects.select_for_update().get_or_create(pk=1)
    previous = state.active_snapshot
    state.active_snapshot = snapshot
    state.save(update_fields=["active_snapshot", "updated_at"])
    return CatalogActivation.objects.create(
        snapshot=snapshot,
        snapshot_reference=snapshot.pk,
        previous_snapshot=previous,
        previous_snapshot_reference=previous.pk if previous else None,
        reason=CatalogActivation.Reason.ROLLBACK,
        activated_at=timezone.now(),
        activated_by=user,
    )
