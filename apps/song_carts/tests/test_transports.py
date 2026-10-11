import re
from datetime import date
from uuid import uuid4

from django.contrib.auth.models import Group
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.song_carts.models import (
    CartComment, CartStatus, SongCart, SongCartItem, SubmissionEmail,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SubmissionTransportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner@example.test", "Test-password-123")
        cls.other = User.objects.create_user("other@example.test", "Test-password-123")
        cls.staff = User.objects.create_user(
            "staff@example.test", "Test-password-123", is_staff=True,
        )
        cls.team = User.objects.create_user(
            "team@example.test", "Test-password-123", is_staff=True,
        )
        cls.team.groups.add(Group.objects.create(name="Technical Team"))
        cls.cart = SongCart.objects.create(
            owner=cls.owner, service_date=date(2026, 10, 25), status=CartStatus.PENDING,
        )
        SongCartItem.objects.create(
            cart=cls.cart, section="praise", song_uid="fixture-song",
            title="Fixture Song",
        )

    def test_cart_link_from_submissions_opens_an_empty_cart_without_creating_a_draft(self):
        self.client.force_login(self.owner)
        submissions = self.client.get(reverse("song_carts:list"))
        cart_link = re.search(
            r'<a href="([^"]+)" aria-label="Your song cart, 0 songs"',
            submissions.content.decode(),
        )
        self.assertIsNotNone(cart_link)

        response = self.client.get(cart_link[1])

        self.assertContains(response, "Your song cart is empty.")
        self.assertContains(response, reverse("catalog:search"))
        self.assertContains(response, reverse("song_carts:add_unlisted"))
        self.assertEqual(SongCart.objects.filter(owner=self.owner).count(), 1)

    def test_cart_link_from_submissions_still_opens_the_saved_draft(self):
        draft = SongCart.objects.create(
            owner=self.owner, service_date=date(2026, 11, 1),
        )
        SongCartItem.objects.create(
            cart=draft, section="praise", song_uid="fixture-song", title="Draft Song",
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("song_carts:list"))

        self.assertContains(
            response,
            f'href="{reverse("song_carts:detail", args=[draft.id])}" '
            'aria-label="Your song cart, 1 song"',
        )

    def test_empty_cart_requires_sign_in(self):
        response = self.client.get(reverse("song_carts:empty"))

        self.assertRedirects(
            response, "/accounts/login/?next=/song-carts/empty/",
            fetch_redirect_response=False,
        )

    def test_admin_detail_get_does_not_acknowledge_the_submission(self):
        self.client.force_login(self.team)

        response = self.client.get(
            reverse("admin:song_carts_songcart_change", args=[self.cart.id]),
        )

        self.assertContains(response, "data-auto-confirm")
        self.assertContains(response, "Song reference")
        self.assertContains(response, f"#{self.cart.songs.get().pk}")
        self.assertEqual(SongCart.objects.get(pk=self.cart.id).status, CartStatus.PENDING)
        self.assertEqual(len(mail.outbox), 0)

    def test_confirmation_post_records_one_acknowledgement_email(self):
        self.client.force_login(self.team)
        url = reverse("admin:song_carts_songcart_confirm", args=[self.cart.id])

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url)
            repeated = self.client.post(url)

        self.assertEqual((response.status_code, repeated.status_code), (204, 204))
        self.assertEqual(
            SongCart.objects.get(pk=self.cart.id).status, CartStatus.CONFIRMED,
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_confirmation_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.team)

        response = client.post(
            reverse("admin:song_carts_songcart_confirm", args=[self.cart.id]),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(SongCart.objects.get(pk=self.cart.id).status, CartStatus.PENDING)

    def test_general_staff_cannot_confirm(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("admin:song_carts_songcart_confirm", args=[self.cart.id]),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(SongCart.objects.get(pk=self.cart.id).status, CartStatus.PENDING)

    def test_comment_create_is_owner_scoped(self):
        self.client.force_login(self.other)

        response = self.client.post(
            reverse("song_carts:add_comment", args=[self.cart.id]), {"body": "Wrong owner"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(CartComment.objects.exists())

    def test_comment_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)

        response = client.post(
            reverse("song_carts:add_comment", args=[self.cart.id]), {"body": "Request"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(CartComment.objects.exists())

    def test_invalid_comment_keeps_typed_content_for_correction(self):
        self.client.force_login(self.owner)
        body = "x" * 5001

        response = self.client.post(
            reverse("song_carts:add_comment", args=[self.cart.id]), {"body": body},
        )

        self.assertContains(response, body, status_code=400)
        self.assertFalse(CartComment.objects.exists())

    def test_owner_page_does_not_serialize_internal_email_errors(self):
        SubmissionEmail.objects.create(
            cart=self.cart, kind="receipt", status="failed",
            error="internal-mail-host-secret",
            recipients=[self.owner.email], subject="Receipt", body="Saved receipt",
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("song_carts:detail", args=[self.cart.id]))

        self.assertContains(response, "Email could not be sent")
        self.assertNotContains(response, "internal-mail-host-secret")

    def test_manual_reply_does_not_create_a_comment(self):
        self.client.force_login(self.team)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("admin:song_carts_songcart_reply", args=[self.cart.id]),
                {"body": "We have your request.", "request_id": str(uuid4())},
            )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(CartComment.objects.exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_nonstaff_landing_is_song_search(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("after_sign_in"))

        self.assertRedirects(
            response, reverse("catalog:search"), fetch_redirect_response=False,
        )

    def test_staff_landing_is_submission_overview(self):
        self.client.force_login(self.team)

        response = self.client.get(reverse("after_sign_in"))

        self.assertRedirects(
            response, reverse("admin:index"), fetch_redirect_response=False,
        )
