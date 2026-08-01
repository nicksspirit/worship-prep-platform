import typing as ty

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta

from apps.common.models import BaseModel


class APIKeyScope(models.TextChoices):
    """Scopes reserved for Song Catalog machine interfaces."""

    CATALOG_IMPORT = "catalog.import", _("Catalog: Import")
    CATALOG_SEARCH = "catalog.search", _("Catalog: Search")
    SONG_READ = "catalog.song.read", _("Catalog: Song metadata")
    LYRICS_READ = "catalog.lyrics.read", _("Catalog: Lyrics")
    RESTRICTED_LYRICS_READ = (
        "catalog.lyrics.restricted",
        _("Catalog: Restricted lyrics"),
    )


def normalize_api_key_scopes(raw_scopes: ty.Iterable[str] | None) -> list[str]:
    """Return unique, sorted, recognized Integration Client scopes."""

    normalized = sorted(
        {str(scope).strip() for scope in raw_scopes or [] if str(scope).strip()}
    )
    allowed = {choice.value for choice in APIKeyScope}
    invalid = [scope for scope in normalized if scope not in allowed]
    if invalid:
        raise ValidationError(
            _("Unknown API key scopes: %(scopes)s")
            % {"scopes": ", ".join(invalid)}
        )
    return normalized


class IntegrationApiKey(BaseModel):
    """Hashed credential issued once to an Integration Client."""

    name = models.CharField(max_length=150)
    key_prefix = models.CharField(max_length=32, unique=True, editable=False)
    hashed_key = models.CharField(max_length=128, editable=False)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    expires_on = models.DateTimeField(null=True, blank=True)
    revoked_on = models.DateTimeField(null=True, blank=True)
    last_used_on = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_api_keys",
    )
    rotated_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rotated_api_keys",
    )
    notes = models.TextField(blank=True)

    class Meta(TypedModelMeta):
        verbose_name = _("API key")
        verbose_name_plural = _("API keys")

    def __str__(self) -> str:
        return f"{self.name} ({self.key_prefix})"

    @property
    def is_revoked(self) -> bool:
        return self.revoked_on is not None

    @property
    def is_expired(self) -> bool:
        return self.expires_on is not None and self.expires_on <= timezone.now()

    @property
    def status(self) -> str:
        if self.is_revoked:
            return "revoked"
        if self.is_expired:
            return "expired"
        if not self.is_active:
            return "inactive"
        return "active"

    def clean(self) -> None:
        super().clean()
        self.name = " ".join(self.name.split()).strip()
        self.scopes = normalize_api_key_scopes(self.scopes)
        if self.revoked_on and self.is_active:
            self.is_active = False

    def revoke(self, *, timestamp=None) -> None:
        """Mark the credential revoked without saving it."""

        self.is_active = False
        self.revoked_on = timestamp or timezone.now()
