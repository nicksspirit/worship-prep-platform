import typing as t

from django.contrib import auth
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta

from apps.common.db.validators import NoWhitespaceValidator
from apps.common.models import BaseModel


class UserManager(BaseUserManager):
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

        user: "User" = self.model(email=email, **extra_fields)
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
        obj: t.Optional["User"] = None,
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

        if isinstance(backend_, ModelBackend):
            qs = backend_.with_perm(
                perm,
                is_active=is_active,
                include_superusers=include_superusers,
                obj=obj,
            )

            return t.cast(QuerySet["User"], qs)

        return self.none()


class User(AbstractUser, BaseModel):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = [
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

    objects: DjangoUserManager["User"] = t.cast(DjangoUserManager["User"], UserManager())

    class Meta(AbstractUser.Meta, TypedModelMeta):
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        swappable = "AUTH_USER_MODEL"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __str__(self) -> str:
        return f"{self.full_name} ({self.email})"

    def clean(self):
        super().clean()
        self.email = self.email.lower().strip()
