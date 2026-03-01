import datetime as dt
import re
from dataclasses import dataclass

import msgspec

from apps.schedules.choices import (
    ContactRole,
    ParsedContentType,
    ScheduleItemType,
    ServiceScheduleStatus,
    SubmissionSource,
    SubmissionStatus,
)
from apps.schedules.models import Contact, ContentSubmission, ScheduleItem, ServiceSchedule
from apps.schedules.schemas import AgendaItemPayload, WhatsAppScheduleIntakePayload


TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")


@dataclass
class IntakeResult:
    schedule: ServiceSchedule
    created_or_updated: str
    items_created: int
    items_updated: int
    submission: ContentSubmission


def parse_optional_time(value: str | None) -> dt.time | None:
    if not value:
        return None

    match = TIME_RE.match(value.strip())
    if not match:
        return None

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if hour > 23 or minute > 59:
        return None

    return dt.time(hour=hour, minute=minute)


def infer_item_type(item: AgendaItemPayload) -> str:
    if item.item_type:
        raw = item.item_type.strip().lower()
        valid_values = {choice for choice, _ in ScheduleItemType.choices}
        if raw in valid_values:
            return raw

    title = item.title.lower()
    if "prayer" in title:
        return ScheduleItemType.OPENING_PRAYER
    if "hymn" in title:
        return ScheduleItemType.HYMN
    if "song" in title or "worship" in title or "praise" in title:
        return ScheduleItemType.WORSHIP_SONG
    if "scripture" in title or "reading" in title:
        return ScheduleItemType.SCRIPTURE_READING
    if "sermon" in title or "word" in title:
        return ScheduleItemType.SERMON
    if "announcement" in title or "welcome" in title:
        return ScheduleItemType.ANNOUNCEMENTS
    if "offering" in title or "tithe" in title:
        return ScheduleItemType.OFFERING
    return ScheduleItemType.SPECIAL_ITEM


async def get_or_create_contact(leader_name: str | None, phone: str | None) -> Contact | None:
    if not leader_name:
        return None

    normalized_name = " ".join(leader_name.split())
    if not normalized_name:
        return None

    contact, _ = await Contact.objects.aget_or_create(
        name=normalized_name,
        phone=phone or "",
        defaults={"role": ContactRole.MINISTER},
    )
    return contact


async def intake_whatsapp_schedule(payload: WhatsAppScheduleIntakePayload) -> IntakeResult:
    existing_submission = None
    if payload.source_message_id:
        existing_submission = await ContentSubmission.objects.filter(
            source_message_id=payload.source_message_id
        ).select_related("created_schedule").afirst()
        if existing_submission and existing_submission.created_schedule:
            return IntakeResult(
                schedule=existing_submission.created_schedule,
                created_or_updated="existing",
                items_created=0,
                items_updated=0,
                submission=existing_submission,
            )

    schedule, created = await ServiceSchedule.objects.aget_or_create(
        date=payload.target_date,
        defaults={
            "title": payload.title or f"Sunday Service - {payload.target_date.isoformat()}",
            "status": ServiceScheduleStatus.IN_PROGRESS,
        },
    )

    if not created:
        if payload.title and schedule.title != payload.title:
            schedule.title = payload.title
        schedule.status = ServiceScheduleStatus.IN_PROGRESS
        await schedule.asave(update_fields=["title", "status", "updated_on"])

    items_created = 0
    items_updated = 0
    for index, item in enumerate(payload.items, start=1):
        position = item.position or index
        assigned_contact = await get_or_create_contact(item.leader_name, payload.sender_phone)
        defaults = {
            "item_type": infer_item_type(item),
            "title": item.title,
            "start_time": parse_optional_time(item.time_start),
            "end_time": parse_optional_time(item.time_end),
            "is_required": item.is_required,
            "assigned_contact": assigned_contact,
            "notes": item.notes or "",
        }
        _schedule_item, item_created = await ScheduleItem.objects.aupdate_or_create(
            schedule=schedule,
            position=position,
            defaults=defaults,
        )
        if item_created:
            items_created += 1
        else:
            items_updated += 1

    parsed_body = "\n".join(
        [
            f"{item.position or idx}. {item.title}"
            for idx, item in enumerate(payload.items, start=1)
        ]
    )
    submission = await ContentSubmission.objects.acreate(
        source=SubmissionSource.WHATSAPP,
        sender_phone=payload.sender_phone,
        sender_email=payload.sender_email,
        sender_name=payload.sender_name,
        source_message_id=payload.source_message_id,
        raw_content=payload.raw_content,
        parsed_content_type=ParsedContentType.AGENDA,
        parsed_title=payload.title,
        parsed_body=parsed_body or payload.raw_content,
        parsed_payload=msgspec.to_builtins(payload),
        target_date=payload.target_date,
        status=SubmissionStatus.MATCHED,
        created_schedule=schedule,
    )

    return IntakeResult(
        schedule=schedule,
        created_or_updated="created" if created else "updated",
        items_created=items_created,
        items_updated=items_updated,
        submission=submission,
    )
