from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.api_keys.forms import IntegrationApiKeyAdminForm
from apps.api_keys.models import APIKeyScope, IntegrationApiKey
from apps.api_keys.services import issue_api_key, rotate_api_key


class IntegrationApiKeyFoundationTests(TestCase):
    def test_issue_stores_only_hash_prefix_and_catalog_scopes(self):
        api_key, plaintext_key = issue_api_key(
            name="Catalog Importer",
            scopes=[APIKeyScope.CATALOG_IMPORT],
        )

        self.assertTrue(plaintext_key.startswith(f"{api_key.key_prefix}."))
        self.assertNotEqual(api_key.hashed_key, plaintext_key)
        self.assertEqual(api_key.scopes, [APIKeyScope.CATALOG_IMPORT])

    def test_rotation_revokes_original_and_returns_one_replacement_secret(self):
        original, _ = issue_api_key(
            name="Catalog Reader",
            scopes=[APIKeyScope.CATALOG_SEARCH, APIKeyScope.SONG_READ],
        )

        replacement, plaintext_key = rotate_api_key(original)

        original.refresh_from_db()
        self.assertTrue(original.is_revoked)
        self.assertEqual(replacement.rotated_from, original)
        self.assertTrue(plaintext_key.startswith(f"{replacement.key_prefix}."))

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
