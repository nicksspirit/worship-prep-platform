from typing import NamedTuple

from reactivated import template


class CartSongProps(NamedTuple):
    id: int
    title: str
    author: str
    song_url: str
    remove_url: str


class ServiceSectionProps(NamedTuple):
    label: str
    songs: list[CartSongProps]


class CartSummaryProps(NamedTuple):
    url: str
    service_date: str
    date_label: str
    status: str
    song_count: int
    submitted_at_label: str | None


class CommentProps(NamedTuple):
    id: int
    body: str
    created_at_label: str
    updated_at_label: str | None
    can_edit: bool
    edit_url: str


class DeliveryProps(NamedTuple):
    label: str
    status: str


@template
class SongCartListPage(NamedTuple):
    title: str
    carts: list[CartSummaryProps]
    status_filter: str
    sort: str
    filter_url: str
    error: str | None


@template
class SongCartPage(NamedTuple):
    title: str
    service_date: str
    date_label: str
    status: str
    notification_status: str
    song_count: int
    sections: list[ServiceSectionProps]
    checkout_url: str
    error: str | None
    submitted_at_label: str | None
    confirmed_at_label: str | None
    confirmed_by: str | None
    rejected_at_label: str | None
    rejected_by: str | None
    rejection_reason: str
    comments: list[CommentProps]
    comment_url: str
    comment_body: str
    comment_errors: list[str]
    deliveries: list[DeliveryProps]


class SectionChoiceProps(NamedTuple):
    value: str
    label: str


@template
class AddSongPage(NamedTuple):
    title: str
    song_title: str
    action_url: str
    song_url: str
    service_date: str
    section: str
    sections: list[SectionChoiceProps]
    errors: dict[str, list[str]]
