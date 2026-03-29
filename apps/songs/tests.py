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
from apps.users.api_keys import issue_api_key
from apps.users.models import APIKeyScope


class SongIntakeTests(TestCase):
    def setUp(self):
        super().setUp()
        _, self.api_key = issue_api_key(
            name="Song intake test key",
            scopes=[APIKeyScope.SONGS_WRITE],
        )
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
            api_key=None,
        )
        self.assertIsInstance(response, JSON)
        self.assertEqual(response.status_code, 401)

    def test_creates_song(self):
        response = async_to_sync(intake_song_endpoint)(
            payload=self._payload(),
            api_key=self.api_key,
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
            api_key=self.api_key,
        )
        self.assertIsInstance(response, SongIntakeResponse)
        self.assertTrue(response.linked_to_schedule)
        self.assertEqual(response.schedule_date, "2026-03-22")
        self.assertEqual(response.preview_url, "/schedule/2026-03-22/preview/")
        self.assertEqual(SongAssignment.objects.count(), 1)
        self.assertEqual(SongAssignment.objects.get().position, 1)

    def test_creates_missing_schedule_and_default_worship_item_when_date_is_provided(self):
        response = async_to_sync(intake_song_endpoint)(
            payload=self._payload(
                schedule_date=dt.date(2026, 4, 5),
            ),
            api_key=self.api_key,
        )

        self.assertIsInstance(response, SongIntakeResponse)
        self.assertTrue(response.linked_to_schedule)
        self.assertEqual(response.schedule_date, "2026-04-05")
        self.assertEqual(response.preview_url, "/schedule/2026-04-05/preview/")

        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 4, 5))
        self.assertEqual(schedule.status, ServiceScheduleStatus.IN_PROGRESS)
        self.assertEqual(schedule.title, "Sunday Service - April 5, 2026")

        schedule_item = ScheduleItem.objects.get(schedule=schedule)
        self.assertEqual(schedule_item.item_type, "worship_song")
        self.assertEqual(schedule_item.title, "Praise & Worship")

        assignment = SongAssignment.objects.get(schedule_item=schedule_item)
        self.assertEqual(assignment.position, 1)

    def test_creates_missing_hymn_item_when_hymn_type_is_provided(self):
        response = async_to_sync(intake_song_endpoint)(
            payload=self._payload(
                schedule_date=dt.date(2026, 4, 12),
                item_type="hymn",
            ),
            api_key=self.api_key,
        )

        self.assertIsInstance(response, SongIntakeResponse)
        self.assertTrue(response.linked_to_schedule)

        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 4, 12))
        schedule_item = ScheduleItem.objects.get(schedule=schedule)
        self.assertEqual(schedule_item.item_type, "hymn")
        self.assertEqual(schedule_item.title, "Congregational Hymn")

    def test_uses_explicit_song_position_when_provided(self):
        schedule = ServiceSchedule.objects.create(
            date=dt.date(2026, 3, 29),
            title="Sunday Service",
            status=ServiceScheduleStatus.READY,
        )
        item = ScheduleItem.objects.create(
            schedule=schedule,
            position=2,
            item_type="worship_song",
            title="Praise & Worship",
        )

        response = async_to_sync(intake_song_endpoint)(
            payload=self._payload(
                schedule_date=dt.date(2026, 3, 29),
                item_type="worship_song",
                position=4,
                group_type="praise",
            ),
            api_key=self.api_key,
        )

        self.assertIsInstance(response, SongIntakeResponse)
        self.assertTrue(response.linked_to_schedule)
        assignment = SongAssignment.objects.get(schedule_item=item)
        self.assertEqual(assignment.position, 4)
