from typing import Any, cast

from allauth.account.views import LoginView
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from .templates import RenderableTemplate, SignInPage


class HomePageView(View):
    def get(self, request, *args, **kwargs) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("schedule_landing")

        return redirect_to_login(request.get_full_path())


class SignInView(LoginView):
    def render_to_response(self, context: dict[str, Any], **response_kwargs) -> HttpResponse:
        form = context["form"]
        page = cast(
            RenderableTemplate,
            SignInPage(
                title="Sign In",
                login_form=form,
                login_value=form.data.get("login") or None,
                signup_url=cast(str | None, context.get("signup_url")),
                reset_password_url=self.passthrough_next_url(reverse("account_reset_password")),
                google_login_url=reverse("google_login"),
                next_value=cast(str | None, context.get("redirect_field_value")),
                redirect_field_name=self.redirect_field_name,
            ),
        )
        return page.render(self.request)
