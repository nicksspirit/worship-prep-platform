"""Catalog Administration forms."""

from django import forms
from django.core.exceptions import ValidationError
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.catalog.models import CatalogSongRights
from apps.catalog.rights import ALLOWED_BASES


class CatalogSongRightsAdminForm(forms.ModelForm):
    """Require policy-valid evidence for every Lyrics Rights Status change."""

    class Meta:
        model = CatalogSongRights
        fields = ["status", "basis", "evidence_reference", "explanation"]
        widgets = {
            "evidence_reference": UnfoldAdminTextareaWidget(attrs={"rows": 3}),
            "explanation": UnfoldAdminTextareaWidget(attrs={"rows": 5}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        basis = cleaned_data.get("basis")
        if status and basis and basis not in ALLOWED_BASES[status]:
            self.add_error(
                "basis",
                ValidationError(
                    "The evidence basis does not establish the selected status."
                ),
            )
        for field in ("evidence_reference", "explanation"):
            value = str(cleaned_data.get(field, "")).strip()
            cleaned_data[field] = value
            if not value:
                self.add_error(field, "This field is required for a rights decision.")
        return cleaned_data
