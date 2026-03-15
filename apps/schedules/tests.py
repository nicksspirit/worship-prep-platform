import datetime as dt
import shutil
import tempfile
from unittest.mock import patch

import msgspec
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django_bolt import JSON

from apps.schedules.api import intake_schedule_endpoint, patch_schedule_endpoint
from apps.schedules.choices import ServiceScheduleStatus
from apps.schedules.models import Contact, ContentSubmission, ScheduleItem, ServiceSchedule
from apps.schedules.schemas import IntakeResponse, ScheduleIntakePayload
from apps.schedules.services.intake import intake_schedule
from apps.schedules.services.preview import get_schedule_preview
from apps.schedules.views import build_empty_state, build_schedule_preview_page, format_service_date
from apps.songs.models import Song, SongAssignment

User = get_user_model()


@override_settings(N8N_INTAKE_API_KEY="test-intake-key")
class ScheduleIntakeTests(TestCase):
    def _payload(self, **overrides) -> ScheduleIntakePayload:
        payload = {
            "source": "whatsapp",
            "sender_name": "Min. Samuel Ojoh",
            "sender_phone": "+15035550000",
            "source_message_id": "wamid-12345",
            "raw_content": "Order of Service for 02/15/2026 ...",
            "title": "Sunday Service",
            "target_date": "2026-02-15",
            "items": [
                {
                    "position": 1,
                    "time_start": "10:30",
                    "time_end": "10:35",
                    "title": "Opening Prayer",
                    "leader_name": "Min. Samuel Ojoh",
                    "item_type": "opening_prayer",
                },
                {
                    "position": 2,
                    "time_start": "10:35",
                    "time_end": "11:05",
                    "title": "Praise & Worship",
                    "leader_name": "The VOGS",
                    "item_type": "worship_song",
                },
            ],
        }
        payload.update(overrides)
        return msgspec.convert(payload, type=ScheduleIntakePayload)

    def test_requires_api_key(self):
        response = async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(),
            n8n_api_key=None,
        )
        self.assertIsInstance(response, JSON)
        self.assertEqual(response.status_code, 401)

    def test_creates_schedule_and_submission(self):
        response = async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)
        self.assertEqual(response.created_or_updated, "created")
        self.assertEqual(response.items_created, 2)
        self.assertEqual(response.preview_url, "/schedule/2026-02-15/preview/")

        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 2, 15))
        self.assertEqual(ScheduleItem.objects.filter(schedule=schedule).count(), 2)
        self.assertEqual(ContentSubmission.objects.count(), 1)

    def test_duplicate_source_message_id_is_idempotent(self):
        request_payload = self._payload()
        async_to_sync(intake_schedule_endpoint)(
            payload=request_payload,
            n8n_api_key="test-intake-key",
        )
        response = async_to_sync(intake_schedule_endpoint)(
            payload=request_payload,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)
        self.assertEqual(response.created_or_updated, "existing")
        self.assertEqual(ContentSubmission.objects.count(), 1)
        self.assertEqual(ScheduleItem.objects.count(), 2)

    def test_duplicate_source_message_id_with_different_payload_returns_conflict(self):
        async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(source_message_id="wamid-conflict"),
            n8n_api_key="test-intake-key",
        )

        response = async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(
                source_message_id="wamid-conflict",
                title="Different Sunday Service",
            ),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, JSON)
        self.assertEqual(response.status_code, 409)

    def test_updates_existing_schedule_by_date(self):
        first = self._payload(source_message_id="wamid-first")
        async_to_sync(intake_schedule_endpoint)(
            payload=first,
            n8n_api_key="test-intake-key",
        )

        second = self._payload(
            source_message_id="wamid-second",
            title="Updated Sunday Service",
            items=[
                {
                    "position": 1,
                    "time_start": "10:31",
                    "time_end": "10:36",
                    "title": "Opening Prayer",
                    "leader_name": "Min. Samuel Ojoh",
                    "item_type": "opening_prayer",
                }
            ],
        )
        response = async_to_sync(intake_schedule_endpoint)(
            payload=second,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)
        self.assertEqual(response.created_or_updated, "updated")
        self.assertEqual(response.items_updated, 1)

        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 2, 15))
        self.assertEqual(schedule.title, "Updated Sunday Service")

    def test_updates_existing_schedule_item_by_type_when_position_changes(self):
        async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(source_message_id="wamid-initial-position"),
            n8n_api_key="test-intake-key",
        )

        response = async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(
                source_message_id="wamid-moved-position",
                items=[
                    {
                        "position": 3,
                        "time_start": "10:40",
                        "time_end": "10:45",
                        "title": "Opening Prayer",
                        "leader_name": "Min. Samuel Ojoh",
                        "item_type": "opening_prayer",
                    }
                ],
            ),
            n8n_api_key="test-intake-key",
        )

        self.assertIsInstance(response, IntakeResponse)
        self.assertEqual(response.created_or_updated, "updated")
        self.assertEqual(response.items_created, 0)
        self.assertEqual(response.items_updated, 1)

        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 2, 15))
        self.assertEqual(ScheduleItem.objects.filter(schedule=schedule).count(), 2)

        updated_item = ScheduleItem.objects.get(schedule=schedule, item_type="opening_prayer")
        self.assertEqual(updated_item.position, 3)
        self.assertEqual(updated_item.start_time, dt.time(10, 40))

    def test_rejects_payload_with_duplicate_schedule_item_types(self):
        response = async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(
                source_message_id="wamid-duplicate-types",
                items=[
                    {
                        "position": 1,
                        "title": "Opening Prayer",
                        "leader_name": "Min. Samuel Ojoh",
                        "item_type": "opening_prayer",
                    },
                    {
                        "position": 2,
                        "title": "Another Prayer",
                        "leader_name": "Min. Victor Umukoro",
                        "item_type": "opening_prayer",
                    },
                ],
            ),
            n8n_api_key="test-intake-key",
        )

        self.assertIsInstance(response, JSON)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ServiceSchedule.objects.count(), 0)
        self.assertEqual(ScheduleItem.objects.count(), 0)

    def test_partial_item_parsing_infers_type(self):
        payload = self._payload(
            items=[
                {
                    "title": "The Word",
                    "leader_name": "Min. Kenechi Adediji",
                }
            ],
            source_message_id="wamid-partial",
        )
        response = async_to_sync(intake_schedule_endpoint)(
            payload=payload,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)

        item = ScheduleItem.objects.get(position=1)
        self.assertEqual(item.item_type, "sermon")
        self.assertIsNone(item.start_time)

    def test_normalizes_known_aliases_and_preserves_honorifics(self):
        payload = self._payload(
            source_message_id="wamid-aliases",
            items=[
                {
                    "position": 1,
                    "title": "Praise & Worship",
                    "leader_name": "THE VOGS",
                },
                {
                    "position": 2,
                    "title": "Final Prayers",
                    "leader_name": "THE PASTOR",
                },
                {
                    "position": 3,
                    "title": "Opening Prayer",
                    "leader_name": "MIN. VICTOR UMUKORO",
                },
            ],
        )

        response = async_to_sync(intake_schedule_endpoint)(
            payload=payload,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)

        self.assertTrue(Contact.objects.filter(name="Voice of God Singers", role="choir").exists())
        self.assertTrue(
            Contact.objects.filter(name="Pastor Ronke Majekodunmi", role="pastor").exists()
        )
        self.assertTrue(Contact.objects.filter(name="Min. Victor Umukoro", role="minister").exists())

    def test_infers_new_schedule_item_types(self):
        payload = self._payload(
            source_message_id="wamid-item-types",
            items=[
                {
                    "position": 1,
                    "title": "Sunday School",
                    "leader_name": "Min. Tolu Daramola",
                },
                {
                    "position": 2,
                    "title": "Benediction",
                    "leader_name": "THE PASTOR",
                },
            ],
        )

        response = async_to_sync(intake_schedule_endpoint)(
            payload=payload,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)

        self.assertEqual(ScheduleItem.objects.get(position=1).item_type, "sunday_school")
        self.assertEqual(ScheduleItem.objects.get(position=2).item_type, "closing_prayer")

    def test_source_optional_defaults_to_unknown(self):
        payload = self._payload(source_message_id="wamid-source-optional")
        payload_dict = msgspec.to_builtins(payload)
        del payload_dict["source"]
        payload_no_source = msgspec.convert(payload_dict, type=ScheduleIntakePayload)

        response = async_to_sync(intake_schedule_endpoint)(
            payload=payload_no_source,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)
        submission = ContentSubmission.objects.get(source_message_id="wamid-source-optional")
        self.assertEqual(submission.source, "unknown")

    def test_uses_human_readable_default_schedule_title(self):
        payload = self._payload(
            source_message_id="wamid-default-title",
            title=None,
        )

        response = async_to_sync(intake_schedule_endpoint)(
            payload=payload,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)

        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 2, 15))
        self.assertEqual(schedule.title, "Sunday Service - February 15, 2026")

    def test_patch_requires_existing_schedule(self):
        response = async_to_sync(patch_schedule_endpoint)(
            payload=self._payload(source_message_id="wamid-patch-missing"),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, JSON)
        self.assertEqual(response.status_code, 404)

    def test_patch_can_reuse_raw_message_id_from_create_without_being_blocked(self):
        async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(source_message_id="wamid-shared"),
            n8n_api_key="test-intake-key",
        )

        response = async_to_sync(patch_schedule_endpoint)(
            payload=self._payload(
                source_message_id="wamid-shared",
                items=[
                    {
                        "position": 1,
                        "title": "Opening Prayer",
                        "leader_name": "MIN. VICTOR UMUKORO",
                    }
                ],
            ),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)
        self.assertEqual(response.created_or_updated, "updated")

        updated_item = ScheduleItem.objects.get(position=1)
        self.assertEqual(updated_item.assigned_contact.name, "Min. Victor Umukoro")
        self.assertEqual(ContentSubmission.objects.count(), 2)

    def test_patch_allows_repeated_updates_with_same_raw_message_id(self):
        async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(source_message_id="wamid-repeat-patch-create"),
            n8n_api_key="test-intake-key",
        )

        first_response = async_to_sync(patch_schedule_endpoint)(
            payload=self._payload(
                source_message_id="wamid-repeat-patch",
                items=[
                    {
                        "position": 1,
                        "title": "Opening Prayer",
                        "leader_name": "MIN. VICTOR UMUKORO",
                    }
                ],
            ),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(first_response, IntakeResponse)

        second_response = async_to_sync(patch_schedule_endpoint)(
            payload=self._payload(
                source_message_id="wamid-repeat-patch",
                items=[
                    {
                        "position": 1,
                        "title": "Opening Prayer",
                        "leader_name": "MIN. KENECHI ADEDIJI",
                    }
                ],
            ),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(second_response, IntakeResponse)
        self.assertEqual(second_response.created_or_updated, "updated")

        updated_item = ScheduleItem.objects.get(position=1)
        self.assertEqual(updated_item.assigned_contact.name, "Min. Kenechi Adediji")
        self.assertEqual(ContentSubmission.objects.count(), 3)

    def test_patch_updates_existing_schedule_without_creating_new_schedule(self):
        async_to_sync(intake_schedule_endpoint)(
            payload=self._payload(source_message_id="wamid-patch-base"),
            n8n_api_key="test-intake-key",
        )

        patch_payload = self._payload(
            source_message_id="wamid-patch-update",
            title="Sunday Service - February 15, 2026",
            items=[
                {
                    "position": 1,
                    "time_start": "10:31",
                    "time_end": "10:36",
                    "title": "Opening Prayer",
                    "leader_name": "MIN. VICTOR UMUKORO",
                },
                {
                    "position": 3,
                    "title": "Final Prayers",
                    "leader_name": "THE PASTOR",
                },
            ],
        )

        response = async_to_sync(patch_schedule_endpoint)(
            payload=patch_payload,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)
        self.assertEqual(response.created_or_updated, "updated")
        self.assertEqual(response.items_updated, 1)
        self.assertEqual(response.items_created, 1)

        self.assertEqual(ServiceSchedule.objects.count(), 1)
        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 2, 15))
        self.assertEqual(schedule.title, "Sunday Service - February 15, 2026")
        self.assertEqual(ScheduleItem.objects.filter(schedule=schedule).count(), 3)

        updated_item = ScheduleItem.objects.get(schedule=schedule, position=1)
        self.assertEqual(updated_item.start_time, dt.time(10, 31))
        self.assertEqual(updated_item.assigned_contact.name, "Min. Victor Umukoro")

        existing_item = ScheduleItem.objects.get(schedule=schedule, position=2)
        self.assertEqual(existing_item.title, "Praise & Worship")

        new_item = ScheduleItem.objects.get(schedule=schedule, position=3)
        self.assertEqual(new_item.item_type, "closing_prayer")
        self.assertEqual(new_item.assigned_contact.name, "Pastor Ronke Majekodunmi")

    def test_atomic_transaction_rolls_back_partial_writes_on_submission_failure(self):
        with patch(
            "apps.schedules.services.intake.ContentSubmission.objects.create",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                async_to_sync(intake_schedule)(
                    self._payload(source_message_id="wamid-atomic")
                )

        self.assertEqual(ServiceSchedule.objects.count(), 0)
        self.assertEqual(ScheduleItem.objects.count(), 0)
        self.assertEqual(ContentSubmission.objects.count(), 0)

    def test_schedule_items_must_be_unique_by_type_per_schedule(self):
        schedule = ServiceSchedule.objects.create(date=dt.date(2026, 2, 15), title="Sunday Service")
        ScheduleItem.objects.create(
            schedule=schedule,
            position=1,
            item_type="opening_prayer",
            title="Opening Prayer",
        )

        with self.assertRaises(ValidationError):
            ScheduleItem.objects.create(
                schedule=schedule,
                position=2,
                item_type="opening_prayer",
                title="Opening Prayer Again",
            )


class SchedulePreviewTests(TestCase):
    def test_returns_none_when_no_schedule(self):
        result = get_schedule_preview(dt.date(2099, 1, 1))
        self.assertIsNone(result)

    def test_returns_none_for_draft_schedule(self):
        ServiceSchedule.objects.create(
            date=dt.date(2026, 4, 5),
            title="Sunday Service",
            status=ServiceScheduleStatus.DRAFT,
        )
        result = get_schedule_preview(dt.date(2026, 4, 5))
        self.assertIsNone(result)

    def test_returns_preview_for_ready_schedule(self):
        schedule = ServiceSchedule.objects.create(
            date=dt.date(2026, 4, 12),
            title="Sunday Service",
            status=ServiceScheduleStatus.READY,
        )
        ScheduleItem.objects.create(
            schedule=schedule,
            position=1,
            item_type="opening_prayer",
            title="Opening Prayer",
        )
        result = get_schedule_preview(dt.date(2026, 4, 12))
        self.assertIsNotNone(result)
        self.assertEqual(result.date, "2026-04-12")
        self.assertEqual(result.title, "Sunday Service")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].title, "Opening Prayer")


class SchedulePageViewTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="planner@example.com",
            password="pass1234",
            first_name="Planner",
            last_name="User",
        )
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def sign_in(self):
        self.client.force_login(self.user)

    def test_home_page_redirects_authenticated_user_to_schedule_landing(self):
        self.sign_in()

        response = self.client.get(reverse("home_page"))

        self.assertRedirects(
            response,
            reverse("schedule_landing"),
            fetch_redirect_response=False,
        )

    def test_schedule_landing_redirects_to_nearest_upcoming_visible_schedule(self):
        self.sign_in()
        today = dt.date.today()
        ServiceSchedule.objects.create(
            date=today + dt.timedelta(days=14),
            title="Later Service",
            status=ServiceScheduleStatus.PUBLISHED,
        )
        upcoming = ServiceSchedule.objects.create(
            date=today + dt.timedelta(days=7),
            title="Nearest Service",
            status=ServiceScheduleStatus.READY,
        )

        response = self.client.get(reverse("schedule_landing"))

        self.assertRedirects(
            response,
            reverse("service_preview", kwargs={"date": upcoming.date.isoformat()}),
            fetch_redirect_response=False,
        )

    def test_build_schedule_preview_page_returns_structured_song_details(self):
        schedule = ServiceSchedule.objects.create(
            date=dt.date(2026, 4, 12),
            title="Sunday Service",
            status=ServiceScheduleStatus.READY,
        )
        item = ScheduleItem.objects.create(
            schedule=schedule,
            position=2,
            item_type="worship_song",
            title="Praise and Worship",
        )
        song = Song.objects.create(
            title="Amazing Grace",
            formatted_lyrics="[Verse 1]\nAmazing grace, how sweet the sound",
            slide_count=2,
        )
        SongAssignment.objects.create(schedule_item=item, song=song, position=0)

        page = build_schedule_preview_page(schedule.date)

        self.assertIsNotNone(page)
        self.assertEqual(page.title, "Sunday Service")
        self.assertEqual(page.items[0].title, "Praise and Worship")
        self.assertEqual(page.items[0].songs[0].title, "Amazing Grace")
        self.assertEqual(page.items[0].songs[0].filename, "Amazing_Grace.txt")

    def test_build_schedule_preview_page_returns_in_progress_schedule_for_direct_link(self):
        ServiceSchedule.objects.create(
            date=dt.date(2026, 4, 5),
            title="In Progress Schedule",
            status=ServiceScheduleStatus.IN_PROGRESS,
        )

        page = build_schedule_preview_page(dt.date(2026, 4, 5))

        self.assertIsNotNone(page)
        self.assertEqual(page.title, "In Progress Schedule")

    def test_build_empty_state_uses_human_friendly_date_label(self):
        date_label = format_service_date(dt.date(2026, 4, 5))

        empty_state = build_empty_state(date_label)

        self.assertEqual(empty_state.heading, "No schedule for Sunday, April 5, 2026 yet")
        self.assertEqual(empty_state.link_label, "Back to schedule list")
