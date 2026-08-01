from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import InvitationRequest


class AccountFoundationTests(TestCase):
    def test_sign_in_page_uses_reactivated_presentation(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign In")
        self.assertContains(response, reverse("request_invitation"))

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
