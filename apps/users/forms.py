import ast
from datetime import datetime, time

from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from unfold.widgets import UnfoldAdminTextareaWidget

from .models import APIKeyScope, IntegrationApiKey, InvitationRequest, User


class FlexibleMultipleChoiceField(forms.MultipleChoiceField):
    """Accept either a list payload or a single serialized string value."""

    def to_python(self, value):
        if not value:
            return []

        raw_values = [value] if isinstance(value, str) else list(value)
        normalized_values: list[str] = []

        for raw_value in raw_values:
            if not isinstance(raw_value, str):
                normalized_values.append(str(raw_value))
                continue

            stripped_value = raw_value.strip()
            if not stripped_value:
                continue

            if stripped_value.startswith("[") and stripped_value.endswith("]"):
                try:
                    parsed_value = ast.literal_eval(stripped_value)
                except (SyntaxError, ValueError):
                    parsed_value = None

                if isinstance(parsed_value, (list, tuple)):
                    normalized_values.extend(
                        str(item).strip() for item in parsed_value if str(item).strip()
                    )
                    continue

            if "," in stripped_value:
                normalized_values.extend(
                    item.strip() for item in stripped_value.split(",") if item.strip()
                )
                continue

            normalized_values.append(stripped_value)

        return super().to_python(normalized_values)


class UserCreationForm(forms.ModelForm):
    """A form for creating new users. 
    Includes all the required fields, plus a repeated password for confirmation.
    """

    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["email"]

    def clean_password2(self):
        """Check that the two password entries match."""

        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError(_("Passwords don't match"))

        return password2

    def save(self, commit=True):
        """Save the provided password in hashed format."""

        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        if commit: user.save()  # noqa: E701

        return user


class InvitationRequestForm(forms.ModelForm):
    """Public form for requesting an invitation to create an account."""

    class Meta:
        model = InvitationRequest
        fields = ["email", "first_name", "last_name", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if InvitationRequest.objects.filter(email=email).exists():
            raise ValidationError(
                _("An invitation request for this email is already on file."),
            )
        return email

    def clean_first_name(self) -> str:
        return self.cleaned_data["first_name"].strip()

    def clean_last_name(self) -> str:
        return self.cleaned_data["last_name"].strip()

    def save(self, commit: bool = True) -> InvitationRequest:
        instance: InvitationRequest = super().save(commit=False)
        instance.email = instance.email.strip().lower()
        if commit:
            instance.save()
        return instance


class UserChangeForm(forms.ModelForm):
    """A form for updating users. 
    Includes all the fields on the user, but replaces the password field with admin's
    disabled password hash display field.
    """

    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = ["email", "password", "is_active", "is_staff"]


class IntegrationApiKeyAdminForm(forms.ModelForm):
    """Admin form for issuing and updating integration API keys."""

    scopes = FlexibleMultipleChoiceField(
        choices=APIKeyScope.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_("Select the API scopes this key should be allowed to use."),
    )
    expires_on = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=_("Optional expiration date. Keys remain valid until the end of this day."),
    )

    class Meta:
        model = IntegrationApiKey
        fields = ["name", "scopes", "expires_on", "notes"]
        widgets = {
            "notes": UnfoldAdminTextareaWidget(
                attrs={
                    "rows": 4,
                    "class": "min-h-32 border-base-300",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scopes"].initial = list(self.instance.scopes or [])
        if self.instance.pk and self.instance.expires_on is not None:
            self.fields["expires_on"].initial = timezone.localtime(self.instance.expires_on).date()

    def clean_expires_on(self):
        expires_on = self.cleaned_data.get("expires_on")
        if expires_on is None:
            return None

        if expires_on < timezone.localdate():
            raise ValidationError(_("Expiration date cannot be in the past."))

        return timezone.make_aware(datetime.combine(expires_on, time.max))

    def save(self, commit=True):
        instance: IntegrationApiKey = super().save(commit=False)
        instance.scopes = self.cleaned_data["scopes"]
        instance.expires_on = self.cleaned_data.get("expires_on")
        if commit:
            instance.save()
        return instance
