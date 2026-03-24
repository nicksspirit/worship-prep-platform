import typing as ty

from django.contrib import auth
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta

from apps.common.db.validators import NoWhitespaceValidator
from apps.common.models import BaseModel

_T = ty.TypeVar("_T", bound="models.Model")


class AccessLevel(models.TextChoices):
    """Access tier granted when an invitation request is approved."""

    MEMBER = "member", _("Member")
    ADMIN = "admin", _("Admin")


class RequestStatus(models.TextChoices):
    """Lifecycle state for a public invitation request."""

    PENDING = "pending", _("Pending")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")


class APIKeyScope(models.TextChoices):
    """Scopes available to machine-to-machine API keys."""

    SCHEDULES_READ = "schedules.read", _("Schedules: Read")
    SCHEDULES_WRITE = "schedules.write", _("Schedules: Write")
    SONGS_WRITE = "songs.write", _("Songs: Write")
    PREVIEW_READ = "preview.read", _("Preview: Read")


def normalize_api_key_scopes(raw_scopes: ty.Iterable[str] | None) -> list[str]:
    """Normalize a collection of API key scopes."""

    normalized = sorted(
        {
            str(scope).strip()
            for scope in raw_scopes or []
            if str(scope).strip()
        }
    )
    allowed = {choice.value for choice in APIKeyScope}
    invalid = [scope for scope in normalized if scope not in allowed]
    if invalid:
        raise ValidationError(
            _("Unknown API key scopes: %(scopes)s")
            % {"scopes": ", ".join(invalid)}
        )
    return normalized


class InvitationRequest(BaseModel):
    """Public request for an account; staff approve and send a django-invitations invite."""

    email = models.EmailField(max_length=254, unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
        db_index=True,
    )
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        blank=True,
        default="",
    )
    reviewed_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitation_requests_reviewed",
    )
    invitation = models.OneToOneField(
        "invitations.Invitation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitation_request",
    )

    class Meta(TypedModelMeta):
        verbose_name = _("Invitation request")
        verbose_name_plural = _("Invitation requests")

    def __str__(self) -> str:
        return f"{self.email} ({self.get_status_display()})"


class HasMeta(ty.Protocol):
    Meta: ty.ClassVar[ty.Any]


class UserManager(BaseUserManager[_T]):
    """A Manager for the User model. This mimics the UserManager in django.contrib.auth.models.UserManager"""

    use_in_migrations = True

    def _create_user(self, email: str, password: str, **extra_fields) -> "User":
        """
        Create and save a user with the given email, and password.
        """

        if not email:
            raise ValueError("The user's email must be set")

        try:
            validate_email(email)
        except ValidationError:
            raise ValueError("The user's email address is invalid")

        user: "User" = ty.cast("User", self.model(email=email, **extra_fields))
        user.set_password(password)
        user.save()

        return user

    def create_user(self, email: str, password: str, **extra_fields) -> "User":
        """
        Create a user with the given email and password.

        Args:
            email: The email of the user.
            password: The password of the user.
            **extra_fields: Additional fields to set on the user.
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields
    ) -> "User":
        """
        Create a superuser with the given email and password.

        Args:
            email: The email of the superuser.
            password: The password of the superuser.
            **extra_fields: Additional fields to set on the superuser.
        
        Returns:
            The created superuser.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if password is None:
            raise ValueError("Password is required")

        extra_field_checks = [
            ("is_staff", "Superuser must have is_staff=True."),
            ("is_superuser", "Superuser must have is_superuser=True."),
        ]

        for field, error_message in extra_field_checks:
            if extra_fields.get(field) is not True:
                raise ValueError(error_message)

        return self._create_user(email, password, **extra_fields)

    def with_perm(
        self,
        perm: str,
        is_active: bool = True,
        include_superusers: bool = True,
        backend: str | None = None,
        obj: ty.Optional["User"] = None,
    ) -> QuerySet["User"]:
        """Return a QuerySet of all users with the given permission.

        Args:
            perm: The permission to check for.
            is_active: Whether to include inactive users.
            include_superusers: Whether to include superusers.
            backend: The backend to use.
            obj: The object to check the permission on.

        Returns:
            A QuerySet of all users with the given permission.

        Raises:
            ValueError: If multiple authentication backends are configured and the `backend` argument is not provided.
            TypeError: If the `backend` argument is not a dotted import path string.
        """
        if backend is None:
            backends = auth.get_backends()

            if len(backends) > 1:
                raise ValueError(
                    "You have multiple authentication backends configured and "
                    "therefore must provide the `backend` argument."
                )

            backend_ = backends[0]
        else:
            backend_ = auth.load_backend(backend)

        from django.contrib.auth.backends import ModelBackend

        qs = self.none()

        if isinstance(backend_, ModelBackend):
            qs = backend_.with_perm(
                perm,
                is_active=is_active,
                include_superusers=include_superusers,
                obj=obj,
            )

        return ty.cast(QuerySet["User"], qs)


class User(AbstractUser, BaseModel):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = [
        "first_name",
        "last_name",
    ]

    email = models.EmailField(
        _("email address"),
        max_length=254,
        unique=True,
        db_index=True,
        error_messages={
            "unique": _("A user with that email address already exists."),
        },
    )
    first_name = models.CharField(
        _("first name"), max_length=150, blank=True, validators=[NoWhitespaceValidator()]
    )
    last_name = models.CharField(
        _("last name"), max_length=150, blank=True, validators=[NoWhitespaceValidator()]
    )
    username = None

    objects: UserManager["User"] = UserManager()
    AbstractUserMeta = ty.cast(HasMeta, AbstractUser)

    class Meta(AbstractUserMeta.Meta, TypedModelMeta):
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        swappable = "AUTH_USER_MODEL"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def avatar_url(self) -> str | None:
        social_account = self.socialaccount_set.first()
        if social_account and social_account.extra_data:
            return social_account.extra_data.get("picture")
        return None

    def clean(self):
        super().clean()
        self.email = self.email.lower().strip()

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"


class IntegrationApiKey(BaseModel):
    """Database-backed API key for machine-to-machine integrations."""

    name = models.CharField(max_length=150)
    key_prefix = models.CharField(max_length=32, unique=True, editable=False)
    hashed_key = models.CharField(max_length=128, editable=False)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    expires_on = models.DateTimeField(null=True, blank=True)
    revoked_on = models.DateTimeField(null=True, blank=True)
    last_used_on = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "users.User",
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

    def clean(self):
        super().clean()
        self.name = " ".join(self.name.split()).strip()
        self.scopes = normalize_api_key_scopes(self.scopes)
        if self.revoked_on and self.is_active:
            self.is_active = False

    def revoke(self, *, timestamp=None):
        """Revoke the API key in-memory."""

        self.is_active = False
        self.revoked_on = timestamp or timezone.now()
