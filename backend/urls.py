"""URL configuration for backend project."""

from allauth.account.decorators import secure_admin_login
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from health_check.views import HealthCheckView

from apps.users.views import SignInView

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
    path("invitations/", include("invitations.urls", namespace="invitations")),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.catalog_prototype.urls")),
    path("", include("apps.schedules.urls")),
    path("", include("apps.users.urls")),
]
