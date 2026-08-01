"""Signal handlers for invitation review and role assignment."""

import structlog
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from invitations.signals import invite_accepted

from apps.accounts.models import AccessLevel, InvitationRequest, RequestStatus, User

logger = structlog.get_logger(__name__)


def _build_invitation_request_review_url(invitation_request_id: int) -> str:
    path = reverse(
        "admin:accounts_invitationrequest_change",
        args=[invitation_request_id],
    )
    domain = Site.objects.get_current().domain.strip()
    if not domain:
        return path

    scheme = "http" if domain.startswith(("localhost", "127.0.0.1")) else "https"
    return f"{scheme}://{domain}{path}"


def _send_invitation_request_notification(invitation_request_id: int) -> None:
    invitation_request = InvitationRequest.objects.filter(
        pk=invitation_request_id
    ).first()
    if invitation_request is None:
        return

    admin_emails = list(
        User.objects.filter(is_active=True, is_staff=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not admin_emails:
        return

    review_url = _build_invitation_request_review_url(invitation_request.pk)
    message = (
        "A new invitation request has been submitted and is waiting for review.\n\n"
        f"Name: {invitation_request.first_name} {invitation_request.last_name}\n"
        f"Email: {invitation_request.email}\n"
        f"Message: {invitation_request.message or '(none)'}\n\n"
        f"Review request: {review_url}\n"
    )

    try:
        EmailMessage(
            subject="Worship Prep: invitation request needs review",
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[],
            bcc=admin_emails,
        ).send(fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send invitation request review notification for request %s",
            invitation_request.pk,
        )


@receiver(post_save, sender=InvitationRequest)
def notify_admins_about_invitation_request(
    sender,
    instance: InvitationRequest,
    created: bool,
    **kwargs,
) -> None:
    """Notify active staff users when a new invitation request is submitted."""
    if not created or instance.status != RequestStatus.PENDING:
        return

    transaction.on_commit(
        lambda invitation_request_id=instance.pk: _send_invitation_request_notification(
            invitation_request_id
        )
    )


@receiver(invite_accepted)
def assign_staff_from_invitation_request(
    sender,
    email: str,
    invitation,
    **kwargs,
) -> None:
    """When an invite is accepted, apply access level from the linked invitation request."""
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        return

    req = (
        InvitationRequest.objects.filter(invitation=invitation).first()
        or InvitationRequest.objects.filter(email__iexact=email).first()
    )
    if req is None:
        return

    if req.access_level == AccessLevel.CATALOG_ADMIN and not user.is_staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
