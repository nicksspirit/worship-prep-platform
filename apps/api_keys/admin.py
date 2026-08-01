from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db.models import TextField
from django.db.models.functions import Cast
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import action

from .forms import IntegrationApiKeyAdminForm
from .models import APIKeyScope, IntegrationApiKey
from .services import generate_api_key_material, revoke_api_key, rotate_api_key


class APIKeyStatusFilter(SimpleListFilter):
    title = _("status")
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            ("active", _("Active")),
            ("inactive", _("Inactive")),
            ("revoked", _("Revoked")),
            ("expired", _("Expired")),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        now = timezone.now()
        if value == "active":
            return queryset.filter(is_active=True, revoked_on__isnull=True).exclude(
                expires_on__lte=now
            )
        if value == "inactive":
            return queryset.filter(is_active=False, revoked_on__isnull=True)
        if value == "revoked":
            return queryset.filter(revoked_on__isnull=False)
        if value == "expired":
            return queryset.filter(expires_on__lte=now, revoked_on__isnull=True)
        return queryset


class APIKeyScopeFilter(SimpleListFilter):
    title = _("scope")
    parameter_name = "scope"

    def lookups(self, request, model_admin):
        return APIKeyScope.choices

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        return queryset.annotate(
            scopes_text=Cast("scopes", output_field=TextField())
        ).filter(scopes_text__icontains=f'"{value}"')


@admin.register(IntegrationApiKey)
class IntegrationApiKeyAdmin(ModelAdmin):
    form = IntegrationApiKeyAdminForm
    list_display = [
        "name",
        "key_prefix",
        "status_display",
        "scope_display",
        "created_by",
        "last_used_on",
        "expires_on",
        "created_on",
    ]
    list_filter = [APIKeyStatusFilter, APIKeyScopeFilter, "created_by"]
    search_fields = ["name", "key_prefix", "notes"]
    ordering = ["-created_on"]
    actions = ["revoke_selected"]
    actions_detail = ["rotate_selected_key", "revoke_selected_key"]
    actions_row = ["rotate_selected_key", "revoke_selected_key"]
    readonly_fields = [
        "status_display",
        "key_prefix",
        "created_by",
        "rotated_from",
        "last_used_on",
        "revoked_on",
        "created_on",
        "updated_on",
    ]

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                (
                    None,
                    {
                        "fields": [
                            "name",
                            "scopes",
                            "expires_on",
                            "notes",
                        ]
                    },
                ),
            )
        return (
            (
                None,
                {
                    "fields": [
                        "name",
                        "status_display",
                        "scopes",
                        "expires_on",
                        "notes",
                    ]
                },
            ),
            (
                _("Metadata"),
                {
                    "classes": ["collapse"],
                    "fields": [
                        "key_prefix",
                        "created_by",
                        "rotated_from",
                        "last_used_on",
                        "revoked_on",
                        "created_on",
                        "updated_on",
                    ],
                },
            ),
        )

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Status"))
    def status_display(self, obj: IntegrationApiKey) -> str:
        return obj.status

    @admin.display(description=_("Scopes"))
    def scope_display(self, obj: IntegrationApiKey) -> str:
        scope_labels = dict(APIKeyScope.choices)
        return ", ".join(
            str(scope_labels.get(scope, scope)) for scope in obj.scopes
        ) or "—"

    def save_model(self, request, obj, form, change):
        plaintext_key = None
        if not change:
            material = generate_api_key_material()
            obj.key_prefix = material.key_prefix
            obj.hashed_key = material.hashed_key
            obj.created_by = request.user
            plaintext_key = material.plaintext_key

        super().save_model(request, obj, form, change)

        if plaintext_key:
            self._message_plaintext_key(
                request,
                plaintext_key,
                _("API key created. Copy it now because it will not be shown again."),
            )

    def _message_plaintext_key(self, request, plaintext_key: str, heading: str) -> None:
        self.message_user(
            request,
            format_html(
                "{}<br><strong>{}</strong><br><code>{}</code>",
                heading,
                _("Plaintext API key"),
                plaintext_key,
            ),
            level=messages.WARNING,
        )

    @admin.action(description=_("Revoke selected API keys"))
    def revoke_selected(self, request, queryset):
        count = 0
        for api_key in queryset.filter(revoked_on__isnull=True):
            revoke_api_key(api_key)
            count += 1
        self.message_user(
            request,
            _("Revoked %(count)d API key(s).") % {"count": count},
            level=messages.SUCCESS,
        )

    @action(description="Revoke API key", url_path="revoke")
    def revoke_selected_key(self, request, object_id: int):
        api_key = self.get_object(request, object_id)
        if api_key is None:
            self.message_user(request, _("API key not found."), level=messages.ERROR)
            return redirect("admin:api_keys_integrationapikey_changelist")

        revoke_api_key(api_key)
        self.message_user(
            request,
            _("Revoked API key %(prefix)s.") % {"prefix": api_key.key_prefix},
            level=messages.SUCCESS,
        )
        return redirect("admin:api_keys_integrationapikey_changelist")

    @action(description="Rotate API key", url_path="rotate")
    def rotate_selected_key(self, request, object_id: int):
        api_key = self.get_object(request, object_id)
        if api_key is None:
            self.message_user(request, _("API key not found."), level=messages.ERROR)
            return redirect("admin:api_keys_integrationapikey_changelist")

        replacement, plaintext_key = rotate_api_key(api_key, rotated_by=request.user)
        self._message_plaintext_key(
            request,
            plaintext_key,
            _("API key rotated. Copy the replacement key now."),
        )
        return redirect(
            reverse("admin:api_keys_integrationapikey_change", args=[replacement.pk])
        )
