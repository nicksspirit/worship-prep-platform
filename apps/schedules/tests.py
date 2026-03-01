import datetime as dt

import msgspec
from asgiref.sync import async_to_sync
from django.test import TestCase, override_settings
from django_bolt import JSON

from apps.schedules.api import intake_schedule_from_whatsapp
from apps.schedules.models import ContentSubmission, ScheduleItem, ServiceSchedule
from apps.schedules.schemas import IntakeResponse, WhatsAppScheduleIntakePayload


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
        self.assertEqual(schedule.schedule_items.count(), 2)
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
