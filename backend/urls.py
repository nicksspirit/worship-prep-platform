"""URL configuration for backend project."""

from allauth.account.decorators import secure_admin_login
from django.contrib import admin
from django.urls import include, path

from apps.users.views import SignInView

admin.autodiscover()
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", SignInView.as_view(), name="account_login"),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.schedules.urls")),
    path("", include("apps.users.urls")),
]
