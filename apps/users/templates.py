from typing import NamedTuple, Protocol

from django.http import HttpRequest
from django.template.response import TemplateResponse

from allauth.account.forms import LoginForm
from reactivated import template


class RenderableTemplate(Protocol):
    """Protocol for @template-decorated classes that gain a render method at runtime."""

    def render(self, request: HttpRequest) -> TemplateResponse: ...


@template
class SignInPage(NamedTuple):
    title: str
    login_form: LoginForm
    login_value: str | None
    signup_url: str | None
    reset_password_url: str
    google_login_url: str
    next_value: str | None
    redirect_field_name: str