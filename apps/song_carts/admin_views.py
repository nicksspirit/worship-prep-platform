from uuid import UUID

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views import View

from apps.song_carts.forms import RejectionForm, SubmissionReplyForm
from apps.song_carts.models import SongCart
from apps.song_carts.services import (
    confirm_submission,
    reject_submission,
    retry_submission_emails,
    send_submission_reply,
)


class ConfirmSubmissionView(View):
    """Acknowledge an opened admin detail through a CSRF-protected request."""

    def post(self, request: HttpRequest, cart_id: UUID, **kwargs) -> HttpResponse:
        try:
            confirm_submission(cart_id, user=request.user)
        except SongCart.DoesNotExist as exc:
            raise Http404("Submission not found.") from exc
        except ValidationError as exc:
            return HttpResponse(" ".join(exc.messages), status=400)
        return HttpResponse(status=204)


class RejectSubmissionView(View):
    """Bind a rejection reason and invoke the team review service."""

    def post(self, request: HttpRequest, cart_id: UUID, **kwargs) -> HttpResponse:
        form = RejectionForm(request.POST)
        if form.is_valid():
            try:
                reject_submission(cart_id, form.cleaned_data["reason"], user=request.user)
            except SongCart.DoesNotExist as exc:
                raise Http404("Submission not found.") from exc
            except ValidationError as exc:
                form.add_error("reason", exc)
            else:
                messages.success(
                    request, "Submission rejected. Check email delivery below.",
                )
        if form.errors:
            messages.error(request, " ".join(form.errors.get("reason", [])))
        return redirect("admin:song_carts_songcart_change", object_id=cart_id)


class ReplySubmissionView(View):
    """Send one email response without posting an administrator comment."""

    def post(self, request: HttpRequest, cart_id: UUID, **kwargs) -> HttpResponse:
        form = SubmissionReplyForm(request.POST)
        if form.is_valid():
            try:
                sent = send_submission_reply(
                    cart_id, form.cleaned_data["body"], user=request.user,
                    request_id=form.cleaned_data["request_id"],
                )
            except SongCart.DoesNotExist as exc:
                raise Http404("Submission not found.") from exc
            except ValidationError as exc:
                form.add_error("body", exc)
            else:
                if sent:
                    messages.success(
                        request, "Email response accepted by the email backend.",
                    )
                else:
                    messages.warning(
                        request,
                        "Email response saved, but delivery failed. Retry it below.",
                    )
        if form.errors:
            messages.error(request, " ".join(
                str(error) for errors in form.errors.values() for error in errors
            ))
        return redirect("admin:song_carts_songcart_change", object_id=cart_id)


class RetrySubmissionEmailsView(View):
    """Retry saved email failures without changing submission state."""

    def post(self, request: HttpRequest, cart_id: UUID, **kwargs) -> HttpResponse:
        try:
            sent, failed = retry_submission_emails(cart_id, user=request.user)
        except SongCart.DoesNotExist as exc:
            raise Http404("Submission not found.") from exc
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.add_message(
                request, messages.WARNING if failed else messages.SUCCESS,
                f"Email retries accepted: {sent}. Failed: {failed}.",
            )
        return redirect("admin:song_carts_songcart_change", object_id=cart_id)
