from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from invitations.exceptions import AlreadyAccepted, AlreadyInvited, UserRegisteredEmail
from invitations.forms import CleanEmailMixin
from invitations.utils import (
    get_invitation_admin_add_form,
    get_invitation_admin_change_form,
    get_invitation_model,
)

from .forms import UserChangeForm, UserCreationForm
from .models import AccessLevel, InvitationRequest, RequestStatus, User

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
