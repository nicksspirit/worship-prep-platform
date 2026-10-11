from typing import Literal, NamedTuple, Protocol, TypedDict

from allauth.account.forms import LoginForm, ResetPasswordForm, ResetPasswordKeyForm
from django.http import HttpRequest
from django.template.response import TemplateResponse
from reactivated import template


class RenderableTemplate(Protocol):
    """Protocol for @template-decorated classes that gain a render method at runtime."""

    def render(self, request: HttpRequest) -> TemplateResponse: ...


class SocialConnection(TypedDict):
    id: int
    provider: str
    name: str


class SocialProvider(TypedDict):
    name: str
    url: str


class AccountWidget(TypedDict):
    name: str
    is_hidden: bool
    value: str | bool | int | list[str] | None
    attrs: dict[str, str]
    type: str | None
    tag: str


class AccountFormField(TypedDict):
    label: str
    help_text: str | None
    help_items: list[str]
    required: bool
    widget: AccountWidget


class AccountForm(TypedDict):
    fields: dict[str, AccountFormField]
    errors: dict[str, list[str]]
    iterator: list[str]


class AccountEmailAddress(TypedDict):
    email: str
    verified: bool
    primary: bool


class ReauthenticationAlternative(TypedDict):
    description: str
    url: str


class RedirectField(TypedDict):
    name: str
    value: str


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
class PasswordResetPage(NamedTuple):
    title: str
    step: Literal["request", "sent", "set", "invalid", "complete"]
    form: ResetPasswordForm | ResetPasswordKeyForm | None
    sign_in_url: str
    reset_url: str


@template
class AccountConnectionsPage(NamedTuple):
    title: str
    email: str
    connections: list[SocialConnection]
    providers: list[SocialProvider]
    form_errors: dict[str, list[str]]


@template
class GoogleConnectPage(NamedTuple):
    title: str
    provider_name: str
    continue_url: str
    cancel_url: str


@template
class SocialLoginPage(NamedTuple):
    title: str
    provider_name: str
    action_url: str


@template
class SocialSignupPage(NamedTuple):
    title: str
    provider_name: str
    site_name: str
    form: AccountForm
    action_url: str
    redirect_field: RedirectField | None


@template
class SocialAuthStatusPage(NamedTuple):
    title: str
    state: Literal["cancelled", "error"]
    sign_in_url: str


@template
class AccountEmailStatesPage(NamedTuple):
    title: str
    page: Literal[
        "verification-sent",
        "confirm-email",
        "confirm-email-invalid",
        "inactive",
        "login-code",
    ]
    email: str | None = None
    user_display: str | None = None
    action_url: str | None = None
    email_url: str | None = None
    recipient: str | None = None
    verify_form: AccountForm | None = None
    can_resend: bool = False
    cancel_url: str | None = None
    logout_url: str | None = None
    login_url: str | None = None
    redirect_field: RedirectField | None = None
    can_change: bool = False
    change_form: AccountForm | None = None


@template
class AccountSettingsPage(NamedTuple):
    title: str
    page: Literal["emails", "change-password", "set-password", "reauthenticate", "signup"]
    form: AccountForm
    action_url: str
    email_addresses: list[AccountEmailAddress]
    can_add_email: bool
    reset_password_url: str | None
    redirect_field: RedirectField | None
    reauthentication_alternatives: list[ReauthenticationAlternative]
    google_login_url: str | None = None


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


@template
class InvitationRequiredPage(NamedTuple):
    """Invitation-only access notice shown when public signup is closed."""

    title: str
    request_invitation_url: str
    sign_in_url: str
