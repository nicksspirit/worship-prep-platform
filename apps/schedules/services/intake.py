import datetime as dt
import re
from dataclasses import dataclass

import msgspec
from asgiref.sync import sync_to_async
from django.db import transaction

from apps.schedules.choices import (
    ContactRole,
    ParsedContentType,
    ScheduleItemType,
    ServiceScheduleStatus,
    SubmissionSource,
    SubmissionStatus,
)
from apps.schedules.exceptions import (
    DuplicateScheduleItemTypeError,
    DuplicateSubmissionError,
    ScheduleNotFoundError,
)
from apps.schedules.models import (
    Contact,
    ContentSubmission,
    ScheduleItem,
    ServiceSchedule,
)
from apps.schedules.schemas import AgendaItemPayload, ScheduleIntakePayload

TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")
KNOWN_CONTACT_ALIASES = {
    "the pastor": ("Pastor Ronke Majekodunmi", ContactRole.PASTOR),
    "the vogs": ("Voice of God Singers", ContactRole.CHOIR),
}


@dataclass
class IntakeResult:
    schedule: ServiceSchedule
    created_or_updated: str
    items_created: int
    items_updated: int
    submission: ContentSubmission


@dataclass(frozen=True)
class ScheduleItemData:
    position: int
    item_type: str
    title: str
    start_time: dt.time | None
    end_time: dt.time | None
    is_required: bool
    assigned_contact: Contact | None
    notes: str


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


def normalize_name(raw: str) -> str:
    """Normalize contact names while preserving honorifics and known aliases."""
    condensed_name = " ".join(raw.split()).strip()
    if not condensed_name:
        return ""

    alias = KNOWN_CONTACT_ALIASES.get(condensed_name.lower())
    if alias:
        return alias[0]

    return condensed_name.title()


def infer_contact_role(leader_name: str) -> str:
    normalized_key = " ".join(leader_name.split()).strip().lower()
    alias = KNOWN_CONTACT_ALIASES.get(normalized_key)
    if alias:
        return alias[1]

    lowered_name = leader_name.lower()
    if lowered_name.startswith(("pastor ", "pst. ", "pst ")):
        return ContactRole.PASTOR
    if lowered_name.startswith(("min. ", "min ", "minister ")):
        return ContactRole.MINISTER
    return ContactRole.OTHER


def default_schedule_title(target_date: dt.date) -> str:
    return f"Sunday Service - {target_date.strftime('%B')} {target_date.day}, {target_date.year}"


def default_sender_name(source: str | None) -> str:
    normalized_source = (source or "unknown").strip().lower()
    if normalized_source == SubmissionSource.WHATSAPP:
        return "WhatsApp Intake Agent"
    if normalized_source == SubmissionSource.EMAIL:
        return "Email Intake Agent"
    return "Automated Intake"


def infer_item_type(item: AgendaItemPayload) -> str:
    if item.item_type:
        raw = item.item_type.strip().lower()
        valid_values = {choice for choice, _ in ScheduleItemType.choices}
        if raw in valid_values:
            return raw

    title = item.title.lower()
    if "sunday school" in title:
        return ScheduleItemType.SUNDAY_SCHOOL
    if "final prayer" in title or "closing prayer" in title or "benediction" in title:
        return ScheduleItemType.CLOSING_PRAYER
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
    if "announcement" in title or "welcome" in title or "comtv" in title:
        return ScheduleItemType.ANNOUNCEMENTS
    if "offering" in title or "tithe" in title:
        return ScheduleItemType.OFFERING
    return ScheduleItemType.SPECIAL_ITEM


def get_or_create_contact(leader_name: str | None, phone: str | None) -> Contact | None:
    if not leader_name:
        return None

    normalized_name = normalize_name(leader_name)
    if not normalized_name:
        return None

    contact, _ = Contact.objects.get_or_create(
        name=normalized_name,
        phone=phone or "",
        defaults={"role": infer_contact_role(leader_name)},
    )
    return contact


def validate_unique_item_types(items: list[AgendaItemPayload]) -> None:
    seen_item_types: set[str] = set()
    for item in items:
        item_type = infer_item_type(item)
        if item_type in seen_item_types:
            raise DuplicateScheduleItemTypeError(
                f"Schedule items must be unique per type. Duplicate type: '{item_type}'."
            )
        seen_item_types.add(item_type)


def upsert_schedule_item(
    *,
    schedule: ServiceSchedule,
    item_data: ScheduleItemData,
) -> bool:
    def shift_items_from_position(start_position: int, *, exclude_pk: str | None = None) -> None:
        occupied_items = (
            ScheduleItem.objects.select_for_update()
            .filter(schedule=schedule, position__gte=start_position)
            .order_by("-position")
        )
        for occupied_item in occupied_items:
            if exclude_pk is not None and str(occupied_item.pk) == exclude_pk:
                continue
            occupied_item.position += 1
            occupied_item.save(update_fields=["position", "updated_on"])

    schedule_item = (
        ScheduleItem.objects.select_for_update()
        .filter(schedule=schedule, item_type=item_data.item_type)
        .first()
    )
    if schedule_item is None:
        schedule_item = (
            ScheduleItem.objects.select_for_update()
            .filter(schedule=schedule, position=item_data.position)
            .first()
        )
        if schedule_item is not None and schedule_item.item_type != item_data.item_type:
            shift_items_from_position(item_data.position)
            schedule_item = None

    if schedule_item is None:
        ScheduleItem.objects.create(
            schedule=schedule,
            position=item_data.position,
            item_type=item_data.item_type,
            title=item_data.title,
            start_time=item_data.start_time,
            end_time=item_data.end_time,
            is_required=item_data.is_required,
            assigned_contact=item_data.assigned_contact,
            notes=item_data.notes,
        )
        return True

    if schedule_item.position != item_data.position:
        conflicting_item = (
            ScheduleItem.objects.select_for_update()
            .filter(schedule=schedule, position=item_data.position)
            .exclude(pk=schedule_item.pk)
            .first()
        )
        if conflicting_item is not None:
            shift_items_from_position(item_data.position, exclude_pk=str(schedule_item.pk))

    schedule_item.position = item_data.position
    schedule_item.item_type = item_data.item_type
    schedule_item.title = item_data.title
    schedule_item.start_time = item_data.start_time
    schedule_item.end_time = item_data.end_time
    schedule_item.is_required = item_data.is_required
    schedule_item.assigned_contact = item_data.assigned_contact
    schedule_item.notes = item_data.notes
    schedule_item.save(
        update_fields=[
            "position",
            "item_type",
            "title",
            "start_time",
            "end_time",
            "is_required",
            "assigned_contact",
            "notes",
            "updated_on",
        ]
    )
    return False


@transaction.atomic
def _intake_schedule_sync(
    payload: ScheduleIntakePayload,
    *,
    allow_create: bool,
) -> IntakeResult:
    builtins_payload = msgspec.to_builtins(payload)
    submission_message_id = payload.source_message_id if allow_create else None
    sender_name = payload.sender_name or default_sender_name(payload.source)

    validate_unique_item_types(payload.items)

    existing_submission = None
    if allow_create and submission_message_id:
        existing_submission = (
            ContentSubmission.objects.filter(source_message_id=submission_message_id)
            .select_related("created_schedule")
            .first()
        )
        if existing_submission and existing_submission.created_schedule:
            if existing_submission.parsed_payload != builtins_payload:
                raise DuplicateSubmissionError(
                    f"Submission {payload.source_message_id} was already processed with "
                    "different content."
                )
            return IntakeResult(
                schedule=existing_submission.created_schedule,
                created_or_updated="existing",
                items_created=0,
                items_updated=0,
                submission=existing_submission,
            )

    created = False
    if allow_create:
        schedule, created = ServiceSchedule.objects.get_or_create(
            date=payload.target_date,
            defaults={
                "title": payload.title or default_schedule_title(payload.target_date),
                "status": ServiceScheduleStatus.IN_PROGRESS,
            },
        )
    else:
        schedule = ServiceSchedule.objects.filter(date=payload.target_date).first()
        if schedule is None:
            raise ScheduleNotFoundError(
                f"No service schedule exists for {payload.target_date.isoformat()}."
            )

    if not created:
        if payload.title and schedule.title != payload.title:
            schedule.title = payload.title
        schedule.status = ServiceScheduleStatus.IN_PROGRESS
        schedule.save(update_fields=["title", "status", "updated_on"])

    items_created = 0
    items_updated = 0
    for index, item in enumerate(payload.items, start=1):
        item_data = ScheduleItemData(
            position=item.position or index,
            item_type=infer_item_type(item),
            title=item.title,
            start_time=parse_optional_time(item.time_start),
            end_time=parse_optional_time(item.time_end),
            is_required=item.is_required,
            assigned_contact=get_or_create_contact(
                item.leader_name, payload.sender_phone
            ),
            notes=item.notes or "",
        )

        item_created = upsert_schedule_item(
            schedule=schedule,
            item_data=item_data,
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
    raw_content = payload.raw_content or parsed_body
    if not raw_content:
        raw_content = (
            f"Partial schedule intake for {payload.target_date.isoformat()}"
        )
    source_value = (payload.source or "unknown").lower()
    if source_value == "whatsapp":
        submission_source = SubmissionSource.WHATSAPP
    elif source_value == "email":
        submission_source = SubmissionSource.EMAIL
    else:
        submission_source = SubmissionSource.UNKNOWN

    submission = ContentSubmission.objects.create(
        source=submission_source,
        sender_phone=payload.sender_phone,
        sender_email=payload.sender_email,
        sender_name=sender_name,
        source_message_id=submission_message_id,
        raw_content=raw_content,
        parsed_content_type=ParsedContentType.AGENDA,
        parsed_title=payload.title,
        parsed_body=parsed_body or raw_content,
        parsed_payload=builtins_payload,
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


async def intake_schedule(payload: ScheduleIntakePayload) -> IntakeResult:
    return await sync_to_async(_intake_schedule_sync, thread_sensitive=True)(
        payload,
        allow_create=True,
    )


async def patch_schedule(payload: ScheduleIntakePayload) -> IntakeResult:
    return await sync_to_async(_intake_schedule_sync, thread_sensitive=True)(
        payload,
        allow_create=False,
    )
