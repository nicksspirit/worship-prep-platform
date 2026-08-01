from typing import NamedTuple, Protocol

from allauth.account.forms import LoginForm
from django.http import HttpRequest
from django.template.response import TemplateResponse
from reactivated import template


class RenderableTemplate(Protocol):
    """Protocol for @template-decorated classes that gain a render method at runtime."""

    def render(self, request: HttpRequest) -> TemplateResponse: ...


@template
class SignInPage(NamedTuple):
    title: str
    login_form: LoginForm
    login_value: str | None
    request_invitation_url: str
    reset_password_url: str
    google_login_url: str
    next_value: str | None
    redirect_field_name: str


@template
class RequestInvitationPage(NamedTuple):
    title: str
    success: bool
    sign_in_url: str
    non_field_errors: list[str]
    email: str
    first_name: str
    last_name: str
    message: str
    field_errors: dict[str, str]