from contextlib import redirect_stdout
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from allauth.socialaccount.models import SocialAccount, SocialToken

from apps.accounts.models import InvitationRequest


class AccountFoundationTests(TestCase):
    def test_createsuperuser_exposes_identity_and_interactive_password_inputs(self):
        output = StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit):
            call_command("createsuperuser", "--help")

        help_text = output.getvalue()
        self.assertIn("--email EMAIL", help_text)
        self.assertIn("--first_name FIRST_NAME", help_text)
        self.assertIn("--last_name LAST_NAME", help_text)
        self.assertIn("--noinput", help_text)
        self.assertNotIn("--password", help_text)

    def test_sign_in_page_uses_reactivated_presentation(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign In")
        self.assertContains(response, reverse("request_invitation"))

    def test_closed_signup_explains_invitation_only_access(self):
        response = self.client.get(reverse("account_signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You need an invitation to join.")
        self.assertContains(response, reverse("request_invitation"))
        self.assertContains(response, reverse("account_login"))
        self.assertNotContains(response, 'href="/accounts/signup/"')

    def test_invitation_request_is_persisted_for_review(self):
        response = self.client.post(
            reverse("request_invitation"),
            {
                "email": "catalog.admin@example.com",
                "first_name": "Catalog",
                "last_name": "Admin",
                "message": "Please invite me.",
            },
        )

        self.assertEqual(response.status_code, 200)
        request = InvitationRequest.objects.get()
        self.assertEqual(request.email, "catalog.admin@example.com")
        self.assertContains(response, "Thank you")

    def test_unfold_admin_boots_with_greenfield_navigation(self):
        user = get_user_model().objects.create_superuser(
            email="superuser@example.com",
            password="pass1234",
            first_name="Super",
            last_name="User",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        navigation = settings.UNFOLD["SIDEBAR"]["navigation"]
        links = [
            str(item["link"])
            for section in navigation
            for item in section["items"]
        ]
        self.assertIn(reverse("admin:accounts_user_changelist"), links)
        self.assertIn(reverse("admin:accounts_invitationrequest_changelist"), links)
        self.assertIn(reverse("admin:api_keys_integrationapikey_changelist"), links)
        self.assertFalse(any("schedule" in link or "songs" in link for link in links))


class GoogleIdentityLinkCommandTests(TestCase):
    def test_superuser_creation_normalizes_email_and_sets_administrative_flags(self):
        user = get_user_model().objects.create_superuser(
            email="New.User@Example.COM ",
            password="pass1234",
            first_name="Target",
            last_name="User",
        )

        self.assertEqual(user.email, "new.user@example.com")
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            email="Target.User@Example.com",
            password="pass1234",
            first_name="Target",
            last_name="User",
        )

    def test_creates_empty_google_identity_without_a_social_token(self):
        call_command(
            "link_google_identity",
            email="target.user@example.com",
            uid="google-subject-123",
        )

        account = SocialAccount.objects.get(provider="google", uid="google-subject-123")
        self.assertEqual(account.user, self.user)
        self.assertEqual(account.extra_data, {})
        self.assertFalse(SocialToken.objects.filter(account=account).exists())

    def test_rejects_google_uid_already_linked_to_another_user(self):
        other_user = get_user_model().objects.create_user(
            email="other@example.com",
            password="pass1234",
        )
        existing = SocialAccount.objects.create(
            user=other_user,
            provider="google",
            uid="google-subject-123",
            extra_data={},
        )

        with self.assertRaisesRegex(CommandError, "already linked to another user"):
            call_command(
                "link_google_identity",
                email=self.user.email,
                uid=existing.uid,
            )

        existing.refresh_from_db()
        self.assertEqual(existing.user, other_user)
        self.assertEqual(SocialAccount.objects.filter(uid=existing.uid).count(), 1)

    def test_reuses_the_correct_existing_google_identity(self):
        SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="google-subject-123",
            extra_data={},
        )

        call_command(
            "link_google_identity",
            email=self.user.email,
            uid="google-subject-123",
        )

        self.assertEqual(
            SocialAccount.objects.filter(
                user=self.user, provider="google", uid="google-subject-123"
            ).count(),
            1,
        )
