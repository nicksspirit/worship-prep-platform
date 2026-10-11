import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.api_keys.models import APIKeyScope, IntegrationApiKey
from apps.api_keys.services import IssueApiKey, authorize_api_key, issue_api_key


class IntegrationApiKeyAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            email="superuser@example.com",
            password="pass1234",
            first_name="Super",
            last_name="User",
        )
        self.client.force_login(self.user)

    def test_add_issues_one_usable_key_and_displays_its_secret(self):
        response = self.client.post(
            reverse("admin:api_keys_integrationapikey_add"),
            {
                "name": "EasyWorship Windows Exporter",
                "scopes": [APIKeyScope.CATALOG_IMPORT],
                "expires_on": "",
                "notes": "Windows catalog imports",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        api_key = IntegrationApiKey.objects.get()
        self.assertEqual(api_key.created_by, self.user)
        self.assertIsNotNone(api_key.created_on)
        self.assertEqual(api_key.notes, "Windows catalog imports")
        plaintext = re.search(r"<code>([^<]+)</code>", response.content.decode())
        self.assertIsNotNone(plaintext)
        authorization = authorize_api_key(
            f"Bearer {plaintext.group(1)}", required_scopes=[APIKeyScope.CATALOG_IMPORT]
        )
        self.assertEqual(authorization.api_key, api_key)

    def test_edit_preserves_issued_credentials(self):
        issued = issue_api_key(
            IssueApiKey(
                name="Exporter",
                scopes=[APIKeyScope.CATALOG_IMPORT],
                created_by=self.user,
            )
        )
        created_on = issued.api_key.created_on

        response = self.client.post(
            reverse(
                "admin:api_keys_integrationapikey_change", args=[issued.api_key.pk]
            ),
            {
                "name": "Renamed exporter",
                "scopes": [APIKeyScope.CATALOG_IMPORT],
                "expires_on": "",
                "notes": "Updated notes",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        issued.api_key.refresh_from_db()
        self.assertEqual(issued.api_key.name, "Renamed exporter")
        self.assertEqual(issued.api_key.notes, "Updated notes")
        self.assertEqual(issued.api_key.created_on, created_on)
        self.assertEqual(issued.api_key.created_by, self.user)
        authorization = authorize_api_key(
            f"Bearer {issued.plaintext_key}", required_scopes=[APIKeyScope.CATALOG_IMPORT]
        )
        self.assertEqual(authorization.api_key, issued.api_key)
