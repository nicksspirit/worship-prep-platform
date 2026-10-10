import io
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, Group
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import CatalogEntry
from apps.catalog.services import CatalogReadError, import_package
from apps.song_carts.models import (
    CartStatus,
    NotificationStatus, SubmissionEmail,
    ServiceSection,
    SongCart,
)
from apps.song_carts.services import (
    AddCartSong, add_cart_song, checkout_cart, get_cart, list_carts, notify_cart,
    remove_cart_song,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SongCartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixture = Path(settings.BASE_DIR) / "contracts/catalog-import/v1/fixtures/valid"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as package:
            for filename in ("manifest.json", "songs.ndjson"):
                package.writestr(filename, (fixture / filename).read_bytes())
        import_package(buffer.getvalue())
        cls.owner = User.objects.create_user("choir@example.test", "Test-password-123")
        cls.other = User.objects.create_user("other@example.test", "Test-password-123")
        cls.admin = User.objects.create_superuser(
            "admin@example.test", "Test-password-123"
        )
        cls.admin.groups.add(Group.objects.create(name="Technical Team"))
        cls.song_uid = CatalogEntry.objects.get().song_uid
        cls.service_date = date(2026, 10, 14)

    def add_song(self, *, section=ServiceSection.CALL_TO_WORSHIP):
        return add_cart_song(
            AddCartSong(self.service_date, section, self.song_uid), user=self.owner
        )

    def test_adds_catalog_song_to_a_weekday_cart(self):
        cart_id = self.add_song()

        cart = get_cart(cart_id, user=self.owner)
        self.assertEqual(cart.service_date, self.service_date)
        self.assertEqual(cart.status, CartStatus.DRAFT)
        self.assertEqual(cart.songs[0].song_uid, self.song_uid)
        self.assertEqual(cart.songs[0].section, ServiceSection.CALL_TO_WORSHIP)

    def test_repeated_add_keeps_one_song_in_the_section(self):
        self.add_song()

        cart_id = self.add_song()

        self.assertEqual(len(get_cart(cart_id, user=self.owner).songs), 1)

    def test_allows_the_same_song_in_different_service_sections(self):
        self.add_song()

        cart_id = self.add_song(section=ServiceSection.PRAISE)

        self.assertEqual(len(get_cart(cart_id, user=self.owner).songs), 2)

    def test_rejects_unknown_service_sections(self):
        with self.assertRaises(ValidationError):
            self.add_song(section="other")

        self.assertFalse(SongCart.objects.exists())

    def test_rejects_songs_missing_from_the_catalog(self):
        with self.assertRaises(CatalogReadError):
            add_cart_song(
                AddCartSong(self.service_date, ServiceSection.CALL_TO_WORSHIP, "missing"),
                user=self.owner,
            )

        self.assertFalse(SongCart.objects.exists())

    def test_anonymous_users_cannot_create_carts(self):
        with self.assertRaises(PermissionDenied):
            add_cart_song(
                AddCartSong(
                    self.service_date, ServiceSection.CALL_TO_WORSHIP, self.song_uid
                ),
                user=AnonymousUser(),
            )

    def test_users_cannot_read_another_users_cart(self):
        cart_id = self.add_song()

        with self.assertRaises(SongCart.DoesNotExist):
            get_cart(cart_id, user=self.other)

    def test_lists_only_the_users_own_carts(self):
        self.add_song()

        carts = list_carts(user=self.other)

        self.assertEqual(carts, [])

    def test_users_cannot_checkout_another_users_cart(self):
        cart_id = self.add_song()

        with self.assertRaises(SongCart.DoesNotExist):
            checkout_cart(cart_id, user=self.other)

        self.assertEqual(SongCart.objects.get(pk=cart_id).status, CartStatus.DRAFT)

    def test_users_cannot_remove_songs_from_another_users_cart(self):
        cart_id = self.add_song()
        song_id = get_cart(cart_id, user=self.owner).songs[0].id

        with self.assertRaises(SongCart.DoesNotExist):
            remove_cart_song(cart_id, song_id, user=self.other)

        self.assertEqual(len(get_cart(cart_id, user=self.owner).songs), 1)

    def test_removes_a_song_from_a_draft(self):
        cart_id = self.add_song()
        song_id = get_cart(cart_id, user=self.owner).songs[0].id

        remove_cart_song(cart_id, song_id, user=self.owner)

        self.assertEqual(get_cart(cart_id, user=self.owner).songs, ())

    def test_empty_carts_cannot_be_checked_out(self):
        cart = SongCart.objects.create(owner=self.owner, service_date=self.service_date)

        with self.assertRaisesMessage(ValidationError, "Add at least one song"):
            checkout_cart(cart.id, user=self.owner)

        cart.refresh_from_db()
        self.assertEqual(cart.status, CartStatus.DRAFT)

    def test_checkout_saves_pending_submission_and_sends_distinct_emails(self):
        cart_id = self.add_song()

        with self.captureOnCommitCallbacks(execute=True):
            checkout_cart(cart_id, user=self.owner)

        cart = SongCart.objects.get(pk=cart_id)
        self.assertEqual(cart.status, CartStatus.PENDING)
        self.assertIsNotNone(cart.submitted_at)
        self.assertIsNone(cart.confirmed_at)
        self.assertEqual(cart.notification_status, NotificationStatus.SENT)
        self.assertEqual(len(mail.outbox), 2)
        message = mail.outbox[1]
        self.assertEqual(message.bcc, [self.admin.email])
        self.assertIn("Wednesday, October 14, 2026", message.body)
        self.assertIn("Call to Worship", message.body)
        self.assertIn("Praise", message.body)
        self.assertIn("Worship", message.body)
        self.assertIn(get_cart(cart_id, user=self.owner).songs[0].title, message.body)
        self.assertNotIn(CatalogEntry.objects.get().cleaned_lyrics, message.body)

    def test_repeated_checkout_does_not_send_another_notification(self):
        cart_id = self.add_song()
        with self.captureOnCommitCallbacks(execute=True):
            checkout_cart(cart_id, user=self.owner)
        submitted_at = SongCart.objects.get(pk=cart_id).submitted_at

        with self.captureOnCommitCallbacks(execute=True):
            checkout_cart(cart_id, user=self.owner)

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(SongCart.objects.get(pk=cart_id).submitted_at, submitted_at)

    def test_failed_email_preserves_the_pending_submission(self):
        cart_id = self.add_song()
        with patch(
            "apps.song_carts.services.emails.EmailMessage.send",
            side_effect=OSError("SMTP unavailable"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                checkout_cart(cart_id, user=self.owner)
        cart = SongCart.objects.get(pk=cart_id)
        self.assertEqual(cart.status, CartStatus.PENDING)
        self.assertEqual(cart.notification_status, NotificationStatus.FAILED)

    def test_admin_can_retry_a_failed_notification(self):
        cart_id = self.add_song()
        checkout_cart(cart_id, user=self.owner)
        SubmissionEmail.objects.filter(cart_id=cart_id).update(
            status=NotificationStatus.FAILED, error="SMTP unavailable",
        )

        notify_cart(cart_id, user=self.admin)

        cart = SongCart.objects.get(pk=cart_id)
        cart.refresh_from_db()
        self.assertEqual(cart.notification_status, NotificationStatus.SENT)
        self.assertEqual(cart.notification_error, "")
        self.assertEqual(len(mail.outbox), 2)

    def test_other_users_cannot_send_cart_notifications(self):
        cart_id = self.add_song()
        checkout_cart(cart_id, user=self.owner)

        with self.assertRaises(PermissionDenied):
            notify_cart(cart_id, user=self.other)

    def test_transaction_rollback_does_not_send_a_notification(self):
        cart_id = self.add_song()

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError):
                with transaction.atomic():
                    checkout_cart(cart_id, user=self.owner)
                    raise ValueError("rollback")

        self.assertEqual(SongCart.objects.get(pk=cart_id).status, CartStatus.DRAFT)
        self.assertEqual(len(mail.outbox), 0)

    def test_submitted_carts_cannot_have_songs_added(self):
        cart_id = self.add_song()
        checkout_cart(cart_id, user=self.owner)

        with self.assertRaises(ValidationError):
            self.add_song(section=ServiceSection.PRAISE)

    def test_submitted_carts_cannot_have_songs_removed(self):
        cart_id = self.add_song()
        song_id = get_cart(cart_id, user=self.owner).songs[0].id
        checkout_cart(cart_id, user=self.owner)

        with self.assertRaises(ValidationError):
            remove_cart_song(cart_id, song_id, user=self.owner)

    def test_cart_metadata_survives_catalog_entry_removal(self):
        cart_id = self.add_song()
        song = get_cart(cart_id, user=self.owner).songs[0]

        CatalogEntry.objects.all().delete()

        self.assertEqual(get_cart(cart_id, user=self.owner).songs[0], song)

    def test_new_tables_have_row_level_security_enabled(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relname, relrowsecurity FROM pg_class "
                "WHERE relname IN ('song_carts_songcart', 'song_carts_songcartitem')"
            )
            protected = dict(cursor.fetchall())

        self.assertEqual(protected, {
            "song_carts_songcart": True, "song_carts_songcartitem": True,
        })

    def test_cart_pages_require_sign_in(self):
        response = self.client.get(reverse("song_carts:list"))

        self.assertRedirects(
            response, "/accounts/login/?next=/song-carts/",
            fetch_redirect_response=False,
        )

    def test_checkout_rejects_get_requests(self):
        cart_id = self.add_song()
        self.client.force_login(self.owner)

        response = self.client.get(reverse("song_carts:checkout", args=[cart_id]))

        self.assertEqual(response.status_code, 405)
        self.assertEqual(SongCart.objects.get(pk=cart_id).status, CartStatus.DRAFT)

    def test_checkout_requires_a_csrf_token(self):
        cart_id = self.add_song()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        url = reverse("song_carts:checkout", args=[cart_id])

        response = client.post(url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(SongCart.objects.get(pk=cart_id).status, CartStatus.DRAFT)

    def test_invalid_add_date_is_rendered_without_creating_a_cart(self):
        self.client.force_login(self.owner)

        response = self.client.post(reverse("song_carts:add", args=[self.song_uid]), {
            "service_date": "invalid", "section": ServiceSection.CALL_TO_WORSHIP,
        })

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Enter a valid date", status_code=400)
        self.assertFalse(SongCart.objects.exists())

    def test_cart_page_shows_three_predefined_sections(self):
        cart_id = self.add_song()
        self.client.force_login(self.owner)

        response = self.client.get(reverse("song_carts:detail", args=[cart_id]))

        self.assertContains(response, "Call to Worship")
        self.assertContains(response, "Praise")
        self.assertContains(response, "Worship")
        self.assertContains(response, "Submit")

    def test_staff_without_model_permissions_can_review_the_selected_songs(self):
        cart_id = self.add_song()
        staff = User.objects.create_user(
            "staff@example.test", "Test-password-123", is_staff=True
        )
        self.client.force_login(staff)

        response = self.client.get(
            reverse("admin:song_carts_songcart_change", args=[cart_id])
        )

        self.assertContains(response, get_cart(cart_id, user=self.owner).songs[0].title)
        self.assertContains(response, "Call to Worship")

    def test_team_member_can_retry_emails_from_admin_details(self):
        cart_id = self.add_song()
        checkout_cart(cart_id, user=self.owner)
        staff = User.objects.create_user(
            "staff@example.test", "Test-password-123", is_staff=True
        )
        staff.groups.add(Group.objects.get(name="Technical Team"))
        self.client.force_login(staff)

        response = self.client.post(reverse(
            "admin:song_carts_songcart_retry_emails", args=[cart_id],
        ))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            SongCart.objects.get(pk=cart_id).notification_status, NotificationStatus.SENT
        )

    def test_admin_home_opens_submission_overview(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "Song submissions")
        self.assertContains(response, "Total submitted")
