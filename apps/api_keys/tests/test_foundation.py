from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.api_keys.forms import IntegrationApiKeyAdminForm
from apps.api_keys.models import APIKeyScope, IntegrationApiKey
from apps.api_keys.services import (
    AuthorizationDenied,
    IssueApiKey,
    authorize_api_key,
    issue_api_key,
    rotate_api_key,
)


class IntegrationApiKeyFoundationTests(TestCase):
    def test_issue_stores_only_hash_prefix_and_catalog_scopes(self):
        issued = issue_api_key(
            IssueApiKey(
                name="Catalog Importer",
                scopes=[APIKeyScope.CATALOG_IMPORT],
            )
        )

        self.assertTrue(issued.plaintext_key.startswith(f"{issued.api_key.key_prefix}."))
        self.assertNotEqual(issued.api_key.hashed_key, issued.plaintext_key)
        self.assertEqual(issued.api_key.scopes, [APIKeyScope.CATALOG_IMPORT])

    def test_authorization_denial_has_no_http_status(self):
        result = authorize_api_key("", required_scopes=[APIKeyScope.CATALOG_SEARCH])

        self.assertIsInstance(result, AuthorizationDenied)
        self.assertEqual(result.code, "invalid_api_key")
        self.assertFalse(hasattr(result, "status_code"))

    def test_rotation_revokes_original_and_returns_one_replacement_secret(self):
        original = issue_api_key(
            IssueApiKey(
                name="Catalog Reader",
                scopes=[APIKeyScope.CATALOG_SEARCH, APIKeyScope.SONG_READ],
            )
        )

        replacement = rotate_api_key(original.api_key)

        original.api_key.refresh_from_db()
        self.assertTrue(original.api_key.is_revoked)
        self.assertEqual(replacement.api_key.rotated_from, original.api_key)
        self.assertTrue(
            replacement.plaintext_key.startswith(f"{replacement.api_key.key_prefix}.")
        )

    def test_admin_form_accepts_target_scope(self):
        form = IntegrationApiKeyAdminForm(
            data={
                "name": "Catalog Search",
                "scopes": APIKeyScope.CATALOG_SEARCH,
                "expires_on": (timezone.localdate() + timedelta(days=30)).isoformat(),
                "notes": "Read-only client",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["scopes"], [APIKeyScope.CATALOG_SEARCH])

    def test_superuser_can_open_api_key_admin(self):
        user = get_user_model().objects.create_superuser(
            email="superuser@example.com",
            password="pass1234",
            first_name="Super",
            last_name="User",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:api_keys_integrationapikey_add"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(IntegrationApiKey.objects.count(), 0)
