from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import IntegrityError
from django.db.models import TextField
from django.db.models.functions import Cast
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import action, display

from invitations.exceptions import AlreadyAccepted, AlreadyInvited, UserRegisteredEmail
from invitations.forms import CleanEmailMixin
from invitations.utils import (
    get_invitation_admin_add_form,
    get_invitation_admin_change_form,
    get_invitation_model,
)

from .api_keys import generate_api_key_material, revoke_api_key, rotate_api_key
from .forms import IntegrationApiKeyAdminForm, UserChangeForm, UserCreationForm
from .models import AccessLevel, APIKeyScope, IntegrationApiKey, InvitationRequest, RequestStatus, User

Invitation = get_invitation_model()
InvitationAdminAddForm = get_invitation_admin_add_form()
InvitationAdminChangeForm = get_invitation_admin_change_form()

if admin.site.is_registered(Invitation):
    admin.site.unregister(Invitation)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = ["email", "is_staff"]
    list_filter = ["is_staff"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Personal info", {"fields": ["first_name", "last_name"]}),
        ("Permissions", {"fields": ["is_staff"]}),
    ]
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": ["email", "first_name", "last_name", "password1", "password2"],
            },
        ),
    ]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]
    filter_horizontal = []


@admin.register(InvitationRequest)
class InvitationRequestAdmin(ModelAdmin):
    list_display = [
        "email",
        "display_name",
        "status_display",
        "access_level_display",
        "created_on",
    ]
    list_filter = ["status", "access_level"]
    search_fields = ["email", "first_name", "last_name", "message"]
    readonly_fields = [
        "email",
        "first_name",
        "last_name",
        "message",
        "created_on",
        "updated_on",
        "invitation",
        "reviewed_by",
    ]
    ordering = ["-created_on"]
    actions = ["approve_as_member", "approve_as_admin", "reject_requests"]

    @display(
        description=_("Name"),
    )
    def display_name(self, obj: InvitationRequest) -> str:
        return f"{obj.first_name} {obj.last_name}".strip()

    @display(
        description=_("Status"),
        label={
            "Pending": "warning",
            "Approved": "success",
            "Rejected": "danger",
        },
    )
    def status_display(self, obj: InvitationRequest) -> str:
        return str(obj.get_status_display())

    @display(
        description=_("Access level"),
        label={
            "Member": "info",
            "Admin": "warning",
        },
    )
    def access_level_display(self, obj: InvitationRequest) -> str:
        if not obj.access_level:
            return "—"
        return str(obj.get_access_level_display())

    @admin.action(description=_("Approve and send invitation (Member)"))
    def approve_as_member(self, request, queryset):
        self._approve_and_send(request, queryset, AccessLevel.MEMBER)

    @admin.action(description=_("Approve and send invitation (Admin)"))
    def approve_as_admin(self, request, queryset):
        self._approve_and_send(request, queryset, AccessLevel.ADMIN)

    @admin.action(description=_("Reject selected requests"))
    def reject_requests(self, request, queryset):
        count = 0
        for obj in queryset.filter(status=RequestStatus.PENDING):
            obj.status = RequestStatus.REJECTED
            obj.reviewed_by = request.user
            obj.save(update_fields=["status", "reviewed_by", "updated_on"])
            count += 1
        self.message_user(
            request,
            _("Rejected %(count)d request(s).") % {"count": count},
            level=messages.SUCCESS,
        )

    def save_model(self, request, obj, form, change):
        original_status = None
        original_access_level = ""
        if change:
            original = InvitationRequest.objects.get(pk=obj.pk)
            original_status = original.status
            original_access_level = original.access_level

        if obj.status != RequestStatus.PENDING and (
            not change
            or obj.status != original_status
            or obj.access_level != original_access_level
        ):
            obj.reviewed_by = request.user

        super().save_model(request, obj, form, change)

    def _approve_and_send(self, request, queryset, access_level: str) -> None:
        mixin = CleanEmailMixin()
        sent = 0
        for obj in queryset.filter(status=RequestStatus.PENDING):
            try:
                mixin.validate_invitation(obj.email)
            except AlreadyInvited:
                self.message_user(
                    request,
                    _("Skipped %(email)s: already invited.") % {"email": obj.email},
                    level=messages.WARNING,
                )
                continue
            except AlreadyAccepted:
                self.message_user(
                    request,
                    _("Skipped %(email)s: invite already accepted.") % {"email": obj.email},
                    level=messages.WARNING,
                )
                continue
            except UserRegisteredEmail:
                self.message_user(
                    request,
                    _("Skipped %(email)s: user already registered.") % {"email": obj.email},
                    level=messages.WARNING,
                )
                continue

            try:
                inv = Invitation.create(email=obj.email)
            except IntegrityError:
                self.message_user(
                    request,
                    _("Skipped %(email)s: could not create invitation.") % {"email": obj.email},
                    level=messages.ERROR,
                )
                continue

            inv.inviter = request.user
            inv.save()
            inv.send_invitation(request)

            obj.status = RequestStatus.APPROVED
            obj.access_level = access_level
            obj.reviewed_by = request.user
            obj.invitation = inv
            obj.save(
                update_fields=[
                    "status",
                    "access_level",
                    "reviewed_by",
                    "invitation",
                    "updated_on",
                ],
            )
            sent += 1

        self.message_user(
            request,
            _("Sent %(count)d invitation(s).") % {"count": sent},
            level=messages.SUCCESS,
        )


@admin.register(Invitation)
class InvitationAdmin(ModelAdmin):
    list_display = ("email", "sent", "accepted", "created")
    list_filter = ("sent", "accepted")
    raw_id_fields = ("inviter",)
    readonly_fields = ("key", "sent", "accepted", "created")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("email", "key", "sent", "accepted", "created", "inviter")
        return self.readonly_fields

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            kwargs["form"] = InvitationAdminChangeForm
        else:
            kwargs["form"] = InvitationAdminAddForm
            kwargs["form"].user = request.user
            kwargs["form"].request = request
        return super().get_form(request, obj, **kwargs)


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
            return redirect("admin:users_integrationapikey_changelist")

        revoke_api_key(api_key)
        self.message_user(
            request,
            _("Revoked API key %(prefix)s.") % {"prefix": api_key.key_prefix},
            level=messages.SUCCESS,
        )
        return redirect("admin:users_integrationapikey_changelist")

    @action(description="Rotate API key", url_path="rotate")
    def rotate_selected_key(self, request, object_id: int):
        api_key = self.get_object(request, object_id)
        if api_key is None:
            self.message_user(request, _("API key not found."), level=messages.ERROR)
            return redirect("admin:users_integrationapikey_changelist")

        replacement, plaintext_key = rotate_api_key(api_key, rotated_by=request.user)
        self._message_plaintext_key(
            request,
            plaintext_key,
            _("API key rotated. Copy the replacement key now."),
        )
        return redirect(
            reverse("admin:users_integrationapikey_change", args=[replacement.pk])
        )
