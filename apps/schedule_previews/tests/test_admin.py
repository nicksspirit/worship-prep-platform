from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.schedule_previews.models import SchedulePreview


class SchedulePreviewAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            "preview-staff@example.test", "test-only-password", is_staff=True
        )
        cls.member = get_user_model().objects.create_user(
            "preview-member@example.test", "test-only-password"
        )
        cls.list_url = reverse("admin:schedule_previews_schedulepreview_changelist")
        now = timezone.now()
        cls.active = SchedulePreview.objects.create(
            content={"title": "Sunday Worship", "sections": []},
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        cls.preview_url = reverse("schedule_preview", args=[cls.active.pk])
        cls.delete_url = reverse(
            "admin:schedule_previews_schedulepreview_delete", args=[cls.active.pk]
        )

    def test_staff_can_open_active_preview_from_service_preparation(self):
        now = timezone.now()
        SchedulePreview.objects.create(
            content={"title": "Earlier Worship", "sections": []},
            created_at=now - timedelta(days=1),
            expires_at=now - timedelta(hours=1),
        )
        self.client.force_login(self.staff)

        page = self.client.get(self.list_url)

        self.assertContains(page, "Service Preparation")
        self.assertContains(page, "Schedule Previews")
        self.assertContains(page, "Sunday Worship")
        self.assertContains(page, self.preview_url)
        self.assertContains(page, "Earlier Worship")
        self.assertContains(page, "Expired")
        self.assertContains(page, "Open preview", count=1)

    def test_member_cannot_list_preview_links(self):
        self.client.force_login(self.member)

        page = self.client.get(self.list_url)

        self.assertEqual(page.status_code, 302)

    def test_staff_with_delete_permission_can_revoke_preview_link(self):
        self.staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="schedule_previews",
                codename="delete_schedulepreview",
            )
        )
        self.client.force_login(self.staff)

        deleted = self.client.post(self.delete_url, {"post": "yes"})

        self.assertEqual(deleted.status_code, 302)
        self.assertEqual(self.client.get(self.preview_url).status_code, 404)

    def test_staff_without_delete_permission_cannot_revoke_preview_link(self):
        self.client.force_login(self.staff)

        denied = self.client.post(self.delete_url, {"post": "yes"})

        self.assertEqual(denied.status_code, 403)
        self.assertTrue(SchedulePreview.objects.filter(pk=self.active.pk).exists())
