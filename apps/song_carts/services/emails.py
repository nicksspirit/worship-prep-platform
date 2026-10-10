from functools import partial
from uuid import UUID

import structlog
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.song_carts.models import (
    CartStatus, EmailKind, NotificationStatus, ServiceSection, SongCart, SubmissionEmail,
)
from .access import TECHNICAL_TEAM, _require_active, _require_team
from .prepare_lyrics import _format_sections, _read_sections

logger = structlog.get_logger(__name__)


def _team_recipients() -> list[str]:
    return list(User.objects.filter(
        is_active=True, is_staff=True, groups__name=TECHNICAL_TEAM,
    ).exclude(email="").values_list("email", flat=True).distinct())


def _submission_url(cart: SongCart, *, admin: bool = False) -> str:
    path = reverse(
        "admin:song_carts_songcart_change" if admin else "song_carts:detail",
        args=[cart.id],
    )
    site = Site.objects.filter(pk=getattr(settings, "SITE_ID", 1)).first()
    domain = site.domain.strip() if site else ""
    scheme = "http" if domain.startswith(("localhost", "127.0.0.1")) else "https"
    return f"{scheme}://{domain}{path}" if domain else path


def _submission_body(cart: SongCart) -> str:
    lines = [
        f"Service date: {cart.service_date:%A, %B %d, %Y}",
        f"Submitted by: {cart.owner.get_full_name() or cart.owner.email} "
        f"<{cart.owner.email}>", "",
    ]
    songs = list(cart.songs.all())
    for section, label in ServiceSection.choices:
        lines.append(label)
        selected = [song for song in songs if song.section == section]
        for index, song in enumerate(selected, 1):
            lines.append(
                f"{index}. #{song.id} {song.title}"
                + (f" — {', '.join(song.authors)}" if song.authors else "")
            )
            if song.song_uid is None:
                lines.append("Unlisted song — reviewed projection text")
                lines.append(_format_sections(_read_sections(song.prepared_sections)))
                lines.append("")
        if not selected:
            lines.append("No songs selected.")
        lines.append("")
    comments = list(cart.comments.all())
    if comments:
        lines.append("Owner comments")
        lines.extend(comment.body for comment in comments)
    return "\n".join(lines)


def _queue_email(
    cart: SongCart, kind: str, subject: str, body: str,
    *, recipients: list[str], event_key: str = "",
) -> SubmissionEmail:
    email, created = SubmissionEmail.objects.get_or_create(
        cart=cart, kind=kind, event_key=event_key,
        defaults={"recipients": recipients, "subject": subject, "body": body},
    )
    if created:
        # shortcut: Delivery runs inline after commit; add a worker for automatic retries.
        transaction.on_commit(partial(_deliver_email, email.id), robust=True)
    return email


@transaction.atomic
def _deliver_email(email_id: int) -> bool:
    email = SubmissionEmail.objects.select_for_update().get(pk=email_id)
    if email.status == NotificationStatus.SENT:
        return True
    try:
        if not email.recipients:
            raise ValueError("No active Technical Team members have email addresses.")
        team = email.kind in (EmailKind.TEAM_NOTICE, EmailKind.COMMENT)
        sent = EmailMessage(
            subject=email.subject, body=email.body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[] if team else email.recipients,
            bcc=email.recipients if team else [],
            connection=get_connection(timeout=10),
        ).send(fail_silently=False)
        if not sent:
            raise RuntimeError("The email backend did not accept the message.")
    except Exception as exc:
        email.status = NotificationStatus.FAILED
        email.error = str(exc)[:1000]
        logger.exception("submission_email_failed", email_id=email.id)
    else:
        email.status = NotificationStatus.SENT
        email.error = ""
        email.sent_at = timezone.now()
    email.save(update_fields=["status", "error", "sent_at"])
    if email.kind == EmailKind.TEAM_NOTICE:
        SongCart.objects.filter(pk=email.cart_id).update(
            notification_status=email.status,
            notification_error=email.error, notified_at=email.sent_at,
        )
    return email.status == NotificationStatus.SENT


def retry_submission_emails(cart_id: UUID, *, user: User) -> tuple[int, int]:
    """Retry unsent events individually without changing submission state."""
    _require_team(user)
    cart = SongCart.objects.get(pk=cart_id)
    sent = failed = 0
    for email in cart.emails.exclude(status=NotificationStatus.SENT):
        if not email.recipients and email.kind in (
            EmailKind.TEAM_NOTICE, EmailKind.COMMENT,
        ):
            SubmissionEmail.objects.filter(pk=email.id).update(
                recipients=_team_recipients(),
            )
        if _deliver_email(email.id):
            sent += 1
        else:
            failed += 1
    return sent, failed


def notify_cart(cart_id: UUID, *, user: User) -> bool:
    """Compatibility entry point for retrying existing submission emails."""
    _require_active(user)
    cart = SongCart.objects.get(pk=cart_id)
    if cart.owner_id != user.pk and not user.is_staff:
        raise PermissionDenied("Only the owner or an administrator can retry emails.")
    if cart.status == CartStatus.DRAFT:
        raise ValidationError("Submit the song cart before sending notifications.")
    results = [_deliver_email(email.id) for email in cart.emails.exclude(
        status=NotificationStatus.SENT,
    )]
    return (
        all(results) if results
        else cart.notification_status == NotificationStatus.SENT
    )


def send_submission_reply(
    cart_id: UUID, body: str, *, user: User, request_id: UUID,
) -> bool:
    """Send an idempotent team email to the owner without adding a thread comment."""
    _require_team(user)
    if not isinstance(request_id, UUID):
        raise ValidationError("A valid reply request identifier is required.")
    body = _validate_body(body, limit=10000)
    with transaction.atomic():
        cart = SongCart.objects.select_for_update().select_related("owner").get(
            pk=cart_id,
        )
        if cart.status == CartStatus.DRAFT:
            raise ValidationError("Submit the selection before sending a reply.")
        email = _queue_email(
            cart, EmailKind.REPLY, f"Worship Prep: reply for {cart.service_date}",
            f"{body}\n\nYour submission: {_submission_url(cart)}",
            recipients=[cart.owner.email], event_key=str(request_id),
        )
    email.refresh_from_db()
    return email.status == NotificationStatus.SENT


def _validate_body(body: str, *, limit: int = 5000) -> str:
    if not isinstance(body, str) or not body.strip():
        raise ValidationError("Enter a message.")
    if len(body.strip()) > limit:
        raise ValidationError(f"Messages cannot exceed {limit:,} characters.")
    return body.strip()
