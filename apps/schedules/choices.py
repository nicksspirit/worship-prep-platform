from django.db import models


class ServiceScheduleStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    IN_PROGRESS = "in_progress", "In Progress"
    READY = "ready", "Ready"
    PUBLISHED = "published", "Published"


class ScheduleItemType(models.TextChoices):
    SUNDAY_SCHOOL = "sunday_school", "Sunday School"
    OPENING_PRAYER = "opening_prayer", "Opening Prayer"
    CLOSING_PRAYER = "closing_prayer", "Closing Prayer"
    WORSHIP_SONG = "worship_song", "Worship Song"
    HYMN = "hymn", "Hymn"
    SCRIPTURE_READING = "scripture_reading", "Scripture Reading"
    SERMON = "sermon", "Sermon"
    ANNOUNCEMENTS = "announcements", "Announcements"
    OFFERING = "offering", "Offering"
    SPECIAL_ITEM = "special_item", "Special Item"


class ScheduleItemStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
    NEEDS_REVISION = "needs_revision", "Needs Revision"


class ContactRole(models.TextChoices):
    MINISTER = "minister", "Minister"
    CHOIR = "choir", "Choir"
    PASTOR = "pastor", "Pastor"
    OTHER = "other", "Other"


class SubmissionSource(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "Email"
    UNKNOWN = "unknown", "Unknown"


class SubmissionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    MATCHED = "matched", "Matched"
    REJECTED = "rejected", "Rejected"


class ParsedContentType(models.TextChoices):
    AGENDA = "agenda", "Agenda"
    LYRICS = "lyrics", "Lyrics"
    SCRIPTURE = "scripture", "Scripture"
    HYMN = "hymn", "Hymn"
    SERMON = "sermon", "Sermon"
    ANNOUNCEMENT = "announcement", "Announcement"
