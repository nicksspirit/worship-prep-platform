from datetime import datetime

from django.urls import reverse
from django.utils import timezone

from apps.song_carts.models import ServiceSection
from apps.song_carts.services import CartDetails
from apps.song_carts.templates import (
    CartSongProps, CartSummaryProps, CommentProps, DeliveryProps,
    ServiceSectionProps, SongCartListPage, SongCartPage,
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
                    reverse("catalog:detail", args=[song.song_uid]),
                    reverse("song_carts:remove", args=[cart.id, song.id]),
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
