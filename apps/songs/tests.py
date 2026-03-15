import datetime as dt
import shutil
import tempfile

import msgspec
from asgiref.sync import async_to_sync
from django.test import TestCase, override_settings
from django_bolt import JSON

from apps.schedules.choices import ServiceScheduleStatus
from apps.schedules.models import ScheduleItem, ServiceSchedule
from apps.songs.api import intake_song_endpoint
from apps.songs.models import Song, SongAssignment
from apps.songs.schemas import SongIntakePayload, SongIntakeResponse


@override_settings(N8N_INTAKE_API_KEY="test-intake-key")
class SongIntakeTests(TestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def _payload(self, **overrides) -> SongIntakePayload:
        payload = {
            "song_title": "Amazing Grace",
            "raw_lyrics": "Amazing grace...",
            "formatted_lyrics": "[Verse 1]\nAmazing grace...",
            "filename": "Amazing_Grace.txt",
            "slide_count": 3,
        }
        payload.update(overrides)
        return msgspec.convert(payload, type=SongIntakePayload)

    def test_requires_api_key(self):
        response = async_to_sync(intake_song_endpoint)(
            payload=self._payload(),
            n8n_api_key=None,
        )
        self.assertIsInstance(response, JSON)
        self.assertEqual(response.status_code, 401)

    def test_creates_song(self):
        response = async_to_sync(intake_song_endpoint)(
            payload=self._payload(),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, SongIntakeResponse)
        self.assertFalse(response.is_existing)
        self.assertEqual(response.song_title, "Amazing Grace")
        self.assertIsNone(response.preview_url)
        self.assertEqual(Song.objects.count(), 1)

    def test_links_to_schedule_item_when_date_and_type_provided(self):
        schedule = ServiceSchedule.objects.create(
            date=dt.date(2026, 3, 22),
            title="Sunday Service",
            status=ServiceScheduleStatus.READY,
        )
        ScheduleItem.objects.create(
            schedule=schedule,
            position=2,
            item_type="worship_song",
            title="Praise & Worship",
        )

        response = async_to_sync(intake_song_endpoint)(
            payload=self._payload(
                schedule_date=dt.date(2026, 3, 22),
                item_type="worship_song",
            ),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, SongIntakeResponse)
        self.assertTrue(response.linked_to_schedule)
        self.assertEqual(response.schedule_date, "2026-03-22")
        self.assertEqual(response.preview_url, "/schedule/2026-03-22/preview/")
        self.assertEqual(SongAssignment.objects.count(), 1)
