from html.parser import HTMLParser
from typing import Any, Literal, cast

from allauth.account import app_settings as account_app_settings
from allauth.account.utils import user_display
from allauth.account.views import (
    AccountInactiveView as AllauthAccountInactiveView,
)
from allauth.account.views import (
    ConfirmEmailVerificationCodeView as AllauthConfirmEmailVerificationCodeView,
)
from allauth.account.views import (
    ConfirmEmailView as AllauthConfirmEmailView,
)
from allauth.account.views import (
    ConfirmLoginCodeView as AllauthConfirmLoginCodeView,
)
from allauth.account.views import (
    EmailVerificationSentView as AllauthEmailVerificationSentView,
)
from allauth.account.views import (
    EmailView as AllauthEmailView,
)
from allauth.account.views import (
    LoginView,
    SignupView,
)
from allauth.account.views import (
    PasswordChangeView as AllauthPasswordChangeView,
)
from allauth.account.views import (
    PasswordResetDoneView as AllauthPasswordResetDoneView,
)
from allauth.account.views import (
    PasswordResetFromKeyDoneView as AllauthPasswordResetFromKeyDoneView,
)
from allauth.account.views import (
    PasswordResetFromKeyView as AllauthPasswordResetFromKeyView,
)
from allauth.account.views import (
    PasswordResetView as AllauthPasswordResetView,
)
from allauth.account.views import (
    PasswordSetView as AllauthPasswordSetView,
)
from allauth.account.views import (
    ReauthenticateView as AllauthReauthenticateView,
)
from allauth.socialaccount.adapter import get_adapter as get_socialaccount_adapter
from allauth.socialaccount.providers.google.views import (
    oauth2_login as google_oauth2_login,
)
from allauth.socialaccount.views import ConnectionsView as AllauthConnectionsView
from allauth.socialaccount.views import SignupView as AllauthSocialSignupView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from .forms import InvitationRequestForm
from .templates import (
    AccountConnectionsPage,
    AccountEmailStatesPage,
    AccountSettingsPage,
    GoogleConnectPage,
    InvitationRequiredPage,
    PasswordResetPage,
    RenderableTemplate,
    RequestInvitationPage,
    SignInPage,
    SocialAuthStatusPage,
    SocialLoginPage,
    SocialSignupPage,
)


class HomePageView(View):
    def get(self, request, *args, **kwargs) -> HttpResponse:
        if request.user.is_authenticated and request.user.is_staff:
            return redirect("admin:index")
        return redirect("catalog:search")


def _serialize_account_form(form: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    iterator: list[str] = []
    for name, field in form.fields.items():
        bound = form[name]
        widget = field.widget
        value = bound.value()
        help_text = str(bound.help_text) if bound.help_text else None
        help_items = _list_help_text(help_text)
        fields[name] = {
            "label": str(bound.label or name),
            "help_text": None if help_items else help_text,
            "help_items": help_items,
            "required": field.required,
            "widget": {
                "name": bound.html_name,
                "is_hidden": widget.is_hidden,
                "value": value,
                "attrs": {
                    key: str(widget.attrs[key])
                    for key in ("id", "placeholder")
                    if key in widget.attrs
                },
                "type": getattr(widget, "input_type", None),
                "tag": f"django.forms.widgets.{type(widget).__name__}",
            },
        }
        iterator.append(name)
    return {
        "fields": fields,
        "errors": {
            name: [str(error) for error in errors]
            for name, errors in form.errors.items()
        },
        "iterator": iterator,
    }


class _ListHelpTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[str] = []
        self._current: list[str] | None = None

    def handle_starttag(self, tag: str, attrs):
        if tag == "li" and self._current is None:
            self._current = []

    def handle_endtag(self, tag: str):
        if tag == "li" and self._current is not None:
            item = " ".join(" ".join(self._current).split())
            if item:
                self.items.append(item)
            self._current = None

    def handle_data(self, data: str):
        if self._current is not None:
            self._current.append(data)


def _list_help_text(help_text: str | None) -> list[str]:
    if not help_text or "<li" not in help_text:
        return []
    parser = _ListHelpTextParser()
    parser.feed(help_text)
    return parser.items


def _redirect_field(context: dict[str, Any]) -> dict[str, str] | None:
    value = context.get("redirect_field_value")
    if not value:
        return None
    return {"name": context["redirect_field_name"], "value": value}


def _account_settings_page(
    request,
    context,
    *,
    page: Literal["emails", "change-password", "set-password", "reauthenticate"],
    title: str,
) -> HttpResponse:
    addresses = [
        {
            "email": address.email,
            "verified": address.verified,
            "primary": address.primary,
        }
        for address in context.get("emailaddresses", [])
    ]
    redirect_value = context.get("redirect_field_value")
    page_data = cast(
        RenderableTemplate,
        AccountSettingsPage(
            title=title,
            page=page,
            form=_serialize_account_form(context["form"]),
            action_url=request.get_full_path(),
            email_addresses=addresses,
            can_add_email=bool(context.get("can_add_email", False)),
            reset_password_url=reverse("account_reset_password"),
            redirect_field=(
                {"name": context["redirect_field_name"], "value": redirect_value}
                if redirect_value
                else None
            ),
            reauthentication_alternatives=context.get(
                "reauthentication_alternatives", []
            ),
        ),
    )
    return page_data.render(request)


class AccountEmailView(AllauthEmailView):
    def render_to_response(self, context, **response_kwargs):
        return _account_settings_page(
            self.request, context, page="emails", title="Email Addresses"
        )


class AccountPasswordChangeView(AllauthPasswordChangeView):
    def render_to_response(self, context, **response_kwargs):
        return _account_settings_page(
            self.request, context, page="change-password", title="Change Password"
        )


class AccountPasswordSetView(AllauthPasswordSetView):
    def render_to_response(self, context, **response_kwargs):
        return _account_settings_page(
            self.request, context, page="set-password", title="Set Password"
        )


class AccountReauthenticateView(AllauthReauthenticateView):
    def render_to_response(self, context, **response_kwargs):
        return _account_settings_page(
            self.request, context, page="reauthenticate", title="Confirm Access"
        )


def google_login_view(request):
    if (
        request.method == "GET"
        and request.GET.get("process") == "connect"
        and request.user.is_authenticated
    ):
        provider = get_socialaccount_adapter().get_provider(request, provider="google")
        page = cast(
            RenderableTemplate,
            GoogleConnectPage(
                title="Connect Google",
                provider_name=provider.name,
                continue_url=provider.get_login_url(request, process="connect"),
                cancel_url=reverse("socialaccount_connections"),
            ),
        )
        return page.render(request)
    if request.method == "GET" and request.GET.get("process") != "connect":
        provider = get_socialaccount_adapter().get_provider(request, provider="google")
        page = cast(
            RenderableTemplate,
            SocialLoginPage(
                title="Sign In with Google",
                provider_name=provider.name,
                action_url=provider.get_login_url(request, process="login"),
            ),
        )
        return page.render(request)
    return google_oauth2_login(request)


class SocialSignupView(AllauthSocialSignupView):
    def render_to_response(self, context, **response_kwargs):
        provider = context["account"].get_provider(self.request)
        page = cast(
            RenderableTemplate,
            SocialSignupPage(
                title="Complete Sign Up",
                provider_name=provider.name,
                site_name=str(context["site"]),
                form=_serialize_account_form(context["form"]),
                action_url=self.request.get_full_path(),
                redirect_field=_redirect_field(context),
            ),
        )
        return page.render(self.request)


def social_login_cancelled_view(request):
    page = cast(
        RenderableTemplate,
        SocialAuthStatusPage(
            title="Sign In Cancelled",
            state="cancelled",
            sign_in_url=reverse("account_login"),
        ),
    )
    return page.render(request)


def social_login_error_view(request):
    page = cast(
        RenderableTemplate,
        SocialAuthStatusPage(
            title="Sign In Error",
            state="error",
            sign_in_url=reverse("account_login"),
        ),
    )
    return page.render(request)


class AccountEmailVerificationSentView(AllauthEmailVerificationSentView):
    def render_to_response(self, context, **response_kwargs):
        page = cast(
            RenderableTemplate,
            AccountEmailStatesPage(title="Verify Email", page="verification-sent"),
        )
        return page.render(self.request)


class AccountEmailVerificationCodeView(AllauthConfirmEmailVerificationCodeView):
    def render_to_response(self, context, **response_kwargs):
        page = cast(
            RenderableTemplate,
            AccountEmailStatesPage(
                title="Verify Email",
                page="login-code",
                recipient=context.get("email") or context.get("phone") or "your account",
                action_url=self.request.get_full_path(),
                verify_form=_serialize_account_form(context["verify_form"]),
                can_resend=bool(context.get("can_resend")),
                cancel_url=context.get("cancel_url"),
                logout_url=reverse("account_logout"),
                login_url=reverse("account_login"),
                redirect_field=_redirect_field(context),
                can_change=bool(context.get("can_change")),
                change_form=(
                    _serialize_account_form(context["change_form"])
                    if context.get("change_form")
                    else None
                ),
            ),
        )
        return page.render(self.request)


def account_email_verification_sent_view(request):
    view = (
        AccountEmailVerificationCodeView
        if account_app_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED
        else AccountEmailVerificationSentView
    )
    return view.as_view()(request)


class AccountConfirmEmailView(AllauthConfirmEmailView):
    def render_to_response(self, context, **response_kwargs):
        confirmation = getattr(self, "object", None)
        if confirmation:
            page = AccountEmailStatesPage(
                title="Confirm Email",
                page="confirm-email",
                email=confirmation.email_address.email,
                user_display=user_display(confirmation.email_address.user),
                action_url=self.request.get_full_path(),
                redirect_field=_redirect_field(context),
            )
        else:
            page = AccountEmailStatesPage(
                title="Email Link Expired",
                page="confirm-email-invalid",
                email_url=reverse("account_email"),
            )
        return cast(RenderableTemplate, page).render(self.request)


class AccountInactiveView(AllauthAccountInactiveView):
    def render_to_response(self, context, **response_kwargs):
        page = cast(
            RenderableTemplate,
            AccountEmailStatesPage(title="Account Inactive", page="inactive"),
        )
        return page.render(self.request)


class AccountConfirmLoginCodeView(AllauthConfirmLoginCodeView):
    def render_to_response(self, context, **response_kwargs):
        page = cast(
            RenderableTemplate,
            AccountEmailStatesPage(
                title="Confirm Sign In",
                page="login-code",
                recipient=context.get("email") or context.get("phone") or "your account",
                action_url=self.request.get_full_path(),
                verify_form=_serialize_account_form(context["verify_form"]),
                can_resend=False,
                logout_url=reverse("account_logout"),
                login_url=reverse("account_login"),
                redirect_field=_redirect_field(context),
            ),
        )
        return page.render(self.request)


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


def _render_password_reset(request, *, step, form=None):
    page = cast(
        RenderableTemplate,
        PasswordResetPage(
            title="Reset Password",
            step=step,
            form=form,
            sign_in_url=reverse("account_login"),
            reset_url=reverse("account_reset_password"),
        ),
    )
    return page.render(request)


class PasswordResetView(AllauthPasswordResetView):
    def render_to_response(self, context, **response_kwargs):
        return _render_password_reset(
            self.request, step="request", form=context["form"]
        )


class PasswordResetDoneView(AllauthPasswordResetDoneView):
    def render_to_response(self, context, **response_kwargs):
        return _render_password_reset(self.request, step="sent")


class PasswordResetFromKeyView(AllauthPasswordResetFromKeyView):
    def render_to_response(self, context, **response_kwargs):
        if context.get("token_fail"):
            return _render_password_reset(self.request, step="invalid")
        return _render_password_reset(self.request, step="set", form=context["form"])


class PasswordResetFromKeyDoneView(AllauthPasswordResetFromKeyDoneView):
    def render_to_response(self, context, **response_kwargs):
        return _render_password_reset(self.request, step="complete")


class AccountConnectionsView(AllauthConnectionsView):
    def render_to_response(self, context, **response_kwargs):
        form = context["form"]
        accounts = list(form.fields["account"].queryset)
        connections = [
            {
                "id": account.pk,
                "provider": account.get_provider(self.request).name,
                "name": account.get_provider_account().to_str(),
            }
            for account in accounts
        ]
        connected_providers = {account.provider for account in accounts}
        providers = [
            {
                "name": provider.name,
                "url": provider.get_login_url(self.request, process="connect"),
            }
            for provider in sorted(
                get_socialaccount_adapter().list_providers(self.request),
                key=lambda item: item.name,
            )
            if not provider.uses_apps or not provider.app.settings.get("hidden")
            if provider.id not in connected_providers
        ]
        page = cast(
            RenderableTemplate,
            AccountConnectionsPage(
                title="Account Connections",
                email=self.request.user.email,
                connections=connections,
                providers=providers,
                form_errors={
                    key: [str(error) for error in errors]
                    for key, errors in form.errors.items()
                },
            ),
        )
        return page.render(self.request)


class InvitationRequiredView(SignupView):
    """Present an invitation-only access notice when public signup is closed."""

    def closed(self) -> HttpResponse:
        page = cast(
            RenderableTemplate,
            InvitationRequiredPage(
                title="Invitation Required",
                request_invitation_url=reverse("request_invitation"),
                sign_in_url=reverse("account_login"),
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
