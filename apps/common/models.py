from django.db import models
from django.utils import timezone
from django_stubs_ext.db.models import TypedModelMeta

from apps.common.db.fields import AutoDateTimeField


class BaseModel(models.Model):
    created_on = models.DateTimeField(auto_now_add=True, editable=False)
    updated_on = AutoDateTimeField(default=timezone.now)
    deleted_on = models.DateTimeField(null=True, blank=True)

    class Meta(TypedModelMeta):
        abstract = True
        ordering = ["-created_on"]

    def save(self, *args, **kwargs):
        self.full_clean()

        return super().save(*args, **kwargs)