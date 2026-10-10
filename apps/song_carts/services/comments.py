from datetime import datetime, timedelta
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.song_carts.models import CartComment, CartStatus, EmailKind, SongCart
from .access import _require_active
from .emails import _queue_email, _submission_url, _team_recipients, _validate_body


def _edit_deadline(comment: CartComment, cart: SongCart) -> datetime | None:
    if cart.status == CartStatus.DRAFT:
        return None
    return max(comment.created_at, cart.submitted_at or comment.created_at) + timedelta(
        minutes=15,
    )


def _can_edit(comment: CartComment, cart: SongCart, user: User) -> bool:
    deadline = _edit_deadline(comment, cart)
    return comment.author_id == user.pk and (
        deadline is None or timezone.now() < deadline
    )


def _notify_comment(cart: SongCart, comment: CartComment) -> None:
    if cart.status == CartStatus.DRAFT:
        return
    _queue_email(
        cart, EmailKind.COMMENT, f"Worship Prep: comment for {cart.service_date}",
        f"{cart.owner.get_full_name() or cart.owner.email} "
        "posted or edited a comment:\n\n"
        f"{comment.body}\n\nReview submission: {_submission_url(cart, admin=True)}",
        recipients=_team_recipients(),
        event_key=(
            f"{comment.id}:{(comment.updated_at or comment.created_at).isoformat()}"
        ),
    )


@transaction.atomic
def add_comment(cart_id: UUID, body: str, *, user: User) -> int:
    """Add an owner-authored comment without changing the selected songs."""
    _require_active(user)
    body = _validate_body(body)
    cart = SongCart.objects.select_for_update().select_related("owner").get(
        pk=cart_id, owner=user,
    )
    comment = CartComment.objects.create(cart=cart, author=user, body=body)
    _notify_comment(cart, comment)
    return comment.id


@transaction.atomic
def edit_comment(cart_id: UUID, comment_id: int, body: str, *, user: User) -> int:
    """Edit only the author's comment while its server-enforced window is open."""
    _require_active(user)
    body = _validate_body(body)
    cart = SongCart.objects.select_for_update().select_related("owner").get(
        pk=cart_id, owner=user,
    )
    comment = CartComment.objects.filter(pk=comment_id, cart=cart).first()
    if comment is None:
        raise ValidationError("Comment not found in this submission.")
    if comment.author_id != user.pk:
        raise PermissionDenied("Only the comment author may edit it.")
    if not _can_edit(comment, cart, user):
        raise ValidationError(
            "The 15-minute edit window has closed. Add a follow-up comment."
        )
    if comment.body != body:
        comment.body = body
        comment.updated_at = timezone.now()
        comment.save(update_fields=["body", "updated_at"])
        _notify_comment(cart, comment)
    return comment.id
