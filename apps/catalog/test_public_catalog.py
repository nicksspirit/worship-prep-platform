import uuid
from datetime import timedelta
from html.parser import HTMLParser

from django.contrib.postgres.search import SearchVector
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import (
    CatalogEntry,
    CatalogImportRun,
    CatalogSnapshot,
    CatalogState,
    ImportStatus,
    RightsStatus,
    SnapshotStatus,
)
from apps.catalog.text import SEARCH_CONFIG, normalize_title

FINGERPRINT = f"sha256:{'a' * 64}"


class NextLinkParser(HTMLParser):
    """Extract the public continuation without coupling tests to page markup."""

    def __init__(self):
        super().__init__()
        self.href = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and values.get("data-purpose") == "catalog-next":
            self.href = values.get("href")


class PublicCatalogTests(TestCase):
    def setUp(self):
        self.snapshot = self.activate_catalog(
            [
                {
                    "uid": "amazing-grace",
                    "title": "Amazing Grace",
                    "authors": ["John Newton"],
                    "lyrics": "Amazing grace\nHow sweet the sound\nThat saved a soul",
                    "rights": RightsStatus.UNKNOWN,
                    "sections": [
                        {
                            "position": 1,
                            "label": "verse",
                            "slides": [
                                {
                                    "position": 1,
                                    "lines": ["Amazing grace", "How sweet the sound"],
                                },
                                {
                                    "position": 2,
                                    "lines": ["That saved a soul"],
                                },
                            ],
                        },
                        {
                            "position": 2,
                            "label": "verse",
                            "slides": [
                                {
                                    "position": 1,
                                    "lines": ["I once was lost", "But now am found"],
                                }
                            ],
                        },
                        {
                            "position": 3,
                            "label": "Refrain (soft)",
                            "slides": [
                                {
                                    "position": 1,
                                    "lines": ["Sing it softly"],
                                }
                            ],
                        },
                    ],
                },
                {
                    "uid": "amazing-mercy",
                    "title": "Amazing Mercy",
                    "authors": [],
                    "lyrics": "Mercy in the morning",
                    "rights": RightsStatus.APPROVED,
                },
                {
                    "uid": "hidden-song",
                    "title": "Amazing Hidden Song",
                    "authors": ["Choir"],
                    "lyrics": "SECRET REFRAIN MUST NEVER LEAK",
                    "rights": RightsStatus.RESTRICTED,
                },
            ]
        )

    @staticmethod
    def activate_catalog(records, *, completed_at=None):
        completed_at = completed_at or timezone.now()
        run = CatalogImportRun.objects.create(
            id=uuid.uuid4(),
            exporter_instance_id=uuid.uuid4(),
            contract_version="catalog-import/v1",
            exporter_version="test",
            parser_version="test",
            source_fingerprint=FINGERPRINT,
            package_sha256=FINGERPRINT,
            records_fingerprint=FINGERPRINT,
            package_file="packages/test.zip",
            report_file="reports/test.json",
            status=ImportStatus.COMPLETED,
            song_count=len(records),
            exporter_created_at=completed_at,
            completed_at=completed_at,
        )
        snapshot = CatalogSnapshot.objects.create(
            import_run=run,
            status=SnapshotStatus.COMPLETED,
            staged_at=completed_at,
            completed_at=completed_at,
            entry_count=len(records),
        )
        for position, record in enumerate(records, start=1):
            sections = record.get("sections") or [
                {
                    "position": 1,
                    "label": "verse",
                    "slides": [
                        {
                            "position": 1,
                            "lines": record["lyrics"].splitlines(),
                        }
                    ],
                }
            ]
            CatalogEntry.objects.create(
                snapshot=snapshot,
                song_uid=record["uid"],
                title=record["title"],
                normalized_title=normalize_title(record["title"]),
                authors=record.get("authors", []),
                copyright_notice=record.get("copyright", ""),
                cleaned_lyrics=record["lyrics"],
                sections=sections,
                slide_count=sum(len(section["slides"]) for section in sections),
                rights_status=record.get("rights", RightsStatus.UNKNOWN),
                fingerprint_version="song-semantic/v1",
                semantic_fingerprint=FINGERPRINT,
                metadata_fingerprint=FINGERPRINT,
                lyrics_fingerprint=FINGERPRINT,
                structure_fingerprint=FINGERPRINT,
                presentation_fingerprint=FINGERPRINT,
                content_changed_at=record.get("changed_at", completed_at),
            )
        snapshot.entries.update(
            title_search=SearchVector("title", config=SEARCH_CONFIG),
            lyrics_search=SearchVector("cleaned_lyrics", config=SEARCH_CONFIG),
        )
        CatalogState.objects.update_or_create(
            pk=1,
            defaults={"active_snapshot": snapshot},
        )
        return snapshot

    def test_empty_catalog_search_shows_freshness_and_hints_not_every_song(self):
        response = self.client.get(reverse("catalog:search"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Catalog refreshed")
        self.assertContains(response, "Start with what you remember")
        self.assertNotContains(response, "Amazing Grace")

    def test_public_search_retains_modes_author_fallback_and_rights_omission(self):
        title_response = self.client.get(
            reverse("catalog:search"),
            {"q": "Amazing", "mode": "title"},
        )

        self.assertEqual(title_response.status_code, 200)
        self.assertContains(title_response, "Amazing Grace")
        self.assertContains(title_response, "Amazing Mercy")
        self.assertContains(title_response, "Amazing Hidden Song")
        self.assertContains(title_response, "N/A")
        self.assertContains(title_response, "Lyric preview")
        self.assertContains(title_response, "Lyrics unavailable for public display")
        self.assertNotContains(title_response, "SECRET REFRAIN MUST NEVER LEAK")

        lyrics_response = self.client.get(
            reverse("catalog:search"),
            {"q": "Mercy", "mode": "lyrics"},
        )
        self.assertContains(lyrics_response, "Amazing Mercy")
        self.assertNotContains(lyrics_response, "Amazing Grace")
        self.assertNotContains(lyrics_response, "Amazing Hidden Song")

        isolated_response = self.client.get(
            reverse("catalog:search"),
            {"q": "morning", "mode": "title"},
        )
        self.assertContains(isolated_response, "No songs found")
        self.assertNotContains(isolated_response, "Amazing Mercy")

    def test_public_search_validates_length_and_keeps_no_result_query(self):
        too_long = "a" * 129
        response = self.client.get(
            reverse("catalog:search"),
            {"q": too_long, "mode": "title"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "at most 128 characters", status_code=400)

        response = self.client.get(
            reverse("catalog:search"),
            {"q": "not in the catalog", "mode": "title"},
        )
        self.assertContains(response, "No songs found")
        self.assertContains(response, "not in the catalog")

    def test_public_continuation_stays_pinned_and_expiry_offers_restart(self):
        old_snapshot = self.activate_catalog(
            [
                {
                    "uid": f"song-{index:02d}",
                    "title": f"Song {index:02d}",
                    "lyrics": f"Line {index}",
                }
                for index in range(21)
            ],
            completed_at=timezone.now() - timedelta(days=1),
        )
        first_page = self.client.get(
            reverse("catalog:search"),
            {"q": "Song", "mode": "title"},
        )
        parser = NextLinkParser()
        parser.feed(first_page.content.decode())
        self.assertIsNotNone(parser.href)

        self.activate_catalog(
            [{"uid": "song-new", "title": "Song New", "lyrics": "New line"}]
        )
        second_page = self.client.get(parser.href)
        self.assertContains(second_page, "Song 20")
        self.assertNotContains(second_page, "Song New")

        old_snapshot.delete()
        expired_page = self.client.get(parser.href)
        self.assertEqual(expired_page.status_code, 410)
        self.assertContains(expired_page, "Restart this search", status_code=410)

    def test_song_detail_preserves_sections_and_has_accessible_projection(self):
        response = self.client.get(
            reverse("catalog:detail", kwargs={"song_uid": "amazing-grace"})
        )
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Song freshness")
        self.assertContains(response, "Catalog freshness")
        self.assertContains(response, "Projection Preview")
        self.assertContains(response, 'class="projection-stage"')
        self.assertContains(response, 'aria-live="polite"')
        self.assertContains(response, "Show next projection slide")
        self.assertContains(response, 'aria-current="step"')
        self.assertLess(content.index("Amazing grace"), content.index("I once was lost"))
        self.assertLess(content.index("I once was lost"), content.index("Sing it softly"))
        self.assertGreaterEqual(content.count(">Verse<"), 2)
        self.assertContains(response, "Refrain (soft)")

    def test_restricted_song_detail_is_metadata_only_and_has_no_preview(self):
        response = self.client.get(
            reverse("catalog:detail", kwargs={"song_uid": "hidden-song"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Metadata-only entry")
        self.assertNotContains(response, "SECRET REFRAIN MUST NEVER LEAK")
        self.assertNotContains(response, "Projection Preview")
        self.assertNotContains(response, "projection-stage")

    def test_unknown_song_returns_not_found(self):
        response = self.client.get(
            reverse("catalog:detail", kwargs={"song_uid": "missing"})
        )

        self.assertEqual(response.status_code, 404)
