from typing import NamedTuple

from reactivated import template

from apps.catalog.templates import SlideProps


class CartSongProps(NamedTuple):
    id: int
    title: str
    author: str
    song_url: str
    remove_url: str
    is_unlisted: bool
    is_reviewed: bool


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


@template
class UnlistedSongPage(NamedTuple):
    title: str
    song_title: str
    lyrics: str
    service_date: str
    date_label: str | None
    section: str
    sections: list[SectionChoiceProps]
    action_url: str
    cart_url: str | None
    can_edit: bool
    reviewed: bool
    review_url: str | None
    fingerprint: str
    errors: dict[str, list[str]]
    slides: list[SlideProps]
    formatted_text: str
