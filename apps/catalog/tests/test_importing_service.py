import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.catalog.importer import (
    InspectedPackage,
    ValidatedPackage,
    _read_archive,
    _validate_records,
)
from apps.catalog.services.importing import (
    ExistingCatalogSong,
    prepare_catalog_entries,
)


class PrepareCatalogEntriesTests(SimpleTestCase):
    def test_validation_transitions_to_typed_package_phases(self):
        fixture_dir = (
            Path(settings.BASE_DIR) / "contracts/catalog-import/v1/fixtures/valid"
        )
        manifest = (fixture_dir / "manifest.json").read_bytes()
        records = (fixture_dir / "songs.ndjson").read_bytes()
        package_buffer = io.BytesIO()
        with zipfile.ZipFile(package_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", manifest)
            archive.writestr("songs.ndjson", records)

        inspected = _read_archive(package_buffer.getvalue())
        validated = _validate_records(inspected.manifest, inspected.records_bytes)

        self.assertIsInstance(inspected, InspectedPackage)
        self.assertIsInstance(validated, ValidatedPackage)
        self.assertEqual(validated.manifest, inspected.manifest)
        self.assertIsInstance(validated.records, tuple)
        self.assertEqual(
            validated.records[0]["source"]["song_uid"], "fixture-song-uid"
        )

    def test_prepares_entry_with_carried_freshness_and_existing_rights(self):
        promoted_at = datetime(2026, 9, 6, tzinfo=timezone.utc)
        original_change = datetime(2026, 8, 1, tzinfo=timezone.utc)
        fingerprint = "sha256:semantic"
        record = {
            "source": {"song_uid": "song-1", "song_item_uid": "item-1"},
            "metadata": {
                "title": "  Ámazing Grace  ",
                "author": "John Newton",
                "copyright": None,
            },
            "cleaned_lyrics": "Amazing grace",
            "sections": [
                {
                    "position": 1,
                    "label": "verse",
                    "slides": [{"position": 1, "lines": ["Amazing grace"]}],
                }
            ],
            "semantic_fingerprint": {
                "version": "song-semantic/v1",
                "value": fingerprint,
                "components": {
                    "metadata": "sha256:metadata",
                    "lyrics": "sha256:lyrics",
                    "structure": "sha256:structure",
                    "presentation": "sha256:presentation",
                },
            },
        }

        entries = prepare_catalog_entries(
            [record],
            previous_songs={
                "song-1": ExistingCatalogSong(fingerprint, original_change)
            },
            rights_by_song_uid={"song-1": "approved"},
            promoted_at=promoted_at,
        )

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry.song_uid, "song-1")
        self.assertEqual(entry.normalized_title, "amazing grace")
        self.assertEqual(entry.authors, ("John Newton",))
        self.assertEqual(entry.slide_count, 1)
        self.assertEqual(entry.rights_status, "approved")
        self.assertEqual(entry.content_changed_at, original_change)
