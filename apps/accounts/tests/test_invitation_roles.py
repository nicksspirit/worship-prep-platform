import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from invitations.models import Invitation

from apps.accounts.models import InvitationAccess, InvitationRequest, RequestStatus
from apps.accounts.services import (
    approve_invitation_request,
    assign_staff_from_invitation,
    send_invitation,
)


@pytest.fixture
def invitation_request(db, settings, client):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    response = client.post(
        reverse("request_invitation"),
        {
            "email": "invitee@example.test",
            "first_name": "Invited",
            "last_name": "User",
            "access_level": "catalog_admin",
        },
    )
    assert response.status_code == 200
    return InvitationRequest.objects.get(email="invitee@example.test")


@pytest.fixture
def reviewer(db):
    return get_user_model().objects.create_superuser(
        email="reviewer@example.test", password="Test-password-123"
    )


@pytest.mark.parametrize(
    ("action", "access_level", "is_staff"),
    [
        ("approve_as_member", "member", False),
        ("approve_as_catalog_admin", "catalog_admin", True),
    ],
)
def test_invited_signup_applies_only_the_approved_role(
    client, invitation_request, reviewer, action, access_level, is_staff
):
    client.force_login(reviewer)
    client.post(
        reverse("admin:accounts_invitationrequest_changelist"),
        {"action": action, "_selected_action": [invitation_request.pk]},
    )
    invitation_request.refresh_from_db()
    assert invitation_request.status == RequestStatus.APPROVED
    assert invitation_request.access_level == access_level
    invitation_email = next(
        message for message in mail.outbox if invitation_request.email in message.to
    )
    invite_url = re.search(
        r"https?://\S+/invitations/accept-invite/\w+/?", invitation_email.body
    )
    assert invite_url is not None
    client.logout()
    response = client.get(invite_url[0])
    assert response.status_code == 302
    assert response.url == reverse("account_signup")
    signup = client.get(response.url)
    assert signup.status_code == 200
    assert "Create your account" in signup.content.decode()
    assert "Chapel of Mercy" in signup.content.decode()
    assert "Menu:" not in signup.content.decode()
    assert 'autocomplete="new-password"' in signup.content.decode().lower()
    assert "Continue with Google" in signup.content.decode()

    response = client.post(
        reverse("account_signup"),
        {
            "email": invitation_request.email,
            "password1": "Test-password-123",
            "password2": "Test-password-123",
            "is_staff": "true",
            "is_superuser": "true",
        },
    )

    assert response.status_code == 302
    user = get_user_model().objects.get(email=invitation_request.email)
    assert user.is_staff is is_staff
    assert user.is_superuser is False
    invitation_request.invitation.refresh_from_db()
    assert invitation_request.invitation.accepted is True


def test_approval_defaults_to_member(client, invitation_request, reviewer):
    request = client.get(reverse("account_login")).wsgi_request

    result = approve_invitation_request(
        invitation_request.pk, reviewer=reviewer,
        deliver=lambda invitation: invitation.send_invitation(request),
    )

    assert result.outcome == "sent"
    invitation_request.refresh_from_db()
    assert invitation_request.access_level == "member"


def test_public_request_cannot_choose_staff_access(invitation_request):
    assert invitation_request.status == RequestStatus.PENDING
    assert invitation_request.access_level == "member"
    assert invitation_request.invitation is None


@pytest.mark.parametrize("is_staff", [False, True])
def test_only_superusers_can_approve_invitations(client, invitation_request, is_staff):
    user = get_user_model().objects.create_user(
        "other@example.test", "Test-password-123", is_staff=is_staff
    )
    client.force_login(user)

    client.post(
        reverse("admin:accounts_invitationrequest_changelist"),
        {"action": "approve_as_catalog_admin", "_selected_action": [invitation_request.pk]},
    )

    invitation_request.refresh_from_db()
    assert invitation_request.status == RequestStatus.PENDING
    assert invitation_request.invitation is None


@pytest.mark.django_db
@pytest.mark.parametrize("is_staff", [False, True])
def test_admin_access_requires_staff(client, is_staff):
    user = get_user_model().objects.create_user(
        "user@example.test", "Test-password-123", is_staff=is_staff
    )
    client.force_login(user)

    response = client.get(reverse("admin:index"))

    assert response.status_code == (200 if is_staff else 302)
    if not is_staff:
        assert response.url.startswith(reverse("admin:login"))


@pytest.mark.django_db
def test_member_navigation_has_song_tools_without_admin(client):
    user = get_user_model().objects.create_user(
        "member@example.test", "Test-password-123"
    )
    client.force_login(user)

    response = client.get(reverse("catalog:search"))

    assert response.status_code == 200
    assert reverse("song_carts:list") in response.content.decode()
    assert reverse("song_carts:add_unlisted") in response.content.decode()
    assert f'href="{reverse("admin:index")}"' not in response.content.decode()


@pytest.mark.django_db
def test_member_can_sign_in_and_reach_the_song_catalog(client):
    user = get_user_model().objects.create_user(
        "member@example.test", "Test-password-123"
    )

    response = client.post(
        reverse("account_login"),
        {"login": user.email, "password": "Test-password-123"},
        follow=True,
    )

    assert response.status_code == 200
    assert response.wsgi_request.path == reverse("catalog:search")
    assert client.session["_auth_user_id"] == str(user.pk)
    assert "My submissions" in response.content.decode()
    assert f'href="{reverse("admin:index")}"' not in response.content.decode()


@pytest.mark.parametrize("status", [RequestStatus.PENDING, RequestStatus.REJECTED])
def test_unapproved_request_cannot_grant_staff(invitation_request, status):
    invitation = Invitation.create(email=invitation_request.email)
    invitation_request.invitation = invitation
    invitation_request.access_level = "catalog_admin"
    invitation_request.status = status
    invitation_request.save()
    user = get_user_model().objects.create_user(
        invitation_request.email, "Test-password-123"
    )

    assign_staff_from_invitation(user.email, invitation)

    user.refresh_from_db()
    assert user.is_staff is False


def test_unrelated_invitation_cannot_grant_staff(invitation_request):
    invitation_request.status = RequestStatus.APPROVED
    invitation_request.access_level = "catalog_admin"
    invitation_request.save()
    user = get_user_model().objects.create_user(
        invitation_request.email, "Test-password-123"
    )
    unrelated = Invitation.create(email="unrelated@example.test")

    assign_staff_from_invitation(user.email, unrelated)

    user.refresh_from_db()
    assert user.is_staff is False


@pytest.mark.parametrize(
    ("access_level", "is_staff"), [("member", False), ("catalog_admin", True)]
)
def test_direct_admin_invitation_grants_selected_role_after_signup(
    client, settings, reviewer, access_level, is_staff
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    client.force_login(reviewer)
    email = "direct@example.test"
    response = client.post(
        reverse("admin:invitations_invitation_add"),
        {"email": email, "access_level": access_level, "_save": "Save"},
    )
    assert response.status_code == 302
    invitation = Invitation.objects.get(email=email)
    assert invitation.inviter == reviewer
    assert invitation.access.access_level == access_level
    assert not InvitationRequest.objects.filter(email=email).exists()
    message = next(message for message in mail.outbox if email in message.to)
    invite_url = re.search(r"https?://\S+/invitations/accept-invite/\w+/?", message.body)
    assert invite_url is not None
    client.logout()
    client.get(invite_url[0])

    response = client.post(
        reverse("account_signup"),
        {
            "email": email,
            "password1": "Test-password-123",
            "password2": "Test-password-123",
            "is_staff": "true",
            "is_superuser": "true",
        },
    )

    assert response.status_code == 302
    user = get_user_model().objects.get(email=email)
    assert user.is_staff is is_staff
    assert user.is_superuser is False
    invitation.refresh_from_db()
    assert invitation.accepted is True
    client.logout()
    login = client.post(
        reverse("account_login"),
        {"login": email, "password": "Test-password-123"},
        follow=True,
    )
    assert login.status_code == 200
    assert client.session["_auth_user_id"] == str(user.pk)
    assert (f'href="{reverse("admin:index")}"' in login.content.decode()) is is_staff
    assert client.get(reverse("admin:index")).status_code == (200 if is_staff else 302)
    invitation_list = client.get(reverse("admin:invitations_invitation_changelist"))
    assert invitation_list.status_code == (403 if is_staff else 302)


def test_direct_invitation_form_defaults_to_member(client, reviewer):
    client.force_login(reviewer)

    response = client.get(reverse("admin:invitations_invitation_add"))

    form = response.context["adminform"].form
    assert form.fields["access_level"].initial == "member"
    assert list(form.fields["access_level"].choices) == [
        ("member", "Member"),
        ("catalog_admin", "Catalog Administrator"),
    ]


@pytest.mark.parametrize("access_level", ["superuser", ""])
def test_direct_invitation_rejects_invalid_role(client, reviewer, access_level):
    client.force_login(reviewer)

    response = client.post(
        reverse("admin:invitations_invitation_add"),
        {"email": "direct@example.test", "access_level": access_level},
    )

    assert response.status_code == 200
    assert "access_level" in response.context["adminform"].form.errors
    assert not Invitation.objects.filter(email="direct@example.test").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("is_staff", [False, True])
def test_only_superusers_can_send_direct_invitations(client, is_staff):
    user = get_user_model().objects.create_user(
        "other@example.test", "Test-password-123", is_staff=is_staff
    )
    client.force_login(user)

    response = client.post(
        reverse("admin:invitations_invitation_add"),
        {"email": "direct@example.test", "access_level": "catalog_admin"},
    )

    assert response.status_code == (403 if is_staff else 302)
    assert not Invitation.objects.filter(email="direct@example.test").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("is_staff", [False, True])
def test_direct_invitation_service_enforces_sender_authority(client, is_staff):
    user = get_user_model().objects.create_user(
        "other@example.test", "Test-password-123", is_staff=is_staff
    )
    request = client.get(reverse("account_login")).wsgi_request

    with pytest.raises(PermissionDenied):
        send_invitation(
            "direct@example.test", inviter=user,
            deliver=lambda invitation: invitation.send_invitation(request),
            access_level="catalog_admin",
        )

    assert not Invitation.objects.filter(email="direct@example.test").exists()


def test_direct_invitation_send_failure_rolls_back_role_and_invitation(
    client, reviewer, monkeypatch
):
    def fail_send(*args, **kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(Invitation, "send_invitation", fail_send)
    request = client.get(reverse("account_login")).wsgi_request

    with pytest.raises(OSError, match="SMTP unavailable"):
        send_invitation(
            "direct@example.test", inviter=reviewer,
            deliver=lambda invitation: invitation.send_invitation(request),
        )

    assert not Invitation.objects.filter(email="direct@example.test").exists()
    assert not InvitationAccess.objects.exists()


def test_direct_admin_invitation_cannot_grant_another_email_staff(reviewer):
    invitation = Invitation.create(email="direct@example.test", inviter=reviewer)
    InvitationAccess.objects.create(invitation=invitation, access_level="catalog_admin")
    user = get_user_model().objects.create_user(
        "other@example.test", "Test-password-123"
    )

    assign_staff_from_invitation(user.email, invitation)

    user.refresh_from_db()
    assert user.is_staff is False
