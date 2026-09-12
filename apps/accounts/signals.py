"""Signal handlers that translate invitation framework events into use cases."""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from invitations.signals import invite_accepted

from apps.accounts.models import InvitationRequest, RequestStatus
from apps.accounts.services import assign_staff_from_invitation, notify_invitation_request


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
        lambda invitation_request_id=instance.pk: notify_invitation_request(
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
    assign_staff_from_invitation(email, invitation)
