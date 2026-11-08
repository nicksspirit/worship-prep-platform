from uuid import uuid4

from django.db import models


class SchedulePreview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(null=True, editable=False)
    expires_at = models.DateTimeField(db_index=True)
    content = models.JSONField()
    request_details = models.JSONField(null=True, editable=False)
    submitted_payload = models.JSONField(null=True, editable=False)
    publisher_key_id = models.PositiveBigIntegerField(null=True, editable=False)

    def __str__(self) -> str:
        return self.content["title"]
