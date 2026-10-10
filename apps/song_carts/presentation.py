from datetime import datetime

from django.urls import reverse
from django.utils import timezone

from apps.song_carts.models import ServiceSection
from apps.catalog.templates import SlideProps
from apps.song_carts.services import CartDetails, UnlistedSongDetails
from apps.song_carts.templates import (
    CartSongProps, CartSummaryProps, CommentProps, DeliveryProps,
    SectionChoiceProps, ServiceSectionProps, SongCartListPage, SongCartPage,
    UnlistedSongPage,
)


def _time(value: datetime | None) -> str | None:
    if value is None:
        return None
    return timezone.localtime(value).strftime("%b %d, %Y · %I:%M %p %Z")


def present_carts(
    carts: list[CartDetails], *, status_filter: str = "", sort: str = "service_date_desc",
    error: str | None = None,
) -> SongCartListPage:
    """Map the user's cart history to rendered page props."""
    return SongCartListPage("My submissions", [
        CartSummaryProps(
            reverse("song_carts:detail", args=[cart.id]),
            cart.service_date.isoformat(),
            cart.service_date.strftime("%A, %B %d, %Y"),
            cart.status,
            len(cart.songs),
            _time(cart.submitted_at),
        ) for cart in carts
    ], status_filter, sort, reverse("song_carts:list"), error)


def present_cart(
    cart: CartDetails, *, error: str | None = None, comment_body: str = "",
    comment_errors: list[str] | None = None,
) -> SongCartPage:
    """Group retained song metadata into predefined service sections."""
    return SongCartPage(
        title="Song cart" if cart.status == "draft" else "Song submission",
        service_date=cart.service_date.isoformat(),
        date_label=cart.service_date.strftime("%A, %B %d, %Y"),
        status=cart.status,
        notification_status=cart.notification_status,
        song_count=len(cart.songs),
        sections=[
            ServiceSectionProps(label, [
                CartSongProps(
                    song.id, song.title, ", ".join(song.authors),
                    reverse("song_carts:unlisted_detail", args=[cart.id, song.id])
                    if song.song_uid is None else
                    reverse("catalog:detail", args=[song.song_uid]),
                    reverse("song_carts:remove", args=[cart.id, song.id]),
                    song.song_uid is None,
                    song.song_uid is not None or song.reviewed_at is not None,
                ) for song in cart.songs if song.section == section
            ]) for section, label in ServiceSection.choices
        ],
        checkout_url=reverse("song_carts:checkout", args=[cart.id]),
        error=error,
        submitted_at_label=_time(cart.submitted_at),
        confirmed_at_label=_time(cart.confirmed_at),
        confirmed_by=cart.confirmed_by,
        rejected_at_label=_time(cart.rejected_at),
        rejected_by=cart.rejected_by,
        rejection_reason=cart.rejection_reason,
        comments=[CommentProps(
            comment.id, comment.body, _time(comment.created_at) or "",
            _time(comment.updated_at),
            comment.can_edit,
            reverse("song_carts:edit_comment", args=[cart.id, comment.id]),
        ) for comment in cart.comments],
        comment_url=reverse("song_carts:add_comment", args=[cart.id]),
        comment_body=comment_body,
        comment_errors=comment_errors or [],
        deliveries=[DeliveryProps(email.label, email.status) for email in cart.emails],
    )


def present_unlisted_song(
    song: UnlistedSongDetails | None, *, song_title: str, lyrics: str,
    service_date: str, section: str, errors: dict[str, list[str]] | None = None,
) -> UnlistedSongPage:
    """Map saved lyrics and bound input to the form and reviewed preview."""
    if song is not None and not song.can_edit:
        song_title, lyrics = song.title, song.lyrics
        service_date, section = song.service_date.isoformat(), song.section
    current = song is not None and (
        song_title, lyrics, service_date, section
    ) == (song.title, song.lyrics, song.service_date.isoformat(), song.section)
    if song is not None:
        service_date = song.service_date.isoformat()
    slides = []
    if current and song is not None:
        for prepared in song.sections:
            for lines in prepared.slides:
                slides.append(SlideProps(len(slides) + 1, prepared.label, list(lines)))
    return UnlistedSongPage(
        title="Add an unlisted song" if song is None else "Unlisted song",
        song_title=song_title, lyrics=lyrics, service_date=service_date,
        date_label=song.service_date.strftime("%A, %B %d, %Y") if song else None,
        section=section,
        sections=[SectionChoiceProps(value, label) for value, label in ServiceSection.choices],
        action_url=reverse("song_carts:unlisted_detail", args=[song.cart_id, song.id])
        if song else reverse("song_carts:add_unlisted"),
        cart_url=reverse("song_carts:detail", args=[song.cart_id]) if song else None,
        can_edit=song.can_edit if song else True,
        reviewed=song.reviewed_at is not None if song else False,
        review_url=reverse("song_carts:review_unlisted", args=[song.cart_id, song.id])
        if song and song.can_edit and current else None,
        fingerprint=song.fingerprint if song and current else "",
        errors=errors or {}, slides=slides,
        formatted_text=song.formatted_text if song and current else "",
    )
