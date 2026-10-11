"""Invitation request use cases."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import structlog
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.urls import reverse
from invitations.exceptions import AlreadyAccepted, AlreadyInvited, UserRegisteredEmail
from invitations.forms import CleanEmailMixin
from invitations.models import Invitation as InvitationModel
from invitations.utils import get_invitation_model

from apps.accounts.models import (
    AccessLevel,
    InvitationAccess,
    InvitationRequest,
    RequestStatus,
    User,
)

logger = structlog.get_logger(__name__)
Invitation = get_invitation_model()


@dataclass(frozen=True, slots=True)
class InvitationRequestInput:
    """Validated details supplied by a person requesting an invitation."""

    email: str
    first_name: str
    last_name: str
    message: str


@dataclass(frozen=True, slots=True)
class InvitationApproval:
    """One approval attempt an admin adapter can render."""

    email: str
    outcome: Literal[
        "sent", "already_invited", "already_accepted", "already_registered", "failed"
    ]


@dataclass(frozen=True, slots=True)
class InvitationRejection:
    """The number of pending requests rejected by one review action."""

    count: int


def submit_invitation_request(data: InvitationRequestInput) -> InvitationRequest:
    """Store one validated public request for Superuser review."""

    return InvitationRequest.objects.create(
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        message=data.message,
        access_level=AccessLevel.MEMBER,
    )


@transaction.atomic
def send_invitation(
    email: str,
    *,
    inviter: User,
    deliver: Callable[[InvitationModel], None],
    access_level: AccessLevel = AccessLevel.MEMBER,
) -> InvitationModel:
    """Send a Superuser's direct invitation with the selected access tier."""

    if not inviter.is_active or not inviter.is_superuser:
        raise PermissionDenied
    access_level = AccessLevel(access_level)
    email = email.strip().lower()
    validate_email(email)
    CleanEmailMixin().validate_invitation(email)
    invitation = Invitation.create(email=email, inviter=inviter)
    InvitationAccess.objects.create(invitation=invitation, access_level=access_level)
    deliver(invitation)
    return invitation


@transaction.atomic
def approve_invitation_request(
    invitation_request_id: int,
    *,
    reviewer: User,
    deliver: Callable[[InvitationModel], None],
    access_level: str = AccessLevel.MEMBER,
) -> InvitationApproval:
    """Approve one pending request, create its invitation, and send it."""

    if not reviewer.is_active or not reviewer.is_superuser:
        raise PermissionDenied
    access_level = AccessLevel(access_level)
    invitation_request = InvitationRequest.objects.select_for_update().get(
        pk=invitation_request_id
    )
    if invitation_request.status != RequestStatus.PENDING:
        return InvitationApproval(invitation_request.email, "failed")

    try:
        CleanEmailMixin().validate_invitation(invitation_request.email)
    except AlreadyInvited:
        return InvitationApproval(invitation_request.email, "already_invited")
    except AlreadyAccepted:
        return InvitationApproval(invitation_request.email, "already_accepted")
    except UserRegisteredEmail:
        return InvitationApproval(invitation_request.email, "already_registered")

    try:
        with transaction.atomic():
            invitation = Invitation.create(
                email=invitation_request.email, inviter=reviewer
            )
    except IntegrityError:
        return InvitationApproval(invitation_request.email, "failed")

    deliver(invitation)
    invitation_request.status = RequestStatus.APPROVED
    invitation_request.access_level = access_level
    invitation_request.reviewed_by = reviewer
    invitation_request.invitation = invitation
    invitation_request.save(
        update_fields=[
            "status",
            "access_level",
            "reviewed_by",
            "invitation",
            "updated_on",
        ]
    )
    return InvitationApproval(invitation_request.email, "sent")


@transaction.atomic
def reject_invitation_requests(
    invitation_requests: list[int], *, reviewer: User
) -> InvitationRejection:
    """Reject the selected requests that remain pending."""

    count = 0
    for invitation_request in InvitationRequest.objects.select_for_update().filter(
        pk__in=invitation_requests, status=RequestStatus.PENDING
    ):
        invitation_request.status = RequestStatus.REJECTED
        invitation_request.reviewed_by = reviewer
        invitation_request.save(update_fields=["status", "reviewed_by", "updated_on"])
        count += 1
    return InvitationRejection(count)


def notify_invitation_request(invitation_request_id: int) -> None:
    """Email active staff users about a new pending request."""

    invitation_request = InvitationRequest.objects.filter(
        pk=invitation_request_id
    ).first()
    if invitation_request is None:
        return
    recipients = list(
        User.objects.filter(is_active=True, is_staff=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not recipients:
        return
    path = reverse(
        "admin:accounts_invitationrequest_change", args=[invitation_request.pk]
    )
    domain = Site.objects.get_current().domain.strip()
    scheme = "http" if domain.startswith(("localhost", "127.0.0.1")) else "https"
    review_url = path if not domain else f"{scheme}://{domain}{path}"
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
            bcc=recipients,
        ).send(fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send invitation request review notification for request %s",
            invitation_request.pk,
        )


def assign_staff_from_invitation(email: str, invitation) -> None:
    """Grant Catalog Administrator staff access after invitation acceptance."""

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        return
    direct_access = InvitationAccess.objects.filter(
        invitation=invitation, invitation__email__iexact=email
    ).first()
    invitation_request = InvitationRequest.objects.filter(
        invitation=invitation,
        email__iexact=email,
        status=RequestStatus.APPROVED,
    ).first()
    access_level = AccessLevel.MEMBER
    if direct_access is not None:
        access_level = direct_access.access_level
    elif invitation_request is not None:
        access_level = invitation_request.access_level
    if access_level == AccessLevel.CATALOG_ADMIN and not user.is_staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
