from uuid import uuid4

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.song_carts.admin_views import (
    ConfirmSubmissionView,
    RejectSubmissionView,
    ReplySubmissionView,
    RetrySubmissionEmailsView,
)
from apps.song_carts.models import SongCart, SongCartItem
from apps.song_carts.services import is_technical_team, read_submission_for_admin


class SongCartItemInline(TabularInline):
    model = SongCartItem
    fields = ("song_reference", "section", "title", "authors", "song_uid")
    readonly_fields = fields
    extra = 0
    can_delete = False

    @admin.display(description="Song reference")
    def song_reference(self, obj):
        return f"#{obj.pk}"

    def has_add_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SongCart)
class SongCartAdmin(ModelAdmin):
    list_display = (
        "service_date", "owner", "status", "submitted_at", "confirmed_at",
    )
    list_filter = ("status", "service_date")
    search_fields = ("owner__email", "songs__title")
    readonly_fields = (
        "owner", "service_date", "status", "created_at", "submitted_at",
        "confirmed_at", "confirmed_by", "rejected_at", "rejected_by",
        "rejection_reason",
    )
    fields = readonly_fields
    inlines = [SongCartItemInline]
    actions = None
    change_form_outer_after_template = "admin/song_carts/submission_review.html"

    def get_custom_urls(self):
        return (
            (
                "<uuid:cart_id>/confirm/", "song_carts_songcart_confirm",
                ConfirmSubmissionView.as_view(),
            ),
            (
                "<uuid:cart_id>/reject/", "song_carts_songcart_reject",
                RejectSubmissionView.as_view(),
            ),
            (
                "<uuid:cart_id>/reply/", "song_carts_songcart_reply",
                ReplySubmissionView.as_view(),
            ),
            (
                "<uuid:cart_id>/retry-emails/", "song_carts_songcart_retry_emails",
                RetrySubmissionEmailsView.as_view(),
            ),
        )

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None,
    ):
        if obj is not None:
            context.update(
                submission=read_submission_for_admin(obj.id, user=request.user),
                can_review_submission=is_technical_team(request.user),
                reply_request_id=uuid4(),
            )
        return super().render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj,
        )

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

