from datetime import datetime, timedelta
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_bolt.testing import TestClient
from structlog.testing import capture_logs

from apps.api_keys.models import APIKeyScope
from apps.api_keys.services import IssueApiKey, issue_api_key
from apps.schedule_previews.api import api
from apps.schedule_previews.models import SchedulePreview

PUBLISH_URL = "/api/v1/schedule-previews"
APP_ORIGIN = "https://app.example.test"


@override_settings(SCHEDULE_PREVIEW_APP_ORIGIN=APP_ORIGIN, SCHEDULE_PREVIEW_TTL_HOURS=5)
class SchedulePreviewTests(TransactionTestCase):
    def setUp(self):
        key = issue_api_key(
            IssueApiKey("Tech booth", [APIKeyScope.SCHEDULE_PREVIEW_PUBLISH])
        )
        self.authorization = {"Authorization": f"Bearer {key.plaintext_key}"}
        self.publisher_key_id = key.api_key.pk
        self.payload = {
            "title": "Sunday Worship",
            "sections": {
                "call_to_worship": [
                    {
                        "title": "Opening Song",
                        "slides": [
                            {
                                "section_label": "Chorus",
                                "lines": ["First line", "Second line"],
                            },
                            {"lines": ["Third line"]},
                        ],
                    },
                ],
                "praise": [
                    {"title": "Praise Song", "slides": [{"lines": ["Praise line"]}]}
                ],
                "worship": [{"title": "Closing Song", "slides": [{"lines": []}]}],
            },
        }
        self.api_client = TestClient(api, read_django_settings=False)
        self.addCleanup(self.api_client.close)

    def publish(self):
        return self.api_client.post(
            PUBLISH_URL, json=self.payload, headers=self.authorization
        )

    def test_publishes_slides_in_order_for_an_anonymous_viewer(self):
        before = timezone.now()

        published = self.publish()

        self.assertEqual(published.status_code, 201, published.text)
        self.assertEqual(published.headers["Cache-Control"], "no-store")
        result = published.json()
        self.assertTrue(
            result["preview_url"].startswith(f"{APP_ORIGIN}/schedule-previews/")
        )
        expires = datetime.fromisoformat(result["expires_at"])
        self.assertGreaterEqual(expires, before + timedelta(hours=5))
        self.assertLessEqual(expires, timezone.now() + timedelta(hours=5))
        path = urlsplit(result["preview_url"]).path
        with capture_logs() as logs:
            page = self.client.get(path)
        self.assertContains(page, "First line")
        self.assertContains(page, "3. Closing Song")
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(page["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(page["Referrer-Policy"], "no-referrer")
        self.assertIn("/schedule-previews/<redacted>/", [log.get("path") for log in logs])
        self.assertNotIn(path, [log.get("path") for log in logs])
        props = page.context_data.get_serialized()
        self.assertEqual(
            props["created_date"],
            timezone.localdate(expires - timedelta(hours=5)).isoformat(),
        )
        self.assertContains(page, "Created")
        self.assertEqual(
            [section["title"] for section in props["sections"]],
            ["Call to Worship", "Praise", "Worship"],
        )
        self.assertEqual(
            props["sections"][0]["songs"][0]["slides"],
            [
                {
                    "position": 1,
                    "section_label": "Chorus",
                    "lines": ["First line", "Second line"],
                },
                {"position": 2, "section_label": "", "lines": ["Third line"]},
            ],
        )
        self.assertEqual(props["sections"][2]["songs"][0]["slides"][0]["lines"], [])

    def test_special_song_section_appears_after_worship_when_supplied(self):
        self.payload["sections"]["special_song"] = [
            {"title": "Guest Song", "slides": [{"lines": ["Guest line"]}]}
        ]

        published = self.publish()

        self.assertEqual(published.status_code, 201, published.text)
        page = self.client.get(urlsplit(published.json()["preview_url"]).path)
        props = page.context_data.get_serialized()
        self.assertEqual(props["sections"][-1]["title"], "Special Song")
        self.assertContains(page, "4. Guest Song")

    def test_rejects_a_missing_required_section(self):
        del self.payload["sections"]["praise"]

        published = self.publish()

        self.assertEqual(published.status_code, 422, published.text)
        self.assertFalse(SchedulePreview.objects.exists())

    def test_rejects_more_than_thirty_songs_across_sections(self):
        self.payload["sections"]["praise"] *= 29

        published = self.publish()

        self.assertEqual(published.status_code, 422, published.text)
        self.assertFalse(SchedulePreview.objects.exists())

    def test_previously_published_ungrouped_link_still_renders(self):
        saved = SchedulePreview.objects.create(
            content={
                "title": "Earlier Service",
                "songs": [
                    {
                        "title": "Opening Song",
                        "slides": [{"section_label": "", "lines": ["First line"]}],
                    }
                ],
            },
            expires_at=timezone.now() + timedelta(hours=1),
        )

        page = self.client.get(reverse("schedule_preview", args=[saved.pk]))

        self.assertContains(page, "First line")
        self.assertNotContains(page, "Call to Worship")

    def test_republishing_keeps_the_earlier_snapshot(self):
        first = self.publish().json()["preview_url"]
        self.payload["sections"]["call_to_worship"][0]["slides"][0]["lines"] = [
            "Corrected line"
        ]

        second = self.publish().json()["preview_url"]

        self.assertNotEqual(first, second)
        earlier_page = self.client.get(urlsplit(first).path)
        self.assertContains(earlier_page, "First line")
        self.assertNotContains(earlier_page, "Corrected line")

    def test_admin_detail_shows_publish_audit_without_the_bearer_key(self):
        staff = get_user_model().objects.create_user(
            "audit-staff@example.test", "test-only-password", is_staff=True
        )
        self.client.force_login(staff)
        self.authorization["X-Request-ID"] = "test-publish-request"
        published = self.publish()
        self.assertEqual(published.status_code, 201, published.text)
        preview = SchedulePreview.objects.get()

        page = self.client.get(
            reverse("admin:schedule_previews_schedulepreview_change", args=[preview.pk])
        )

        self.assertEqual(preview.submitted_payload, self.payload)
        self.assertEqual(preview.publisher_key_id, self.publisher_key_id)
        self.assertContains(page, f"POST {PUBLISH_URL}")
        self.assertContains(page, "test-publish-request")
        self.assertContains(page, "API key ID")
        self.assertContains(page, "call_to_worship")
        self.assertNotContains(page, self.authorization["Authorization"].split()[1])

    def test_expired_link_never_renders_lyrics(self):
        published = self.publish().json()["preview_url"]
        SchedulePreview.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

        page = self.client.get(urlsplit(published).path)

        self.assertContains(page, "This preview is unavailable", status_code=404)
        self.assertNotContains(page, "First line", status_code=404)

    def test_publish_prunes_expired_snapshots(self):
        expired = SchedulePreview.objects.create(
            content=self.payload, expires_at=timezone.now() - timedelta(seconds=1)
        )

        published = self.publish()

        self.assertEqual(published.status_code, 201)
        self.assertFalse(SchedulePreview.objects.filter(pk=expired.pk).exists())

    def test_publish_requires_a_key(self):
        published = self.api_client.post(PUBLISH_URL, json=self.payload)

        self.assertEqual(published.status_code, 401, published.text)
        self.assertFalse(SchedulePreview.objects.exists())

    def test_catalog_scope_does_not_grant_publish_access(self):
        key = issue_api_key(IssueApiKey("Catalog", [APIKeyScope.LYRICS_READ]))

        published = self.api_client.post(
            PUBLISH_URL,
            json=self.payload,
            headers={"Authorization": f"Bearer {key.plaintext_key}"},
        )

        self.assertEqual(published.status_code, 403, published.text)
        self.assertFalse(SchedulePreview.objects.exists())

    def test_rejects_client_expiry_overrides(self):
        self.payload["expires_in_hours"] = 100

        published = self.publish()

        self.assertEqual(published.status_code, 422, published.text)
        self.assertFalse(SchedulePreview.objects.exists())

    def test_rejects_embedded_line_breaks(self):
        self.payload["sections"]["call_to_worship"][0]["slides"][0]["lines"] = [
            "One\nTwo"
        ]

        published = self.publish()

        self.assertEqual(published.status_code, 422, published.text)
        self.assertFalse(SchedulePreview.objects.exists())

    def test_lyrics_cannot_inject_script_into_the_preview(self):
        lyric = "</script><script>alert('unexpected')</script>"
        self.payload["sections"]["call_to_worship"][0]["slides"][0]["lines"] = [lyric]
        published = self.publish().json()["preview_url"]

        page = self.client.get(urlsplit(published).path)

        self.assertContains(page, "&lt;/script&gt;&lt;script&gt;")
        self.assertNotContains(page, lyric)
