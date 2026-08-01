from typing import Any, cast

from allauth.account.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from .forms import InvitationRequestForm
from .templates import RenderableTemplate, RequestInvitationPage, SignInPage


class HomePageView(View):
    def get(self, request, *args, **kwargs) -> HttpResponse:
        return redirect("account_login")


class SignInView(LoginView):
    def render_to_response(self, context: dict[str, Any], **response_kwargs) -> HttpResponse:
        form = context["form"]
        page = cast(
            RenderableTemplate,
            SignInPage(
                title="Sign In",
                login_form=form,
                login_value=form.data.get("login") or None,
                request_invitation_url=reverse("request_invitation"),
                reset_password_url=self.passthrough_next_url(reverse("account_reset_password")),
                google_login_url=reverse("google_login"),
                next_value=cast(str | None, context.get("redirect_field_value")),
                redirect_field_name=self.redirect_field_name,
            ),
        )
        return page.render(self.request)


class RequestInvitationView(View):
    """Public form to request an invitation (stored for staff review)."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return self._render(request, InvitationRequestForm(), success=False)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        form = InvitationRequestForm(request.POST)
        if form.is_valid():
            form.save()
            return self._render(request, InvitationRequestForm(), success=True)

        return self._render(request, form, success=False)

    def _render(
        self,
        request: HttpRequest,
        form: InvitationRequestForm,
        *,
        success: bool,
    ) -> HttpResponse:
        non_field = [str(e) for e in form.non_field_errors()]
        field_errors = {k: v[0] for k, v in form.errors.items() if k != "__all__"}
        page = cast(
            RenderableTemplate,
            RequestInvitationPage(
                title="Request Invitation",
                success=success,
                sign_in_url=reverse("account_login"),
                non_field_errors=non_field,
                email=form.data.get("email", ""),
                first_name=form.data.get("first_name", ""),
                last_name=form.data.get("last_name", ""),
                message=form.data.get("message", ""),
                field_errors=field_errors,
            ),
        )
        return page.render(request)
