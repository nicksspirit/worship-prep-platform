from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.apps import apps
from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.song_carts.models import (
    CartComment, CartStatus, EmailKind, ServiceSection, SongCart, SongCartItem,
)
from apps.song_carts.services import (
    add_comment, checkout_cart, confirm_submission, edit_comment, get_cart,
    is_technical_team, list_carts, read_submission_for_admin, reject_submission,
    remove_cart_song, retry_submission_emails, send_submission_reply, submission_overview,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SubmissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(
            password="!test-unusable", email="owner@example.test",
        )
        cls.other = User.objects.create(
            password="!test-unusable", email="other@example.test",
        )
        cls.staff = User.objects.create(
            password="!test-unusable", email="staff@example.test", is_staff=True,
        )
        cls.team = User.objects.create(
            password="!test-unusable", email="team@example.test", is_staff=True,
        )
        cls.second_team = User.objects.create(
            password="!test-unusable", email="second@example.test", is_staff=True,
        )
        cls.nonstaff_team = User.objects.create(
            password="!test-unusable", email="nonstaff@example.test",
        )
        cls.inactive_team = User.objects.create(
            password="!test-unusable",
            email="inactive@example.test", is_staff=True, is_active=False,
        )
        group = Group.objects.create(name="Technical Team")
        group.user_set.add(
            cls.team, cls.second_team, cls.nonstaff_team, cls.inactive_team,
        )

    def draft(self, *, owner=None, day=11):
        cart = SongCart.objects.create(
            owner=owner or self.owner, service_date=date(2026, 10, day),
        )
        SongCartItem.objects.create(
            cart=cart, section=ServiceSection.CALL_TO_WORSHIP,
            song_uid="stable-song-uid", title="Example Song", authors=["Example Author"],
        )
        return cart

    def submit(self, cart):
        with self.captureOnCommitCallbacks(execute=True):
            checkout_cart(cart.id, user=self.owner)
        cart.refresh_from_db()

    def test_submit_records_pending_and_sends_owner_receipt_and_team_notice(self):
        cart = self.draft()

        self.submit(cart)

        self.assertEqual(cart.status, CartStatus.PENDING)
        self.assertIsNotNone(cart.submitted_at)
        self.assertIsNone(cart.confirmed_at)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])
        self.assertCountEqual(
            mail.outbox[1].bcc, [self.team.email, self.second_team.email],
        )
        self.assertIn("#", mail.outbox[1].body)
        self.assertCountEqual(cart.emails.values_list("kind", flat=True), [
            EmailKind.RECEIPT, EmailKind.TEAM_NOTICE,
        ])

    def test_repeated_submit_preserves_time_and_email_events(self):
        cart = self.draft()
        self.submit(cart)
        submitted_at = cart.submitted_at

        self.submit(cart)

        self.assertEqual(cart.submitted_at, submitted_at)
        self.assertEqual(cart.emails.count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_email_failure_does_not_roll_back_submission_or_other_email(self):
        cart = self.draft()

        with patch("apps.song_carts.services.emails.EmailMessage.send", side_effect=[
            OSError("mail unavailable"), 1,
        ]):
            self.submit(cart)

        self.assertEqual(cart.status, CartStatus.PENDING)
        self.assertEqual(cart.emails.get(kind=EmailKind.RECEIPT).status, "failed")
        self.assertEqual(cart.emails.get(kind=EmailKind.TEAM_NOTICE).status, "sent")

    def test_team_first_open_records_actor_and_sends_one_confirmation(self):
        cart = self.draft()
        self.submit(cart)

        with self.captureOnCommitCallbacks(execute=True):
            confirm_submission(cart.id, user=self.team)

        cart.refresh_from_db()
        self.assertEqual(cart.status, CartStatus.CONFIRMED)
        self.assertEqual(cart.confirmed_by, self.team)
        self.assertIsNotNone(cart.confirmed_at)
        self.assertEqual(len(mail.outbox), 3)
        self.assertIn("does not mean", mail.outbox[-1].body)

    def test_second_view_preserves_first_actor_and_creates_no_email(self):
        cart = self.draft()
        self.submit(cart)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_submission(cart.id, user=self.team)
        cart.refresh_from_db()
        confirmed_at = cart.confirmed_at

        with self.captureOnCommitCallbacks(execute=True):
            confirm_submission(cart.id, user=self.second_team)

        cart.refresh_from_db()
        self.assertEqual(cart.confirmed_at, confirmed_at)
        self.assertEqual(cart.confirmed_by, self.team)
        self.assertEqual(cart.emails.filter(kind=EmailKind.CONFIRMATION).count(), 1)
        self.assertEqual(len(mail.outbox), 3)

    def test_general_staff_cannot_acknowledge(self):
        cart = self.draft()
        self.submit(cart)

        with self.assertRaises(PermissionDenied):
            confirm_submission(cart.id, user=self.staff)

        cart.refresh_from_db()
        self.assertEqual(cart.status, CartStatus.PENDING)

    def test_nonstaff_group_members_cannot_acknowledge(self):
        cart = self.draft()
        self.submit(cart)

        with self.assertRaises(PermissionDenied):
            confirm_submission(cart.id, user=self.nonstaff_team)

    def test_inactive_team_members_have_no_team_authority(self):
        self.assertFalse(is_technical_team(self.inactive_team))

    def test_opening_draft_does_not_confirm_or_notify(self):
        cart = self.draft()

        confirm_submission(cart.id, user=self.team)

        cart.refresh_from_db()
        self.assertEqual(cart.status, CartStatus.DRAFT)
        self.assertFalse(cart.emails.exists())

    def test_rejection_of_confirmed_preserves_seen_actor_and_time(self):
        cart = self.draft()
        self.submit(cart)
        confirm_submission(cart.id, user=self.team)
        cart.refresh_from_db()
        confirmed_at = cart.confirmed_at

        with self.captureOnCommitCallbacks(execute=True):
            reject_submission(
                cart.id, "Unable to prepare this selection", user=self.second_team,
            )

        cart.refresh_from_db()
        self.assertEqual(cart.status, CartStatus.REJECTED)
        self.assertEqual(cart.confirmed_at, confirmed_at)
        self.assertEqual(cart.confirmed_by, self.team)
        self.assertEqual(cart.rejected_by, self.second_team)
        self.assertIn(cart.rejection_reason, mail.outbox[-1].body)

    def test_pending_can_be_rejected_without_seen_confirmation(self):
        cart = self.draft()
        self.submit(cart)

        reject_submission(cart.id, "Please contact the team", user=self.team)

        cart.refresh_from_db()
        self.assertEqual(cart.status, CartStatus.REJECTED)
        self.assertIsNone(cart.confirmed_at)

    def test_rejected_opening_never_reconfirms(self):
        cart = self.draft()
        self.submit(cart)
        reject_submission(cart.id, "Reason", user=self.team)

        confirm_submission(cart.id, user=self.second_team)

        cart.refresh_from_db()
        self.assertEqual(cart.status, CartStatus.REJECTED)
        self.assertIsNone(cart.confirmed_at)
        self.assertFalse(cart.emails.filter(kind=EmailKind.CONFIRMATION).exists())

    def test_repeated_rejection_does_not_change_reason_or_send_again(self):
        cart = self.draft()
        self.submit(cart)
        with self.captureOnCommitCallbacks(execute=True):
            reject_submission(cart.id, "First reason", user=self.team)

        with self.captureOnCommitCallbacks(execute=True):
            reject_submission(cart.id, "Another reason", user=self.second_team)

        cart.refresh_from_db()
        self.assertEqual(cart.rejection_reason, "First reason")
        self.assertEqual(cart.emails.filter(kind=EmailKind.REJECTION).count(), 1)
        self.assertEqual(len(mail.outbox), 3)

    def test_rejection_requires_a_reason(self):
        cart = self.draft()
        self.submit(cart)

        with self.assertRaises(ValidationError):
            reject_submission(cart.id, " ", user=self.team)

    def test_rejection_reason_cannot_exceed_2000_characters(self):
        cart = self.draft()
        self.submit(cart)

        with self.assertRaises(ValidationError):
            reject_submission(cart.id, "x" * 2001, user=self.team)

    def test_general_staff_cannot_reject(self):
        cart = self.draft()
        self.submit(cart)

        with self.assertRaises(PermissionDenied):
            reject_submission(cart.id, "Reason", user=self.staff)

    def test_submitted_states_lock_song_removal(self):
        for state in (CartStatus.PENDING, CartStatus.CONFIRMED, CartStatus.REJECTED):
            with self.subTest(state=state):
                cart = self.draft(day=11 + list(CartStatus.values).index(state))
                cart.status = state
                cart.save(update_fields=["status"])
                with self.assertRaises(ValidationError):
                    remove_cart_song(cart.id, cart.songs.get().id, user=self.owner)
                self.assertEqual(cart.songs.count(), 1)

    def test_draft_comments_are_saved_without_email(self):
        cart = self.draft()

        comment_id = add_comment(cart.id, "Start with song #1", user=self.owner)

        comment = CartComment.objects.get(pk=comment_id)
        self.assertIsNone(comment.updated_at)
        self.assertFalse(cart.emails.exists())
        self.assertTrue(get_cart(cart.id, user=self.owner).comments[0].can_edit)

    def test_draft_comments_remain_editable_after_fifteen_minutes(self):
        cart = self.draft()
        comment_id = add_comment(cart.id, "Original", user=self.owner)
        CartComment.objects.filter(pk=comment_id).update(
            created_at=timezone.now() - timedelta(days=1),
        )

        edit_comment(cart.id, comment_id, "Updated", user=self.owner)

        self.assertEqual(CartComment.objects.get(pk=comment_id).body, "Updated")
        self.assertFalse(cart.emails.exists())

    def test_old_draft_comment_edit_window_starts_at_submission(self):
        cart = self.draft()
        comment_id = add_comment(cart.id, "Original", user=self.owner)
        CartComment.objects.filter(pk=comment_id).update(
            created_at=timezone.now() - timedelta(days=1),
        )
        self.submit(cart)

        with self.captureOnCommitCallbacks(execute=True):
            edit_comment(cart.id, comment_id, "Updated after submit", user=self.owner)

        self.assertEqual(
            CartComment.objects.get(pk=comment_id).body, "Updated after submit",
        )
        self.assertEqual(cart.emails.filter(kind=EmailKind.COMMENT).count(), 1)
        self.assertEqual(len(mail.outbox), 3)

    def test_comment_edit_deadline_is_enforced_and_exposed(self):
        cart = self.draft()
        comment_id = add_comment(cart.id, "Original", user=self.owner)
        old = timezone.now() - timedelta(minutes=16)
        CartComment.objects.filter(pk=comment_id).update(created_at=old)
        self.submit(cart)
        SongCart.objects.filter(pk=cart.id).update(submitted_at=old)

        with self.assertRaisesMessage(ValidationError, "15-minute"):
            edit_comment(cart.id, comment_id, "Too late", user=self.owner)

        comment = get_cart(cart.id, user=self.owner).comments[0]
        self.assertFalse(comment.can_edit)
        self.assertEqual(comment.edit_deadline, old + timedelta(minutes=15))

    def test_post_submission_comment_uses_its_creation_time_for_deadline(self):
        cart = self.draft()
        self.submit(cart)
        SongCart.objects.filter(pk=cart.id).update(
            submitted_at=timezone.now() - timedelta(days=1),
        )

        comment_id = add_comment(cart.id, "New question", user=self.owner)

        comment = get_cart(cart.id, user=self.owner).comments[0]
        self.assertEqual(comment.id, comment_id)
        self.assertTrue(comment.can_edit)
        self.assertEqual(
            comment.edit_deadline, comment.created_at + timedelta(minutes=15),
        )

    def test_owner_can_add_comment_after_rejection(self):
        cart = self.draft()
        self.submit(cart)
        reject_submission(cart.id, "Reason", user=self.team)

        with self.captureOnCommitCallbacks(execute=True):
            comment_id = add_comment(cart.id, "Please explain", user=self.owner)

        self.assertEqual(CartComment.objects.get(pk=comment_id).body, "Please explain")
        self.assertEqual(cart.emails.filter(kind=EmailKind.COMMENT).count(), 1)
        cart.refresh_from_db()
        self.assertEqual(cart.status, CartStatus.REJECTED)

    def test_other_users_cannot_post_in_owner_thread(self):
        cart = self.draft()

        with self.assertRaises(SongCart.DoesNotExist):
            add_comment(cart.id, "Other message", user=self.other)

        self.assertFalse(cart.comments.exists())

    def test_admin_cannot_post_in_owner_thread(self):
        cart = self.draft()

        with self.assertRaises(SongCart.DoesNotExist):
            add_comment(cart.id, "Admin message", user=self.team)

    def test_missing_comment_id_is_a_validation_error(self):
        cart = self.draft()

        with self.assertRaises(ValidationError):
            edit_comment(cart.id, 123456, "Missing", user=self.owner)

    def test_comments_validate_nonempty_body(self):
        cart = self.draft()

        with self.assertRaises(ValidationError):
            add_comment(cart.id, " ", user=self.owner)

    def test_comments_validate_maximum_length(self):
        cart = self.draft()

        with self.assertRaises(ValidationError):
            add_comment(cart.id, "x" * 5001, user=self.owner)

    def test_repeating_same_edit_does_not_send_another_notice(self):
        cart = self.draft()
        self.submit(cart)
        with self.captureOnCommitCallbacks(execute=True):
            comment_id = add_comment(cart.id, "Question", user=self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            edit_comment(cart.id, comment_id, "Question", user=self.owner)

        self.assertEqual(cart.emails.filter(kind=EmailKind.COMMENT).count(), 1)
        self.assertIsNone(cart.comments.get().updated_at)

    def test_manual_reply_sends_only_email_and_is_idempotent(self):
        cart = self.draft()
        self.submit(cart)
        request_id = uuid4()
        with self.captureOnCommitCallbacks(execute=True):
            send_submission_reply(
                cart.id, "Please call us", user=self.team, request_id=request_id,
            )

        result = send_submission_reply(
            cart.id, "Please call us", user=self.team, request_id=request_id,
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 3)
        self.assertFalse(cart.comments.exists())
        self.assertEqual(cart.emails.filter(kind=EmailKind.REPLY).count(), 1)
        self.assertEqual(mail.outbox[-1].to, [self.owner.email])

    def test_manual_reply_failure_records_failed_event(self):
        cart = self.draft()
        self.submit(cart)

        with patch(
            "apps.song_carts.services.emails.EmailMessage.send", side_effect=OSError(),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                send_submission_reply(
                    cart.id, "Reply", user=self.team, request_id=uuid4(),
                )

        self.assertEqual(cart.emails.get(kind=EmailKind.REPLY).status, "failed")
        cart.refresh_from_db()
        self.assertEqual(cart.status, CartStatus.PENDING)

    def test_general_staff_cannot_send_manual_reply(self):
        cart = self.draft()
        self.submit(cart)

        with self.assertRaises(PermissionDenied):
            send_submission_reply(cart.id, "Reply", user=self.staff, request_id=uuid4())

    def test_manual_reply_validates_maximum_length(self):
        cart = self.draft()
        self.submit(cart)

        with self.assertRaises(ValidationError):
            send_submission_reply(
                cart.id, "x" * 10001, user=self.team, request_id=uuid4(),
            )

    def test_team_can_retry_only_failed_events(self):
        cart = self.draft()
        with patch(
            "apps.song_carts.services.emails.EmailMessage.send",
            side_effect=[OSError(), 1],
        ):
            self.submit(cart)

        result = retry_submission_emails(cart.id, user=self.team)

        self.assertEqual(result, (1, 0))
        self.assertEqual(cart.emails.get(kind=EmailKind.RECEIPT).status, "sent")
        self.assertEqual(len(mail.outbox), 1)

    def test_general_staff_cannot_retry_events(self):
        cart = self.draft()
        self.submit(cart)

        with self.assertRaises(PermissionDenied):
            retry_submission_emails(cart.id, user=self.staff)

    def test_no_team_recipients_preserves_receipt_and_failed_team_notice(self):
        self.team.groups.clear()
        self.second_team.groups.clear()
        cart = self.draft()

        self.submit(cart)

        self.assertEqual(cart.status, "pending")
        self.assertEqual(cart.emails.get(kind=EmailKind.RECEIPT).status, "sent")
        self.assertEqual(cart.emails.get(kind=EmailKind.TEAM_NOTICE).status, "failed")

    def test_rollback_discards_lifecycle_and_events(self):
        cart = self.draft()

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    checkout_cart(cart.id, user=self.owner)
                    raise RuntimeError("rollback")

        cart.refresh_from_db()
        self.assertEqual(cart.status, "draft")
        self.assertFalse(cart.emails.exists())
        self.assertEqual(mail.outbox, [])

    def test_owner_list_filter_is_isolated_from_other_users(self):
        cart = self.draft()
        self.submit(cart)
        self.draft(owner=self.other)

        rows = list_carts(user=self.owner, status="pending")

        self.assertEqual([row.id for row in rows], [cart.id])

    def test_owner_list_validates_sort(self):
        with self.assertRaises(ValidationError):
            list_carts(user=self.owner, sort="unsafe")

    def test_recently_submitted_sort_places_drafts_last(self):
        pending = self.draft()
        self.submit(pending)
        draft = self.draft(day=12)

        rows = list_carts(user=self.owner, sort="submitted_desc")

        self.assertEqual([row.id for row in rows], [pending.id, draft.id])

    def test_owner_list_validates_state(self):
        with self.assertRaises(ValidationError):
            list_carts(user=self.owner, status="unsafe")

    def test_admin_read_does_not_acknowledge(self):
        cart = self.draft()
        self.submit(cart)

        result = read_submission_for_admin(cart.id, user=self.staff)

        self.assertEqual(result.status, "pending")
        self.assertIsNone(result.confirmed_by)
        self.assertEqual(cart.emails.count(), 2)

    def test_owner_cannot_read_admin_submission_details(self):
        cart = self.draft()

        with self.assertRaises(PermissionDenied):
            read_submission_for_admin(cart.id, user=self.owner)

    def test_admin_overview_defaults_pending_and_excludes_drafts_from_counts(self):
        pending = self.draft()
        self.submit(pending)
        self.draft(day=12)

        result = submission_overview(user=self.staff)

        self.assertEqual([row.id for row in result.rows], [pending.id])
        self.assertEqual(result.counts, {
            "pending": 1, "confirmed": 0, "rejected": 0, "total": 1,
        })

    def test_admin_empty_filter_excludes_drafts(self):
        pending = self.draft()
        self.submit(pending)
        self.draft(day=12)

        result = submission_overview(user=self.staff, status="")

        self.assertEqual(result.total, 1)
        self.assertEqual(result.rows[0].id, pending.id)

    def test_admin_all_filter_explicitly_includes_drafts(self):
        self.draft()

        result = submission_overview(user=self.staff, status="all")

        self.assertEqual(result.total, 1)
        self.assertEqual(result.counts["total"], 0)

    def test_admin_overview_discloses_truncation(self):
        SongCart.objects.bulk_create([
            SongCart(
                owner=self.owner, service_date=date(2026, 1, 1) + timedelta(days=index),
            )
            for index in range(101)
        ])

        result = submission_overview(user=self.staff, status="all")

        self.assertEqual(result.total, 101)
        self.assertEqual(len(result.rows), 100)
        self.assertTrue(result.truncated)

    def test_admin_overview_searches_submitter(self):
        self.draft()
        other = self.draft(owner=self.other)

        result = submission_overview(user=self.staff, status="all", query="other@example")

        self.assertEqual([row.id for row in result.rows], [other.id])

    def test_new_comment_and_email_tables_have_row_level_security(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relname, relrowsecurity FROM pg_class WHERE relname IN "
                "('song_carts_cartcomment', 'song_carts_submissionemail')"
            )
            protected = dict(cursor.fetchall())

        self.assertEqual(protected, {
            "song_carts_cartcomment": True, "song_carts_submissionemail": True,
        })

    def test_legacy_submission_migration_preserves_known_history_without_email(self):
        from importlib import import_module
        migration = import_module(
            "apps.song_carts.migrations."
            "0002_alter_songcart_options_songcart_confirmed_by_and_more"
        )
        cart = self.draft()
        old_time = timezone.now() - timedelta(days=1)
        SongCart.objects.filter(pk=cart.id).update(
            status="confirmed", confirmed_at=old_time, notification_status="sent",
            notified_at=old_time, notification_error="historical error",
        )
        cart.songs.update(section="praise_worship")

        with connection.schema_editor(atomic=False) as editor:
            migration.migrate_legacy_submissions(apps, editor)

        cart.refresh_from_db()
        self.assertEqual(cart.status, "pending")
        self.assertEqual(cart.submitted_at, old_time)
        self.assertIsNone(cart.confirmed_at)
        self.assertIsNone(cart.confirmed_by)
        self.assertEqual(cart.notification_status, "sent")
        self.assertEqual(cart.songs.get().section, "praise")
        event = cart.emails.get()
        self.assertEqual(event.status, "sent")
        self.assertEqual(event.sent_at, old_time)
        self.assertEqual(event.error, "historical error")
        self.assertEqual(mail.outbox, [])
