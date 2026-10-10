import uuid

from django.conf import settings
from django.db import models


class ServiceSection(models.TextChoices):
    CALL_TO_WORSHIP = "call_to_worship", "Call to Worship"
    PRAISE = "praise", "Praise"
    WORSHIP = "worship", "Worship"


class CartStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    REJECTED = "rejected", "Rejected"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class EmailKind(models.TextChoices):
    RECEIPT = "receipt", "Submission receipt"
    TEAM_NOTICE = "team_notice", "Technical Team notice"
    CONFIRMATION = "confirmation", "Seen confirmation"
    REJECTION = "rejection", "Rejection notice"
    COMMENT = "comment", "Comment notice"
    REPLY = "reply", "Administrator reply"


class SongCart(models.Model):
    """One person's song selection for a service date."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    service_date = models.DateField()
    status = models.CharField(max_length=16, choices=CartStatus, default=CartStatus.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="confirmed_song_carts",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rejected_song_carts",
    )
    rejection_reason = models.TextField(blank=True)
    notification_status = models.CharField(
        max_length=16, choices=NotificationStatus, default=NotificationStatus.PENDING
    )
    notified_at = models.DateTimeField(null=True, blank=True)
    notification_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "Submission"
        verbose_name_plural = "Submissions"
        ordering = ["-service_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "service_date"], name="song_cart_owner_date_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.service_date} — {self.owner} ({self.get_status_display()})"


class SongCartItem(models.Model):
    """Ordered song metadata retained independently of catalog snapshots."""

    cart = models.ForeignKey(SongCart, on_delete=models.CASCADE, related_name="songs")
    section = models.CharField(max_length=32, choices=ServiceSection)
    song_uid = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=512)
    authors = models.JSONField(default=list, blank=True)
    original_lyrics = models.TextField(blank=True)
    prepared_sections = models.JSONField(default=list, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "section", "song_uid"],
                name="song_cart_section_song_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(song_uid__isnull=False, original_lyrics="")
                    | (models.Q(song_uid__isnull=True) & ~models.Q(original_lyrics=""))
                ),
                name="song_cart_item_source_consistent",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class CartComment(models.Model):
    """The owner's ongoing thread, independent of locked song content."""

    cart = models.ForeignKey(SongCart, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]


class SubmissionEmail(models.Model):
    """One captured email event with its own retryable delivery outcome."""

    cart = models.ForeignKey(SongCart, on_delete=models.CASCADE, related_name="emails")
    kind = models.CharField(max_length=32, choices=EmailKind)
    event_key = models.CharField(max_length=255, default="")
    recipients = models.JSONField(default=list)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(
        max_length=16, choices=NotificationStatus, default=NotificationStatus.PENDING,
    )
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.UniqueConstraint(
            fields=["cart", "kind", "event_key"], name="submission_email_event_unique",
        )]
