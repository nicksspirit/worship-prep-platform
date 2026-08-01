from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
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
    CatalogState,
    ImportStatus,
    RightsStatus,
    SnapshotStatus,
)

MAX_PACKAGE_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_RECORDS_BYTES = 120 * 1024 * 1024
RETAIN_PRIOR_SNAPSHOTS = 7
ARCHIVE_FILES = {"manifest.json", "songs.ndjson"}


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


def _sha256(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _load_json(content: bytes, *, label: str):
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


def _read_archive(package: bytes) -> tuple[dict, bytes]:
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
    return manifest, records_bytes


def _validate_records(manifest: dict, records_bytes: bytes) -> list[dict]:
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
        records.append(record)
    if len(records) != manifest["counts"]["songs"]:
        raise ImportRejected(
            "song_count_mismatch", "Manifest song count differs from records."
        )
    if len(manifest["warnings"]) != manifest["counts"]["warnings"]:
        raise ImportRejected(
            "warning_count_mismatch", "Manifest warning count differs from warnings."
        )
    return records


def _event(run, event: str, outcome: str, *, details=None, occurred_at=None):
    return CatalogImportEvent.objects.create(
        import_run=run,
        source=CatalogImportEvent.Source.IMPORTER,
        event=event,
        outcome=outcome,
        occurred_at=occurred_at or timezone.now(),
        details=details or {},
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


def _stage_and_promote(run: CatalogImportRun, records: list[dict]) -> None:
    promoted_at = timezone.now()
    with transaction.atomic():
        state, _ = CatalogState.objects.select_for_update().get_or_create(pk=1)
        previous = state.active_snapshot
        previous_entries = {}
        if previous:
            previous_entries = {
                entry.song_uid: entry
                for entry in previous.entries.only(
                    "song_uid", "semantic_fingerprint", "content_changed_at"
                )
            }
        snapshot = CatalogSnapshot.objects.create(
            import_run=run, staged_at=promoted_at, entry_count=len(records)
        )
        entries = []
        for record in records:
            source = record["source"]
            metadata = record["metadata"]
            fingerprint = record["semantic_fingerprint"]
            components = fingerprint["components"]
            prior = previous_entries.get(source["song_uid"])
            changed_at = (
                prior.content_changed_at
                if prior and prior.semantic_fingerprint == fingerprint["value"]
                else promoted_at
            )
            entries.append(
                CatalogEntry(
                    snapshot=snapshot,
                    song_uid=source["song_uid"],
                    title=metadata["title"],
                    authors=[metadata["author"]] if metadata["author"] else [],
                    copyright_notice=metadata["copyright"] or "",
                    cleaned_lyrics=record["cleaned_lyrics"],
                    sections=record["sections"],
                    slide_count=sum(
                        len(section["slides"]) for section in record["sections"]
                    ),
                    rights_status=RightsStatus.UNKNOWN,
                    fingerprint_version=fingerprint["version"],
                    semantic_fingerprint=fingerprint["value"],
                    metadata_fingerprint=components["metadata"],
                    lyrics_fingerprint=components["lyrics"],
                    structure_fingerprint=components["structure"],
                    presentation_fingerprint=components["presentation"],
                    content_changed_at=changed_at,
                )
            )
        CatalogEntry.objects.bulk_create(entries, batch_size=500)
        snapshot.entries.update(
            title_search=SearchVector("title", config="simple"),
            lyrics_search=SearchVector("cleaned_lyrics", config="simple"),
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


def import_package(package: bytes) -> ImportResult:
    """Validate, privately retain, stage, and atomically promote one package."""

    manifest, records_bytes = _read_archive(package)
    run_id = UUID(manifest["run_id"])
    package_sha = _sha256(package)
    existing = CatalogImportRun.objects.filter(pk=run_id).first()
    if existing:
        if existing.package_sha256 != package_sha:
            raise ImportRejected(
                "run_id_conflict", "Run ID already belongs to another package."
            )
        return ImportResult(existing, created=False)

    previous = CatalogImportRun.objects.filter(status=ImportStatus.COMPLETED).first()
    created_at = parse_datetime(manifest["created_at"])
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
    )
    run.package_file.save(f"{run_id}.zip", ContentFile(package), save=False)
    run.save()
    CatalogImportEvent.objects.create(
        import_run=run,
        source=CatalogImportEvent.Source.EXPORTER,
        event="package_created",
        outcome="completed",
        occurred_at=created_at,
        details={"exporter_version": run.exporter_version},
    )
    _event(run, "package_received", "completed")
    try:
        run.status = ImportStatus.VALIDATING
        run.save(update_fields=["status"])
        records = _validate_records(manifest, records_bytes)
        _event(run, "validation", "completed", details={"song_count": len(records)})
        run.status = ImportStatus.STAGING
        run.save(update_fields=["status"])
        _stage_and_promote(run, records)
    except ImportRejected as exc:
        run.status = ImportStatus.FAILED
        run.failure_code = exc.code
        run.failure_summary = exc.summary
        run.completed_at = timezone.now()
        run.save(
            update_fields=["status", "failure_code", "failure_summary", "completed_at"]
        )
        _event(run, "import", "failed", details={"code": exc.code})
        _try_write_report(run)
        raise
    except Exception:
        run.status = ImportStatus.FAILED
        run.failure_code = "staging_failed"
        run.failure_summary = "The candidate snapshot could not be staged or promoted."
        run.completed_at = timezone.now()
        run.save(
            update_fields=["status", "failure_code", "failure_summary", "completed_at"]
        )
        _event(run, "import", "failed", details={"code": run.failure_code})
        _try_write_report(run)
        raise
    _try_write_report(run)
    return ImportResult(run, created=True)


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
