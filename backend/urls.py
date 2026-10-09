"""URL configuration for backend project."""

from allauth.account.decorators import secure_admin_login
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from health_check.views import HealthCheckView

from apps.accounts.views import (
    InvitationRequiredView,
    PasswordResetDoneView,
    PasswordResetFromKeyDoneView,
    PasswordResetFromKeyView,
    PasswordResetView,
    AccountEmailView,
    AccountPasswordChangeView,
    AccountPasswordSetView,
    AccountReauthenticateView,
    AccountConnectionsView,
    AccountConfirmEmailView,
    AccountConfirmLoginCodeView,
    AccountInactiveView,
    SocialSignupView,
    SignInView,
    account_email_verification_sent_view,
    google_login_view,
    social_login_cancelled_view,
    social_login_error_view,
)

admin.autodiscover()
admin.site.login = secure_admin_login(admin.site.login)


def health_view(_request):
    return JsonResponse({"status": "ok"})


class DjangoReadyView(HealthCheckView):
    """Readiness: database + default storage (e.g. Supabase S3 in production)."""

    checks = (
        "health_check.checks.Database",
        "health_check.checks.Storage",
    )


urlpatterns = [
    path("health/", health_view, name="health"),
    path("ready/", DjangoReadyView.as_view(), name="ready"),
    path("admin/", admin.site.urls),
    path("accounts/login/", SignInView.as_view(), name="account_login"),
    path("accounts/email/", AccountEmailView.as_view(), name="account_email"),
    path(
        "accounts/password/change/",
        AccountPasswordChangeView.as_view(),
        name="account_change_password",
    ),
    path(
        "accounts/password/set/",
        AccountPasswordSetView.as_view(),
        name="account_set_password",
    ),
    path(
        "accounts/reauthenticate/",
        AccountReauthenticateView.as_view(),
        name="account_reauthenticate",
    ),
    path("accounts/google/login/", google_login_view, name="google_login"),
    path(
        "accounts/3rdparty/",
        AccountConnectionsView.as_view(),
        name="socialaccount_connections",
    ),
    path(
        "accounts/3rdparty/login/cancelled/",
        social_login_cancelled_view,
        name="socialaccount_login_cancelled",
    ),
    path(
        "accounts/3rdparty/login/error/",
        social_login_error_view,
        name="socialaccount_login_error",
    ),
    path(
        "accounts/3rdparty/signup/",
        SocialSignupView.as_view(),
        name="socialaccount_signup",
    ),
    path("accounts/inactive/", AccountInactiveView.as_view(), name="account_inactive"),
    path(
        "accounts/confirm-email/",
        account_email_verification_sent_view,
        name="account_email_verification_sent",
    ),
    re_path(
        r"^accounts/confirm-email/(?P<key>[-:\w]+)/$",
        AccountConfirmEmailView.as_view(),
        name="account_confirm_email",
    ),
    path(
        "accounts/login/code/confirm/",
        AccountConfirmLoginCodeView.as_view(),
        name="account_confirm_login_code",
    ),
    path(
        "accounts/password/reset/",
        PasswordResetView.as_view(),
        name="account_reset_password",
    ),
    path(
        "accounts/password/reset/done/",
        PasswordResetDoneView.as_view(),
        name="account_reset_password_done",
    ),
    path(
        "accounts/password/reset/key/done/",
        PasswordResetFromKeyDoneView.as_view(),
        name="account_reset_password_from_key_done",
    ),
    re_path(
        r"^accounts/password/reset/key/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$",
        PasswordResetFromKeyView.as_view(),
        name="account_reset_password_from_key",
    ),
    path(
        "accounts/signup/",
        InvitationRequiredView.as_view(),
        name="account_signup",
    ),
    path("invitations/", include("invitations.urls", namespace="invitations")),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.accounts.urls")),
]
