from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.song_carts.models import CartStatus, EmailKind, SongCart
from .access import _require_active, _require_team
from .emails import (
    _queue_email, _submission_body, _submission_url, _team_recipients,
    _validate_body,
)


@transaction.atomic
def checkout_cart(cart_id: UUID, *, user: User) -> UUID:
    """Submit the owner's nonempty draft, independently of email delivery."""
    _require_active(user)
    cart = SongCart.objects.select_for_update().select_related("owner").get(
        pk=cart_id, owner=user,
    )
    if cart.status != CartStatus.DRAFT:
        return cart.id
    if not cart.songs.exists():
        raise ValidationError("Add at least one song before submission.")
    cart.status = CartStatus.PENDING
    cart.submitted_at = timezone.now()
    cart.save(update_fields=["status", "submitted_at"])
    body = _submission_body(cart)
    _queue_email(
        cart, EmailKind.RECEIPT,
        f"Worship Prep: submission received for {cart.service_date}",
        "Your song selection has been received and awaits the Technical Team.\n\n"
        f"{body}\n\nYour submission: {_submission_url(cart)}",
        recipients=[cart.owner.email],
    )
    _queue_email(
        cart, EmailKind.TEAM_NOTICE,
        f"Worship Prep: new submission for {cart.service_date}",
        f"A new song selection awaits your review.\n\n{body}\n\n"
        f"Review submission: {_submission_url(cart, admin=True)}",
        recipients=_team_recipients(),
    )
    return cart.id


@transaction.atomic
def confirm_submission(cart_id: UUID, *, user: User) -> UUID:
    """Acknowledge the first Technical Team opening; later openings are no-ops."""
    _require_team(user)
    cart = SongCart.objects.select_for_update().select_related("owner").get(pk=cart_id)
    if cart.status != CartStatus.PENDING:
        return cart.id
    cart.status = CartStatus.CONFIRMED
    cart.confirmed_at = timezone.now()
    cart.confirmed_by = user
    cart.save(update_fields=["status", "confirmed_at", "confirmed_by"])
    _queue_email(
        cart, EmailKind.CONFIRMATION,
        f"Worship Prep: Technical Team has seen your submission for {cart.service_date}",
        "The Technical Team has opened your song selection. This acknowledges receipt; "
        "it does not mean the songs are ready for projection.\n\n"
        f"Your submission: {_submission_url(cart)}",
        recipients=[cart.owner.email],
    )
    return cart.id


@transaction.atomic
def reject_submission(cart_id: UUID, reason: str, *, user: User) -> UUID:
    """Reject a submitted selection without erasing its first acknowledgement."""
    _require_team(user)
    reason = _validate_body(reason, limit=2000)
    cart = SongCart.objects.select_for_update().select_related("owner").get(pk=cart_id)
    if cart.status == CartStatus.REJECTED:
        return cart.id
    if cart.status not in (CartStatus.PENDING, CartStatus.CONFIRMED):
        raise ValidationError("Only submitted selections can be rejected.")
    cart.status = CartStatus.REJECTED
    cart.rejected_at = timezone.now()
    cart.rejected_by = user
    cart.rejection_reason = reason
    cart.save(update_fields=["status", "rejected_at", "rejected_by", "rejection_reason"])
    _queue_email(
        cart, EmailKind.REJECTION,
        f"Worship Prep: selection rejected for {cart.service_date}",
        f"The Technical Team rejected your song selection.\n\nReason: {reason}\n\n"
        "Your songs remain saved. You can add a comment to request clarification.\n"
        f"Your submission: {_submission_url(cart)}",
        recipients=[cart.owner.email],
    )
    return cart.id
