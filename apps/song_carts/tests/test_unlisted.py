from dataclasses import replace
from datetime import date, timedelta

from django.contrib.auth.models import AnonymousUser, Group
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings

from apps.accounts.models import User
from apps.song_carts.models import CartStatus, ServiceSection, SongCart, SongCartItem
from apps.song_carts.services import (
    UnlistedSongInput, checkout_cart, get_cart, get_unlisted_song, prepare_lyrics,
    review_unlisted_song, save_unlisted_song,
)


class PrepareLyricsTests(SimpleTestCase):
    def test_recognizes_explicit_and_plain_labels_in_source_order(self):
        sections = prepare_lyrics(
            "[Verse1]\nFirst line\nChorus\nSing again\n[Bridge]\nFinal line",
        )

        self.assertEqual([section.label for section in sections], [
            "Verse1", "Chorus", "Bridge",
        ])
        self.assertEqual([section.position for section in sections], [1, 2, 3])
        self.assertEqual(sections[0].slides, (("First line",),))

    def test_keeps_paragraph_boundaries_and_repeated_lyrics(self):
        sections = prepare_lyrics("One line\n\nOne line\nSing this (x2)\n\nAmen")

        self.assertEqual(sections[0].label, "")
        self.assertEqual(sections[0].slides, (
            ("One line",), ("One line", "Sing this (x2)"), ("Amen",),
        ))

    def test_wraps_without_losing_unicode_words_or_splitting_hyphenated_words(self):
        hyphenated_word = "wonderful-" * 4
        lyrics = "\n".join([
            "Éternel 爱 God our refuge and strength forever and ever amen",
            hyphenated_word, "Final lyric",
        ])

        sections = prepare_lyrics(lyrics)

        lines = [
            line for section in sections for slide in section.slides for line in slide
        ]
        self.assertEqual(" ".join(lines).split(), lyrics.split())
        self.assertIn(hyphenated_word, lines)
        self.assertTrue(all(len(line) <= 45 for line in lines))
        self.assertTrue(all(
            len(slide) <= 2 for section in sections for slide in section.slides
        ))

    def test_preserves_repeated_section_labels_and_source_case(self):
        sections = prepare_lyrics("[CHORUS]\nSing\n[CHORUS]\nSing")

        self.assertEqual([section.label for section in sections], ["CHORUS", "CHORUS"])
        self.assertEqual(sections[0].slides, sections[1].slides)

    def test_rejects_empty_label_only_oversize_and_control_character_lyrics(self):
        for lyrics in (
            "", " \n\t", "[Verse 1]\n[Chorus]", "x" * 20001,
            "a\x00b", "a\x1fb", "a\x7fb",
        ):
            with self.subTest(lyrics=lyrics[:20]), self.assertRaises(ValidationError):
                prepare_lyrics(lyrics)

    def test_allows_tabs_crlf_and_exact_character_limit(self):
        sections = prepare_lyrics("Sing\tforever\r\nAmen")

        self.assertEqual(sections[0].slides[0][-1], "Amen")
        self.assertTrue(prepare_lyrics("word " * 4000))

    def test_accepts_45_character_word_and_rejects_46_without_splitting(self):
        self.assertEqual(prepare_lyrics("x" * 45)[0].slides, (("x" * 45,),))

        with self.assertRaisesMessage(ValidationError, "missing space"):
            prepare_lyrics("x" * 46)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class UnlistedSongTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(
            email="unlisted-owner@example.test", password="!test-unusable",
        )
        cls.other = User.objects.create(
            email="unlisted-other@example.test", password="!test-unusable",
        )
        cls.inactive = User.objects.create(
            email="unlisted-inactive@example.test", password="!test-unusable",
            is_active=False,
        )
        cls.team = User.objects.create(
            email="unlisted-team@example.test", password="!test-unusable", is_staff=True,
        )
        Group.objects.create(name="Technical Team").user_set.add(cls.team)

    def data(self, **changes):
        return replace(UnlistedSongInput(
            date(2026, 10, 18), ServiceSection.PRAISE, "A new song",
            "[Verse1]\nGod is our refuge\nAnd strength\n\n[Chorus]\nSing again (x2)",
        ), **changes)

    def save(self, **changes):
        return save_unlisted_song(self.data(**changes), user=self.owner)

    def reviewed(self):
        song = self.save()
        review_unlisted_song(song.cart_id, song.id, song.fingerprint, user=self.owner)
        return get_unlisted_song(song.cart_id, song.id, user=self.owner)

    def test_saves_raw_and_prepared_content_to_an_owned_draft_without_email(self):
        data = self.data(lyrics="  [Verse1]\r\nÉternel\tGod\r\n\r\nAmen  ")

        song = save_unlisted_song(data, user=self.owner)

        cart = SongCart.objects.get(pk=song.cart_id)
        stored = cart.songs.get(pk=song.id)
        self.assertEqual(cart.owner_id, self.owner.pk)
        self.assertEqual(cart.status, CartStatus.DRAFT)
        self.assertIsNone(stored.song_uid)
        self.assertEqual(stored.original_lyrics, data.lyrics)
        self.assertEqual(stored.prepared_sections[0]["label"], "Verse1")
        self.assertEqual(stored.prepared_sections[0]["slides"][-1], ["Amen"])
        self.assertEqual(song.lyrics, data.lyrics)
        self.assertIsNone(song.reviewed_at)
        self.assertTrue(song.can_edit)
        self.assertEqual(len(song.fingerprint), 64)
        self.assertEqual(cart.emails.count(), 0)

    def test_cart_details_include_unlisted_projection_and_catalog_metadata_defaults(self):
        song = self.save()
        SongCartItem.objects.create(
            cart_id=song.cart_id, section=ServiceSection.WORSHIP,
            song_uid="stable-catalog", title="Catalog title", authors=["Original author"],
        )

        details = get_cart(song.cart_id, user=self.owner)

        unlisted, catalog = details.songs
        self.assertEqual(unlisted.original_lyrics, song.lyrics)
        self.assertEqual(unlisted.sections, song.sections)
        self.assertEqual(unlisted.formatted_text, song.formatted_text)
        self.assertIsNone(unlisted.song_uid)
        self.assertEqual(catalog.song_uid, "stable-catalog")
        self.assertEqual(catalog.authors, ("Original author",))
        self.assertEqual(
            (catalog.original_lyrics, catalog.sections, catalog.formatted_text),
            ("", (), ""),
        )

    def test_allows_same_title_more_than_once_without_overwriting(self):
        first = self.save()

        second = self.save(lyrics="Another lyric")

        self.assertEqual(first.cart_id, second.cart_id)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(SongCartItem.objects.filter(cart_id=first.cart_id).count(), 2)
        self.assertEqual(get_unlisted_song(
            first.cart_id, first.id, user=self.owner,
        ).lyrics, first.lyrics)

    def test_invalid_intake_does_not_create_a_cart(self):
        cases = (
            {"service_date": "2026-10-18"}, {"section": "other"}, {"title": " "},
            {"title": "t" * 513}, {"title": "a\x00b"}, {"lyrics": "[Chorus]"},
            {"lyrics": "x" * 20001}, {"lyrics": "x" * 46},
        )

        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.save(**changes)

        self.assertEqual(SongCart.objects.count(), 0)

    def test_review_is_idempotent_and_unchanged_save_preserves_review_time(self):
        reviewed = self.reviewed()

        review_unlisted_song(
            reviewed.cart_id, reviewed.id, reviewed.fingerprint, user=self.owner,
        )
        saved = self.save(song_id=reviewed.id)

        self.assertIsNotNone(reviewed.reviewed_at)
        self.assertEqual(saved.reviewed_at, reviewed.reviewed_at)
        self.assertEqual(saved.fingerprint, reviewed.fingerprint)

    def test_title_lyrics_and_section_edits_each_invalidate_review(self):
        for changes in (
            {"title": "Changed title"}, {"lyrics": "Changed lyrics"},
            {"section": ServiceSection.WORSHIP},
        ):
            with self.subTest(changes=changes):
                song = self.reviewed()

                changed = self.save(song_id=song.id, **changes)

                self.assertIsNone(changed.reviewed_at)
                self.assertNotEqual(changed.fingerprint, song.fingerprint)

    def test_stale_review_does_not_acknowledge_new_content(self):
        song = self.save()
        self.save(song_id=song.id, lyrics="Changed lyrics")

        with self.assertRaisesMessage(ValidationError, "out of date"):
            review_unlisted_song(song.cart_id, song.id, song.fingerprint, user=self.owner)

        self.assertIsNone(get_unlisted_song(
            song.cart_id, song.id, user=self.owner,
        ).reviewed_at)

    def test_fingerprint_covers_exact_stored_preparation(self):
        song = self.save()
        SongCartItem.objects.filter(pk=song.id).update(prepared_sections=[{
            "position": 1, "label": "Verse1", "slides": [["Changed preparation"]],
        }])

        with self.assertRaisesMessage(ValidationError, "out of date"):
            review_unlisted_song(song.cart_id, song.id, song.fingerprint, user=self.owner)

        self.assertIsNone(SongCartItem.objects.get(pk=song.id).reviewed_at)

    def test_existing_item_cannot_be_moved_to_another_service_date(self):
        song = self.save()

        with self.assertRaisesMessage(ValidationError, "date must match"):
            self.save(song_id=song.id, service_date=song.service_date + timedelta(days=1))

        self.assertEqual(SongCart.objects.count(), 1)
        self.assertEqual(get_unlisted_song(
            song.cart_id, song.id, user=self.owner,
        ).service_date, song.service_date)

    def test_catalog_item_cannot_be_edited_as_unlisted(self):
        song = self.save()
        catalog = SongCartItem.objects.create(
            cart_id=song.cart_id, section=ServiceSection.WORSHIP,
            song_uid="catalog-uid", title="Catalog title", authors=["Catalog author"],
        )

        with self.assertRaisesMessage(ValidationError, "Only unlisted songs"):
            self.save(song_id=catalog.id, title="Changed catalog")

        catalog.refresh_from_db()
        self.assertEqual((catalog.song_uid, catalog.title, catalog.authors), (
            "catalog-uid", "Catalog title", ["Catalog author"],
        ))
        self.assertEqual(catalog.original_lyrics, "")

    def test_other_owner_cannot_read_review_or_update_an_item(self):
        song = self.save()

        with self.assertRaises(SongCart.DoesNotExist):
            get_unlisted_song(song.cart_id, song.id, user=self.other)
        with self.assertRaises(SongCart.DoesNotExist):
            review_unlisted_song(song.cart_id, song.id, song.fingerprint, user=self.other)
        with self.assertRaises(SongCartItem.DoesNotExist):
            save_unlisted_song(self.data(song_id=song.id), user=self.other)

        self.assertEqual(SongCartItem.objects.get(pk=song.id).title, song.title)

    def test_unauthenticated_and_inactive_users_cannot_save(self):
        for user in (AnonymousUser(), self.inactive):
            with self.subTest(user=user), self.assertRaises(PermissionDenied):
                save_unlisted_song(self.data(), user=user)

        self.assertEqual(SongCart.objects.count(), 0)

    def test_locked_states_allow_reading_but_reject_save_and_review(self):
        song = self.reviewed()
        for status in (CartStatus.PENDING, CartStatus.CONFIRMED, CartStatus.REJECTED):
            with self.subTest(status=status):
                SongCart.objects.filter(pk=song.cart_id).update(status=status)

                details = get_unlisted_song(song.cart_id, song.id, user=self.owner)
                with self.assertRaises(ValidationError):
                    self.save(song_id=song.id, title="Locked edit")
                with self.assertRaises(ValidationError):
                    review_unlisted_song(
                        song.cart_id, song.id, song.fingerprint, user=self.owner,
                    )
                with self.assertRaises(ValidationError):
                    self.save(title="Another song on locked date")

                self.assertFalse(details.can_edit)
                self.assertEqual(details.reviewed_at, song.reviewed_at)

    def test_submission_requires_review_of_every_unlisted_song(self):
        song = self.reviewed()
        self.save(title="Another unreviewed song")

        with self.assertRaisesMessage(ValidationError, "every unlisted song"):
            checkout_cart(song.cart_id, user=self.owner)

        cart = SongCart.objects.get(pk=song.cart_id)
        self.assertEqual(cart.status, CartStatus.DRAFT)
        self.assertIsNone(cart.submitted_at)
        self.assertEqual(cart.emails.count(), 0)

    def test_reviewed_submission_emails_contain_sectioned_projection_handoff(self):
        song = self.reviewed()

        with self.captureOnCommitCallbacks(execute=True):
            checkout_cart(song.cart_id, user=self.owner)

        cart = SongCart.objects.get(pk=song.cart_id)
        self.assertEqual(cart.status, CartStatus.PENDING)
        self.assertEqual(len(mail.outbox), 2)
        for email in mail.outbox:
            self.assertIn(f"#{song.id} {song.title}", email.body)
            self.assertIn("Unlisted song — reviewed projection text", email.body)
            self.assertIn(song.formatted_text, email.body)
            self.assertIn("Praise\n", email.body)
        self.assertEqual(mail.outbox[1].bcc, [self.team.email])

    def test_database_rejects_inconsistent_song_source_fields(self):
        song = self.save()

        for fields in ({"song_uid": "catalog-uid"}, {"original_lyrics": ""}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    SongCartItem.objects.filter(pk=song.id).update(**fields)

        self.assertIsNone(SongCartItem.objects.get(pk=song.id).song_uid)
