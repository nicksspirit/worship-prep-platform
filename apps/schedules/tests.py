import datetime as dt
from unittest.mock import patch

import msgspec
from asgiref.sync import async_to_sync
from django.test import TestCase, override_settings
from django_bolt import JSON

from apps.schedules.api import intake_schedule_from_whatsapp, patch_schedule_from_whatsapp
from apps.schedules.models import Contact, ContentSubmission, ScheduleItem, ServiceSchedule
from apps.schedules.schemas import IntakeResponse, WhatsAppScheduleIntakePayload
from apps.schedules.services.intake import intake_whatsapp_schedule


@override_settings(N8N_INTAKE_API_KEY="test-intake-key")
class WhatsAppScheduleIntakeTests(TestCase):
    def _payload(self, **overrides) -> WhatsAppScheduleIntakePayload:
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
        return msgspec.convert(payload, type=WhatsAppScheduleIntakePayload)

    def test_requires_api_key(self):
        response = async_to_sync(intake_schedule_from_whatsapp)(
            payload=self._payload(),
            n8n_api_key=None,
        )
        self.assertIsInstance(response, JSON)
        self.assertEqual(response.status_code, 401)

    def test_creates_schedule_and_submission(self):
        response = async_to_sync(intake_schedule_from_whatsapp)(
            payload=self._payload(),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)
        self.assertEqual(response.created_or_updated, "created")
        self.assertEqual(response.items_created, 2)

        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 2, 15))
        self.assertEqual(ScheduleItem.objects.filter(schedule=schedule).count(), 2)
        self.assertEqual(ContentSubmission.objects.count(), 1)

    def test_duplicate_source_message_id_is_idempotent(self):
        request_payload = self._payload()
        async_to_sync(intake_schedule_from_whatsapp)(
            payload=request_payload,
            n8n_api_key="test-intake-key",
        )
        response = async_to_sync(intake_schedule_from_whatsapp)(
            payload=request_payload,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)
        self.assertEqual(response.created_or_updated, "existing")
        self.assertEqual(ContentSubmission.objects.count(), 1)
        self.assertEqual(ScheduleItem.objects.count(), 2)

    def test_duplicate_source_message_id_with_different_payload_returns_conflict(self):
        async_to_sync(intake_schedule_from_whatsapp)(
            payload=self._payload(source_message_id="wamid-conflict"),
            n8n_api_key="test-intake-key",
        )

        response = async_to_sync(intake_schedule_from_whatsapp)(
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
        async_to_sync(intake_schedule_from_whatsapp)(
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
        response = async_to_sync(intake_schedule_from_whatsapp)(
            payload=second,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)
        self.assertEqual(response.created_or_updated, "updated")
        self.assertEqual(response.items_updated, 1)

        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 2, 15))
        self.assertEqual(schedule.title, "Updated Sunday Service")

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
        response = async_to_sync(intake_schedule_from_whatsapp)(
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

        response = async_to_sync(intake_schedule_from_whatsapp)(
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

        response = async_to_sync(intake_schedule_from_whatsapp)(
            payload=payload,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)

        self.assertEqual(ScheduleItem.objects.get(position=1).item_type, "sunday_school")
        self.assertEqual(ScheduleItem.objects.get(position=2).item_type, "closing_prayer")

    def test_uses_human_readable_default_schedule_title(self):
        payload = self._payload(
            source_message_id="wamid-default-title",
            title=None,
        )

        response = async_to_sync(intake_schedule_from_whatsapp)(
            payload=payload,
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, IntakeResponse)

        schedule = ServiceSchedule.objects.get(date=dt.date(2026, 2, 15))
        self.assertEqual(schedule.title, "Sunday Service - February 15, 2026")

    def test_patch_requires_existing_schedule(self):
        response = async_to_sync(patch_schedule_from_whatsapp)(
            payload=self._payload(source_message_id="wamid-patch-missing"),
            n8n_api_key="test-intake-key",
        )
        self.assertIsInstance(response, JSON)
        self.assertEqual(response.status_code, 404)

    def test_patch_can_reuse_raw_message_id_from_create_without_being_blocked(self):
        async_to_sync(intake_schedule_from_whatsapp)(
            payload=self._payload(source_message_id="wamid-shared"),
            n8n_api_key="test-intake-key",
        )

        response = async_to_sync(patch_schedule_from_whatsapp)(
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
        async_to_sync(intake_schedule_from_whatsapp)(
            payload=self._payload(source_message_id="wamid-repeat-patch-create"),
            n8n_api_key="test-intake-key",
        )

        first_response = async_to_sync(patch_schedule_from_whatsapp)(
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

        second_response = async_to_sync(patch_schedule_from_whatsapp)(
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
        async_to_sync(intake_schedule_from_whatsapp)(
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

        response = async_to_sync(patch_schedule_from_whatsapp)(
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
                async_to_sync(intake_whatsapp_schedule)(
                    self._payload(source_message_id="wamid-atomic")
                )

        self.assertEqual(ServiceSchedule.objects.count(), 0)
        self.assertEqual(ScheduleItem.objects.count(), 0)
        self.assertEqual(ContentSubmission.objects.count(), 0)
