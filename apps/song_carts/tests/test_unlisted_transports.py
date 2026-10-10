from datetime import date

from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.song_carts.models import CartStatus, SongCartItem
from apps.song_carts.presentation import present_unlisted_song
from apps.song_carts.services import (
    UnlistedSongInput, get_unlisted_song, save_unlisted_song,
)


class UnlistedTransportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner@example.test", "Test-password-123")
        cls.other = User.objects.create_user("other@example.test", "Test-password-123")
        cls.song = save_unlisted_song(UnlistedSongInput(
            date(2026, 11, 8), "worship", "Unlisted title", "[Verse 1]\nOriginal words",
        ), user=cls.owner)

    def setUp(self):
        self.client.force_login(self.owner)
        self.detail = reverse("song_carts:unlisted_detail", args=[
            self.song.cart_id, self.song.id,
        ])
        self.review = reverse("song_carts:review_unlisted", args=[
            self.song.cart_id, self.song.id,
        ])
        self.data = {
            "title": self.song.title, "lyrics": self.song.lyrics,
            "section": self.song.section, "service_date": "2026-11-08",
        }

    def test_new_song_redirects_to_saved_preview_without_reviewing_it(self):
        response = self.client.post(reverse("song_carts:add_unlisted"), {
            **self.data, "title": "Another song",
        })

        saved = SongCartItem.objects.get(title="Another song")
        self.assertRedirects(response, reverse("song_carts:unlisted_detail", args=[
            saved.cart_id, saved.id,
        ]), fetch_redirect_response=False)
        self.assertIsNone(saved.reviewed_at)
        self.assertEqual(self.client.session["song_cart_service_date"], "2026-11-08")

    def test_get_shows_saved_preview_without_changing_review(self):
        response = self.client.get(self.detail)

        self.assertContains(response, "Mark lyrics reviewed")
        self.assertContains(response, "Original words")
        self.assertIsNone(SongCartItem.objects.get(pk=self.song.id).reviewed_at)

    def test_valid_review_returns_to_the_cart(self):
        response = self.client.post(self.review, {"fingerprint": self.song.fingerprint})

        self.assertRedirects(response, reverse("song_carts:detail", args=[
            self.song.cart_id,
        ]), fetch_redirect_response=False)
        self.assertIsNotNone(SongCartItem.objects.get(pk=self.song.id).reviewed_at)

    def test_stale_review_shows_the_latest_saved_preview(self):
        save_unlisted_song(UnlistedSongInput(
            date(2026, 11, 8), "worship", self.song.title, "Updated words", self.song.id,
        ), user=self.owner)

        response = self.client.post(self.review, {"fingerprint": self.song.fingerprint})

        self.assertContains(response, "out of date", status_code=400)
        self.assertContains(response, "Updated words", status_code=400)
        self.assertIsNone(SongCartItem.objects.get(pk=self.song.id).reviewed_at)

    def test_invalid_save_retains_input_and_hides_the_old_preview(self):
        response = self.client.post(self.detail, {**self.data, "lyrics": "[Chorus]"})

        self.assertContains(response, "[Chorus]", status_code=400)
        self.assertNotContains(response, "Mark lyrics reviewed", status_code=400)
        self.assertEqual(SongCartItem.objects.get(pk=self.song.id).original_lyrics,
                         self.song.lyrics)

    def test_another_owner_cannot_read_save_or_review(self):
        self.client.force_login(self.other)

        for method, url, data in [
            (self.client.get, self.detail, {}),
            (self.client.post, self.detail, self.data),
            (self.client.post, self.review, {"fingerprint": self.song.fingerprint}),
        ]:
            with self.subTest(url=url, method=method.__name__):
                self.assertEqual(method(url, data).status_code, 404)

    def test_save_and_review_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)

        for url in [reverse("song_carts:add_unlisted"), self.detail, self.review]:
            with self.subTest(url=url):
                self.assertEqual(client.post(url, self.data).status_code, 403)

    def test_submitted_song_is_readonly_and_rejects_saving(self):
        item = SongCartItem.objects.select_related("cart").get(pk=self.song.id)
        item.cart.status = CartStatus.PENDING
        item.cart.save(update_fields=["status"])

        response = self.client.post(self.detail, {**self.data, "title": "Forged change"})

        self.assertContains(response, "Unlisted title", status_code=400)
        self.assertNotContains(response, "Save and preview", status_code=400)
        self.assertEqual(SongCartItem.objects.get(pk=self.song.id).title, self.song.title)

    def test_bound_changes_cannot_expose_a_stale_review_fingerprint(self):
        song = get_unlisted_song(self.song.cart_id, self.song.id, user=self.owner)

        page = present_unlisted_song(
            song, song_title=song.title, lyrics="Changed unsaved words",
            service_date=song.service_date.isoformat(), section=song.section,
        )

        self.assertEqual(page.slides, [])
        self.assertEqual(page.fingerprint, "")
        self.assertIsNone(page.review_url)

    def test_invalid_date_can_be_corrected_without_moving_the_saved_song(self):
        song = get_unlisted_song(self.song.cart_id, self.song.id, user=self.owner)

        page = present_unlisted_song(
            song, song_title=song.title, lyrics=song.lyrics,
            service_date="invalid", section=song.section,
        )

        self.assertEqual(page.service_date, "2026-11-08")
        self.assertEqual(page.slides, [])

    def test_staff_can_read_prepared_and_original_lyrics_in_admin(self):
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])

        response = self.client.get(reverse("admin:song_carts_songcart_change", args=[
            self.song.cart_id,
        ]))

        self.assertContains(response, "Prepared lyrics")
        self.assertContains(response, "Original pasted lyrics")
        self.assertContains(response, "Original words")
        self.assertContains(response, f"#{self.song.id}")
        self.assertEqual(SongCartItem.objects.get(pk=self.song.id).cart.status,
                         CartStatus.DRAFT)
