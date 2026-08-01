from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import InvitationRequest, User


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

        if commit: user.save()

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
