from datetime import timedelta, time
from io import StringIO
from unittest.mock import Mock

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django_bolt import JSON

from apps.users.admin import IntegrationApiKeyAdmin
from apps.users.api_keys import AuthenticatedAPIKey, authorize_api_key, issue_api_key, rotate_api_key
from apps.users.forms import IntegrationApiKeyAdminForm
from apps.users.models import APIKeyScope, IntegrationApiKey

User = get_user_model()


class IntegrationApiKeyServiceTests(TestCase):
    def test_issue_api_key_stores_only_hash_and_prefix(self):
        api_key, plaintext_key = issue_api_key(
            name="N8N Integration",
            scopes=[APIKeyScope.SCHEDULES_READ, APIKeyScope.SCHEDULES_WRITE],
        )

        self.assertTrue(plaintext_key.startswith(f"{api_key.key_prefix}."))
        self.assertNotEqual(api_key.hashed_key, plaintext_key)
        self.assertEqual(api_key.status, "active")
        self.assertEqual(
            api_key.scopes,
            [
                APIKeyScope.SCHEDULES_READ,
                APIKeyScope.SCHEDULES_WRITE,
            ],
        )

    def test_authorize_api_key_updates_last_used_on(self):
        api_key, plaintext_key = issue_api_key(
            name="Schedule Writer",
            scopes=[APIKeyScope.SCHEDULES_WRITE],
        )

        result = async_to_sync(authorize_api_key)(
            plaintext_key,
            required_scopes=[APIKeyScope.SCHEDULES_WRITE],
        )

        self.assertIsInstance(result, AuthenticatedAPIKey)
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.last_used_on)

    def test_authorize_api_key_rejects_missing_scope(self):
        _api_key, plaintext_key = issue_api_key(
            name="Schedule Reader",
            scopes=[APIKeyScope.SCHEDULES_READ],
        )

        result = async_to_sync(authorize_api_key)(
            plaintext_key,
            required_scopes=[APIKeyScope.SCHEDULES_WRITE],
        )

        self.assertIsInstance(result, JSON)
        self.assertEqual(result.status_code, 403)

    def test_rotate_api_key_revokes_original_and_creates_replacement(self):
        original_key, _plaintext_key = issue_api_key(
            name="Rotating Integration",
            scopes=[APIKeyScope.SONGS_WRITE],
        )

        replacement_key, replacement_plaintext = rotate_api_key(original_key)

        original_key.refresh_from_db()
        self.assertTrue(original_key.is_revoked)
        self.assertEqual(replacement_key.rotated_from, original_key)
        self.assertTrue(replacement_plaintext.startswith(f"{replacement_key.key_prefix}."))


class IntegrationApiKeyAdminTests(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="pass1234",
            first_name="Admin",
            last_name="User",
        )

    def test_admin_add_creates_key_and_shows_plaintext_message(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("admin:users_integrationapikey_add"),
            {
                "name": "Admin Created Key",
                "scopes": [
                    APIKeyScope.SCHEDULES_READ,
                    APIKeyScope.SCHEDULES_WRITE,
                ],
                "expires_on": "",
                "notes": "Used by n8n",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(IntegrationApiKey.objects.count(), 1)
        messages = [str(message) for message in response.context["messages"]]
        self.assertTrue(any("Plaintext API key" in message for message in messages))

    def test_staff_without_permissions_cannot_access_api_key_admin(self):
        staff_user = User.objects.create_user(
            email="staff@example.com",
            password="pass1234",
            first_name="Staff",
            last_name="User",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse("admin:users_integrationapikey_add"))

        self.assertEqual(response.status_code, 403)

    def test_rotate_admin_action_creates_replacement_key(self):
        api_key, _plaintext_key = issue_api_key(
            name="Needs Rotation",
            scopes=[APIKeyScope.SCHEDULES_READ],
            created_by=self.superuser,
        )
        admin_instance = IntegrationApiKeyAdmin(IntegrationApiKey, django_admin.site)
        admin_instance.message_user = Mock()

        request = self.factory.get("/")
        request.user = self.superuser

        response = admin_instance.rotate_selected_key(request, api_key.pk)

        self.assertEqual(response.status_code, 302)
        api_key.refresh_from_db()
        replacement = IntegrationApiKey.objects.exclude(pk=api_key.pk).get()
        self.assertTrue(api_key.is_revoked)
        self.assertEqual(replacement.rotated_from, api_key)
        admin_instance.message_user.assert_called()

    def test_sidebar_navigation_includes_api_keys(self):
        navigation = settings.UNFOLD["SIDEBAR"]["navigation"]
        user_management_section = next(
            section for section in navigation if str(section["title"]) == "User Management"
        )
        item_titles = [str(item["title"]) for item in user_management_section["items"]]
        item_links = [str(item["link"]) for item in user_management_section["items"]]

        self.assertIn("API Keys", item_titles)
        self.assertIn(reverse("admin:users_integrationapikey_changelist"), item_links)


class IntegrationApiKeyAdminFormTests(TestCase):
    def test_form_accepts_single_scope_string_payload(self):
        form = IntegrationApiKeyAdminForm(
            data={
                "name": "Single scope key",
                "scopes": APIKeyScope.SCHEDULES_READ,
                "expires_on": "2026-03-31",
                "notes": "demo",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["scopes"], [APIKeyScope.SCHEDULES_READ])

    def test_form_accepts_comma_separated_scope_payload(self):
        form = IntegrationApiKeyAdminForm(
            data={
                "name": "CSV scope key",
                "scopes": f"{APIKeyScope.SCHEDULES_READ},{APIKeyScope.SONGS_WRITE}",
                "expires_on": "2026-03-31",
                "notes": "demo",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["scopes"],
            [APIKeyScope.SCHEDULES_READ, APIKeyScope.SONGS_WRITE],
        )

    def test_form_stores_date_expiration_at_end_of_day(self):
        form = IntegrationApiKeyAdminForm(
            data={
                "name": "Date expiry key",
                "scopes": [APIKeyScope.SCHEDULES_READ],
                "expires_on": "2026-03-31",
                "notes": "demo",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        api_key = form.save(commit=False)

        self.assertEqual(api_key.expires_on.date().isoformat(), "2026-03-31")
        self.assertEqual(api_key.expires_on.timetz().replace(tzinfo=None), time.max)

    def test_form_rejects_past_expiration_date(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        form = IntegrationApiKeyAdminForm(
            data={
                "name": "Expired key",
                "scopes": [APIKeyScope.SCHEDULES_READ],
                "expires_on": yesterday,
                "notes": "demo",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("expires_on", form.errors)


class AuthenticateApiKeyCommandTests(TestCase):
    def test_command_authenticates_valid_key(self):
        api_key, plaintext_key = issue_api_key(
            name="CLI Key",
            scopes=[APIKeyScope.SCHEDULES_READ, APIKeyScope.SONGS_WRITE],
        )
        stdout = StringIO()

        call_command("authenticate_api_key", plaintext_key, stdout=stdout)

        api_key.refresh_from_db()
        output = stdout.getvalue()
        self.assertIn("API key authenticated.", output)
        self.assertIn("Name: CLI Key", output)
        self.assertIn(f"Prefix: {api_key.key_prefix}", output)
        self.assertIn("Scopes: schedules.read, songs.write", output)
        self.assertIsNotNone(api_key.last_used_on)

    def test_command_rejects_invalid_key(self):
        with self.assertRaises(CommandError) as context:
            call_command(
                "authenticate_api_key",
                "wpp_live_invalid.not-a-real-secret",
                stdout=StringIO(),
            )

        self.assertIn("Invalid API key.", str(context.exception))
