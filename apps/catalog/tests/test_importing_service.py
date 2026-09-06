from datetime import datetime, timezone

from django.test import SimpleTestCase

from apps.catalog.services.importing import (
    ExistingCatalogSong,
    prepare_catalog_entries,
)


class PrepareCatalogEntriesTests(SimpleTestCase):
    def test_prepares_entry_with_carried_freshness_and_existing_rights(self):
        promoted_at = datetime(2026, 9, 6, tzinfo=timezone.utc)
        original_change = datetime(2026, 8, 1, tzinfo=timezone.utc)
        fingerprint = "sha256:semantic"
        record = {
            "source": {"song_uid": "song-1"},
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
