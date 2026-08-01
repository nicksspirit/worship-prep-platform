import copy
import hashlib
import io
import json
import time
import uuid
import zipfile
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.test import TransactionTestCase
from django.utils import timezone
from django_bolt.serializers import Serializer
from django_bolt.testing import TestClient

from apps.api_keys.models import APIKeyScope
from apps.api_keys.services import check_rate_limit, issue_api_key, rotate_api_key
from apps.catalog.api import api as catalog_api
from apps.catalog.importer import import_package
from apps.catalog.models import CatalogEntry, CatalogState, RightsStatus
from apps.catalog.schema import (
    APIErrorResponse,
    CatalogImportResponse,
    CatalogSearchResponse,
    SongLyricsResponse,
    SongMetadataResponse,
)
from apps.catalog.search import CURSOR_MAX_AGE_SECONDS, search_catalog
from apps.catalog.text import SEARCH_CONFIG, normalize_title


class CatalogReadAPITests(TransactionTestCase):
    def setUp(self):
        self.search_key, self.search_secret = issue_api_key(
            name="Search",
            scopes=[APIKeyScope.CATALOG_SEARCH],
        )
        self.reader_key, self.reader_secret = issue_api_key(
            name="Reader",
            scopes=[
                APIKeyScope.CATALOG_SEARCH,
                APIKeyScope.SONG_READ,
                APIKeyScope.LYRICS_READ,
            ],
        )
        self.privileged_key, self.privileged_secret = issue_api_key(
            name="Privileged reader",
            scopes=[
                APIKeyScope.CATALOG_SEARCH,
                APIKeyScope.SONG_READ,
                APIKeyScope.LYRICS_READ,
                APIKeyScope.RESTRICTED_LYRICS_READ,
            ],
        )
        self.activate_catalog(self.song_records())
        CatalogEntry.objects.filter(song_uid="03-echo").update(
            rights_status=RightsStatus.RESTRICTED
        )
        self.client = TestClient(catalog_api, read_django_settings=False)

    def tearDown(self):
        self.client.close()

    @staticmethod
    def song_records():
        return [
            {
                "uid": "01-grace",
                "title": "Ámazing Grace",
                "author": "John Newton",
                "lyrics": "Amazing words\nLost and found",
                "label": "Verse",
            },
            {
                "uid": "02-mercy",
                "title": "Amazing Mercy",
                "author": None,
                "lyrics": "Mercy flows forever",
                "label": "Chorus",
            },
            {
                "uid": "03-echo",
                "title": "Echo",
                "author": "Choir",
                "lyrics": "Amazing words\nHidden refrain",
                "label": "Custom refrain",
            },
            {
                "uid": "04-same",
                "title": "Same Title",
                "author": None,
                "lyrics": "First duplicate",
                "label": "Verse",
            },
            {
                "uid": "05-same",
                "title": "Same Title",
                "author": None,
                "lyrics": "Second duplicate",
                "label": "Verse",
            },
        ]

    @staticmethod
    def build_package(records):
        fixture_dir = (
            Path(settings.BASE_DIR) / "contracts/catalog-import/v1/fixtures/valid"
        )
        manifest = json.loads((fixture_dir / "manifest.json").read_text())
        fixture_record = json.loads((fixture_dir / "songs.ndjson").read_text())
        package_records = []
        for position, item in enumerate(records, start=1):
            record = copy.deepcopy(fixture_record)
            record["source"].update(
                song_rowid=position,
                song_item_uid=f"item-{item['uid']}",
                song_uid=item["uid"],
                song_revision_uid=f"revision-{item['uid']}",
                slide_uids=[f"slide-{item['uid']}"],
            )
            record["metadata"].update(
                title=item["title"],
                author=item["author"],
            )
            record["cleaned_lyrics"] = item["lyrics"]
            record["sections"] = [
                {
                    "position": 1,
                    "label": item["label"],
                    "slides": [
                        {
                            "position": 1,
                            "source_slide_uid": f"slide-{item['uid']}",
                            "lines": item["lyrics"].splitlines(),
                        }
                    ],
                }
            ]
            fingerprint = hashlib.sha256(
                f"{item['uid']}:{item['title']}:{item['lyrics']}".encode()
            ).hexdigest()
            record["semantic_fingerprint"]["value"] = f"sha256:{fingerprint}"
            package_records.append(record)

        records_bytes = b"".join(
            json.dumps(record, separators=(",", ":")).encode() + b"\n"
            for record in package_records
        )
        digest = f"sha256:{hashlib.sha256(records_bytes).hexdigest()}"
        manifest["run_id"] = str(uuid.uuid4())
        manifest["counts"]["songs"] = len(package_records)
        manifest["records"].update(
            bytes=len(records_bytes),
            sha256=digest,
            fingerprint=digest,
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("songs.ndjson", records_bytes)
        return buffer.getvalue()

    def activate_catalog(self, records):
        return import_package(self.build_package(records)).run.snapshot

    @staticmethod
    def auth(secret):
        return {"Authorization": f"Bearer {secret}"}

    def test_openapi_documents_versioned_read_contract_and_bearer_security(self):
        schema = catalog_api._get_openapi_schema()

        self.assertEqual(schema["info"]["version"], "1.0.0")
        self.assertEqual(schema["security"], [{"BearerAuth": []}])
        self.assertEqual(
            schema["components"]["securitySchemes"]["BearerAuth"]["scheme"],
            "bearer",
        )
        self.assertIn("/api/v1/catalog/search", schema["paths"])
        self.assertIn("/api/v1/catalog/songs/{song_uid}", schema["paths"])
        self.assertIn("/api/v1/catalog/songs/{song_uid}/lyrics", schema["paths"])
        self.assertNotIn("/api/v1/catalog/preview", schema["paths"])
        self.assertIn("CatalogSearchResponse", schema["components"]["schemas"])
        self.assertIn("CatalogImportResponse", schema["components"]["schemas"])
        self.assertEqual(catalog_api._openapi_config.path, "/api/v1/docs")
        for contract in (
            APIErrorResponse,
            CatalogImportResponse,
            CatalogSearchResponse,
            SongMetadataResponse,
            SongLyricsResponse,
        ):
            self.assertTrue(issubclass(contract, Serializer))
        for method, path, handler_id, _handler in catalog_api._routes:
            with self.subTest(method=method, path=path):
                self.assertIsNotNone(
                    catalog_api._handler_meta[handler_id].get("response_type")
                )

        catalog_api._register_openapi_routes()
        with TestClient(catalog_api, read_django_settings=False) as docs_client:
            machine_schema = docs_client.get("/api/v1/docs/openapi.json")
            rendered_docs = docs_client.get("/api/v1/docs")
        self.assertEqual(machine_schema.status_code, 200)
        self.assertEqual(machine_schema.json()["info"]["version"], "1.0.0")
        self.assertEqual(rendered_docs.status_code, 200)
        self.assertIn("redoc", rendered_docs.text.lower())

    def test_title_and_lyrics_modes_stay_separate_and_accent_insensitive(self):
        title_response = self.client.get(
            "/api/v1/catalog/search",
            params={"q": "AMAZING", "mode": "title"},
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(title_response.status_code, 200)
        self.assertEqual(
            [item["song_uid"] for item in title_response.json()["results"]],
            ["01-grace", "02-mercy"],
        )
        self.assertNotIn("03-echo", str(title_response.json()))

        lyrics_response = self.client.get(
            "/api/v1/catalog/search",
            params={"q": "amazing words", "mode": "lyrics"},
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(lyrics_response.status_code, 200)
        self.assertEqual(
            [item["song_uid"] for item in lyrics_response.json()["results"]],
            ["01-grace"],
        )

        privileged_response = self.client.get(
            "/api/v1/catalog/search",
            params={"q": "amazing words", "mode": "lyrics"},
            headers=self.auth(self.privileged_secret),
        )
        self.assertEqual(
            [item["song_uid"] for item in privileged_response.json()["results"]],
            ["01-grace", "03-echo"],
        )

    def test_title_fallback_tolerates_a_typo_only_after_normal_search_misses(self):
        response = self.client.get(
            "/api/v1/catalog/search",
            params={"q": "Amazng Grce", "mode": "title"},
            headers=self.auth(self.reader_secret),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["song_uid"] for item in response.json()["results"]],
            ["01-grace"],
        )

    def test_keyset_continuation_is_deterministic_and_snapshot_pinned(self):
        first = self.client.get(
            "/api/v1/catalog/search",
            params={"limit": 2},
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(first.status_code, 200)
        first_body = first.json()
        self.assertEqual(
            [item["song_uid"] for item in first_body["results"]],
            ["01-grace", "02-mercy"],
        )
        self.assertTrue(first_body["has_more"])

        replacement = [
            {
                "uid": "00-new",
                "title": "Aardvark Song",
                "author": None,
                "lyrics": "Brand new",
                "label": "Verse",
            },
            *self.song_records(),
        ]
        self.activate_catalog(replacement)

        second = self.client.get(
            first_body["next"],
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(second.status_code, 200)
        second_uids = [item["song_uid"] for item in second.json()["results"]]
        self.assertEqual(second_uids, ["03-echo", "04-same"])
        self.assertNotIn("00-new", second_uids)

        third = self.client.get(
            second.json()["next"],
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(
            [item["song_uid"] for item in third.json()["results"]],
            ["05-same"],
        )

    def test_invalid_mismatched_expired_and_pruned_continuations_are_distinct(self):
        first = self.client.get(
            "/api/v1/catalog/search",
            params={"limit": 2},
            headers=self.auth(self.reader_secret),
        ).json()
        parsed = urlsplit(first["next"])
        parameters = parse_qs(parsed.query)
        token = parameters["next"][0]

        tampered = parameters.copy()
        tampered["next"] = [f"{token[:-1]}x"]
        tampered_url = urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(tampered, doseq=True),
                "",
            )
        )
        response = self.client.get(
            tampered_url,
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_cursor")

        mismatch = parameters.copy()
        mismatch["limit"] = ["3"]
        mismatch_url = urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urlencode(mismatch, doseq=True),
                "",
            )
        )
        response = self.client.get(
            mismatch_url,
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "cursor_query_mismatch")

        privileged_lyrics = self.client.get(
            "/api/v1/catalog/search",
            params={"q": "amazing words", "mode": "lyrics", "limit": 1},
            headers=self.auth(self.privileged_secret),
        ).json()
        response = self.client.get(
            privileged_lyrics["next"],
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "cursor_query_mismatch")

        with patch(
            "django.core.signing.time.time",
            return_value=time.time() + CURSOR_MAX_AGE_SECONDS + 1,
        ):
            response = self.client.get(
                first["next"],
                headers=self.auth(self.reader_secret),
            )
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["error"]["code"], "cursor_expired")
        self.assertIn("restart", response.json()["error"])

        old_snapshot = CatalogState.objects.get().active_snapshot
        self.activate_catalog(self.song_records())
        old_snapshot.delete()
        response = self.client.get(
            first["next"],
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()["error"]["code"], "cursor_expired")

    def test_metadata_never_leaks_lyrics_and_structured_lyrics_enforce_rights(self):
        metadata = self.client.get(
            "/api/v1/catalog/songs/03-echo",
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(metadata.status_code, 200)
        self.assertEqual(metadata.json()["lyrics_access"], "restricted")
        self.assertNotIn("lyrics", metadata.json())
        self.assertNotIn("sections", metadata.json())

        unknown_lyrics = self.client.get(
            "/api/v1/catalog/songs/01-grace/lyrics",
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(unknown_lyrics.status_code, 200)
        self.assertEqual(unknown_lyrics.json()["rights_status"], "unknown")

        denied = self.client.get(
            "/api/v1/catalog/songs/03-echo/lyrics",
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(
            denied.json()["error"]["code"],
            "restricted_lyrics_forbidden",
        )
        self.assertNotIn("Hidden refrain", denied.text)

        allowed = self.client.get(
            "/api/v1/catalog/songs/03-echo/lyrics",
            headers=self.auth(self.privileged_secret),
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(
            allowed.json()["sections"],
            [
                {
                    "position": 1,
                    "label": "Custom refrain",
                    "text": "Amazing words\nHidden refrain",
                }
            ],
        )

    def test_invalid_expired_revoked_and_under_scoped_keys_use_stable_errors(self):
        response = self.client.get("/api/v1/catalog/search")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "invalid_api_key")

        self.reader_key.expires_on = timezone.now()
        self.reader_key.save(update_fields=["expires_on", "updated_on"])
        response = self.client.get(
            "/api/v1/catalog/search",
            headers=self.auth(self.reader_secret),
        )
        self.assertEqual(response.status_code, 401)

        replacement, replacement_secret = rotate_api_key(self.privileged_key)
        response = self.client.get(
            "/api/v1/catalog/search",
            headers=self.auth(self.privileged_secret),
        )
        self.assertEqual(response.status_code, 401)
        response = self.client.get(
            "/api/v1/catalog/search",
            headers=self.auth(replacement_secret),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-RateLimit-Limit"], "60")
        replacement.refresh_from_db()
        self.assertIsNotNone(replacement.last_used_on)

        response = self.client.get(
            "/api/v1/catalog/search",
            params={"q": "words", "mode": "lyrics"},
            headers=self.auth(self.search_secret),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "insufficient_scope")

        response = self.client.get(
            "/api/v1/catalog/search",
            params={"q": "  ", "mode": "lyrics"},
            headers=self.auth(replacement_secret),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"],
            "lyrics_query_too_short",
        )

        response = self.client.get(
            "/api/v1/catalog/search",
            params={"q": "x" * 201},
            headers=self.auth(replacement_secret),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "query_too_long")

    def test_rate_limit_is_per_key_and_returns_retry_metadata(self):
        first = check_rate_limit(self.search_key, bucket="test", limit=2)
        second = check_rate_limit(self.search_key, bucket="test", limit=2)
        denied = check_rate_limit(self.search_key, bucket="test", limit=2)
        other_key = check_rate_limit(self.reader_key, bucket="test", limit=2)

        self.assertTrue(first.allowed)
        self.assertEqual(first.remaining, 1)
        self.assertTrue(second.allowed)
        self.assertEqual(second.remaining, 0)
        self.assertFalse(denied.allowed)
        self.assertEqual(denied.headers["X-RateLimit-Remaining"], "0")
        self.assertIn("Retry-After", denied.headers)
        self.assertTrue(other_key.allowed)

        with patch("apps.catalog.api.SEARCH_RATE_LIMIT", 1):
            allowed_response = self.client.get(
                "/api/v1/catalog/search",
                headers=self.auth(self.search_secret),
            )
            denied_response = self.client.get(
                "/api/v1/catalog/search",
                headers=self.auth(self.search_secret),
            )
        self.assertEqual(allowed_response.status_code, 200)
        self.assertEqual(denied_response.status_code, 429)
        self.assertEqual(
            denied_response.json()["error"]["code"],
            "rate_limited",
        )
        self.assertEqual(denied_response.headers["X-RateLimit-Remaining"], "0")
        self.assertIn("Retry-After", denied_response.headers)

    def test_postgres_search_and_continuation_meet_synthetic_catalog_targets(self):
        snapshot = CatalogState.objects.get().active_snapshot
        now = timezone.now()
        fingerprint = "sha256:" + "1" * 64
        entries = [
            CatalogEntry(
                snapshot=snapshot,
                song_uid=f"perf-{index:04d}",
                title=f"Song {index:04d}",
                normalized_title=normalize_title(f"Song {index:04d}"),
                authors=[],
                cleaned_lyrics="grace truth mercy",
                sections=[],
                slide_count=1,
                fingerprint_version="song-semantic/v1",
                semantic_fingerprint=fingerprint,
                metadata_fingerprint=fingerprint,
                lyrics_fingerprint=fingerprint,
                structure_fingerprint=fingerprint,
                presentation_fingerprint=fingerprint,
                content_changed_at=now,
            )
            for index in range(2283)
        ]
        CatalogEntry.objects.bulk_create(entries, batch_size=500)
        CatalogEntry.objects.filter(
            snapshot=snapshot, song_uid__startswith="perf-"
        ).update(
            title_search=SearchVector("title", config=SEARCH_CONFIG),
            lyrics_search=SearchVector("cleaned_lyrics", config=SEARCH_CONFIG),
        )

        first_page = search_catalog(query="Song", mode="title", limit=100)
        continuation = parse_qs(urlsplit(first_page.next_url).query)["next"][0]

        def percentile_95(operation):
            durations = []
            for _ in range(20):
                started_at = perf_counter()
                operation()
                durations.append(perf_counter() - started_at)
            return sorted(durations)[18]

        title_p95 = percentile_95(
            lambda: search_catalog(query="Song", mode="title", limit=20)
        )
        lyrics_p95 = percentile_95(
            lambda: search_catalog(query="grace truth", mode="lyrics", limit=20)
        )
        continuation_p95 = percentile_95(
            lambda: search_catalog(
                query="Song",
                mode="title",
                limit=100,
                continuation=continuation,
            )
        )

        self.assertLessEqual(title_p95, 0.250)
        self.assertLessEqual(lyrics_p95, 0.500)
        self.assertLessEqual(continuation_p95, 0.300)
