from django.conf import settings
from django.db import models
from django_stubs_ext.db.models import TypedModelMeta

from apps.common.models import BaseModel
from apps.schedules.choices import (
    ContactRole,
    ParsedContentType,
    ScheduleItemStatus,
    ScheduleItemType,
    ServiceScheduleStatus,
    SubmissionSource,
    SubmissionStatus,
)


class ScheduleTemplate(BaseModel):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)

    class Meta(TypedModelMeta):
        verbose_name = "Schedule Template"
        verbose_name_plural = "Schedule Templates"

    def __str__(self) -> str:
        return self.name


class ServiceSchedule(BaseModel):
    date = models.DateField(unique=True)
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ServiceScheduleStatus.choices,
        default=ServiceScheduleStatus.DRAFT,
    )
    template = models.ForeignKey(
        ScheduleTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedules",
    )
    notes = models.TextField(blank=True)

    class Meta(TypedModelMeta):
        verbose_name = "Service Schedule"
        verbose_name_plural = "Service Schedules"

    def __str__(self) -> str:
        return f"{self.date.isoformat()} - {self.title or 'Sunday Service'}"


class Contact(BaseModel):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=20, choices=ContactRole.choices, default=ContactRole.OTHER)

    class Meta(TypedModelMeta):
        constraints = [
            models.UniqueConstraint(fields=["name", "phone"], name="unique_contact_name_phone")
        ]
        verbose_name = "Contact"
        verbose_name_plural = "Contacts"

    def __str__(self) -> str:
        return self.name


class TemplateItem(BaseModel):
    template = models.ForeignKey(
        ScheduleTemplate, on_delete=models.CASCADE, related_name="template_items"
    )
    position = models.PositiveIntegerField()
    item_type = models.CharField(max_length=32, choices=ScheduleItemType.choices)
    title = models.CharField(max_length=255)
    is_required = models.BooleanField(default=True)
    default_contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="template_items"
    )

    class Meta(TypedModelMeta):
        constraints = [
            models.UniqueConstraint(
                fields=["template", "position"], name="unique_template_item_position"
            )
        ]
        ordering = ["position"]
        verbose_name = "Template Item"
        verbose_name_plural = "Template Items"

    def __str__(self) -> str:
        return f"{self.template.name} #{self.position}: {self.title}"


class ScheduleItem(BaseModel):
    schedule = models.ForeignKey(
        ServiceSchedule, on_delete=models.CASCADE, related_name="schedule_items"
    )
    position = models.PositiveIntegerField()
    item_type = models.CharField(max_length=32, choices=ScheduleItemType.choices)
    title = models.CharField(max_length=255)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_required = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20, choices=ScheduleItemStatus.choices, default=ScheduleItemStatus.PENDING
    )
    assigned_contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_items"
    )
    notes = models.TextField(blank=True)

    class Meta(TypedModelMeta):
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "position"], name="unique_schedule_item_position"
            )
        ]
        ordering = ["position"]
        verbose_name = "Schedule Item"
        verbose_name_plural = "Schedule Items"

    def __str__(self) -> str:
        return f"{self.schedule.date.isoformat()} #{self.position}: {self.title}"


class ContentSubmission(BaseModel):
    source = models.CharField(max_length=20, choices=SubmissionSource.choices)
    sender_phone = models.CharField(max_length=32, null=True, blank=True)
    sender_email = models.EmailField(null=True, blank=True)
    sender_name = models.CharField(max_length=255)
    source_message_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    raw_content = models.TextField()
    parsed_content_type = models.CharField(max_length=32, choices=ParsedContentType.choices)
    parsed_title = models.CharField(max_length=255, null=True, blank=True)
    parsed_body = models.TextField()
    parsed_payload = models.JSONField(default=dict, blank=True)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=SubmissionStatus.choices, default=SubmissionStatus.PENDING
    )
    matched_item = models.ForeignKey(
        ScheduleItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="submissions"
    )
    created_schedule = models.ForeignKey(
        ServiceSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta(TypedModelMeta):
        verbose_name = "Content Submission"
        verbose_name_plural = "Content Submissions"

    def __str__(self) -> str:
        return f"{self.source} - {self.sender_name} ({self.created_on.isoformat()})"
