import datetime as dt

import msgspec


class AgendaItemPayload(msgspec.Struct, kw_only=True):
    position: int | None = None
    time_start: str | None = None
    time_end: str | None = None
    item_type: str | None = None
    title: str
    leader_name: str | None = None
    notes: str | None = None
    is_required: bool = True


class WhatsAppScheduleIntakePayload(msgspec.Struct, kw_only=True):
    source: str
    target_date: dt.date
    raw_content: str
    sender_name: str
    sender_phone: str | None = None
    sender_email: str | None = None
    source_message_id: str | None = None
    title: str | None = None
    items: list[AgendaItemPayload] = []


class IntakeResponse(msgspec.Struct, kw_only=True):
    schedule_id: str
    date: str
    created_or_updated: str
    items_created: int
    items_updated: int
    confirmation_text: str
