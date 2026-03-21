"""Signal handlers for user lifecycle (django-invitations integration)."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _

from invitations.signals import invite_accepted

from apps.users.models import AccessLevel, InvitationRequest, RequestStatus

logger = logging.getLogger(__name__)


def _public_base_url() -> str:
    """Base URL for building links in outbound email (SITE_BASE_URL or django.contrib.sites)."""
    configured = getattr(settings, "SITE_BASE_URL", "") or ""
    if configured:
        return configured.rstrip("/")
    try:
        from django.contrib.sites.models import Site

        site = Site.objects.get_current()
        domain = (site.domain or "").strip()
        if domain.startswith("http://") or domain.startswith("https://"):
            return domain.rstrip("/")
        local = domain.startswith("127.") or "localhost" in domain
        scheme = "http" if local else "https"
        return f"{scheme}://{domain}".rstrip("/")
    except Exception:
        return "http://127.0.0.1:8000"


@receiver(post_save, sender=InvitationRequest)
def notify_staff_on_new_invitation_request(
    sender,
    instance: InvitationRequest,
    created: bool,
    **kwargs,
) -> None:
    """Email all active staff when a new invitation request is submitted."""
    if not created or instance.status != RequestStatus.PENDING:
        return

    User = get_user_model()
    recipients = list(
        User.objects.filter(is_staff=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        return

    base = _public_base_url()
    list_path = reverse("admin:users_invitationrequest_changelist")
    detail_path = reverse("admin:users_invitationrequest_change", args=[instance.pk])
    list_url = f"{base}{list_path}"
    detail_url = f"{base}{detail_path}"

    subject = _("New invitation request: %(email)s") % {"email": instance.email}
    body = _(
        "A new invitation request was submitted and needs review.\n\n"
        "Requester email: %(email)s\n"
        "Name: %(first)s %(last)s\n"
        "Message (optional):\n%(message)s\n\n"
        "Review in admin (list):\n%(list_url)s\n\n"
        "Open this request:\n%(detail_url)s\n"
    ) % {
        "email": instance.email,
        "first": instance.first_name,
        "last": instance.last_name,
        "message": instance.message or _("(none)"),
        "list_url": list_url,
        "detail_url": detail_url,
    }

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send invitation-request notification email to staff"
        )


@receiver(invite_accepted)
def assign_staff_from_invitation_request(
    sender,
    email: str,
    invitation,
    **kwargs,
) -> None:
    """When an invite is accepted, apply access level from the linked invitation request."""
    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        return

    req = (
        InvitationRequest.objects.filter(invitation=invitation).first()
        or InvitationRequest.objects.filter(email__iexact=email).first()
    )
    if req is None:
        return

    if req.access_level == AccessLevel.ADMIN and not user.is_staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
