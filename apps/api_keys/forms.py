import ast
from datetime import datetime, time

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from unfold.widgets import UnfoldAdminTextareaWidget

from .models import APIKeyScope, IntegrationApiKey


class FlexibleMultipleChoiceField(forms.MultipleChoiceField):
    """Accept list, serialized-list, or comma-separated admin form values."""

    def to_python(self, value):
        if not value:
            return []

        raw_values = [value] if isinstance(value, str) else list(value)
        normalized_values: list[str] = []
        for raw_value in raw_values:
            stripped_value = str(raw_value).strip()
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
            normalized_values.extend(
                item.strip() for item in stripped_value.split(",") if item.strip()
            )
        return super().to_python(normalized_values)


class IntegrationApiKeyAdminForm(forms.ModelForm):
    """Admin form for issuing and updating Integration Client credentials."""

    scopes = FlexibleMultipleChoiceField(
        choices=APIKeyScope.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_("Select the scopes this Integration Client may use."),
    )
    expires_on = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=_("Optional expiration date, inclusive through the end of that day."),
    )

    class Meta:
        model = IntegrationApiKey
        fields = ["name", "scopes", "expires_on", "notes"]
        widgets = {
            "notes": UnfoldAdminTextareaWidget(
                attrs={"rows": 4, "class": "min-h-32 border-base-300"}
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scopes"].initial = list(self.instance.scopes or [])
        if self.instance.pk and self.instance.expires_on is not None:
            self.fields["expires_on"].initial = timezone.localtime(
                self.instance.expires_on
            ).date()

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
