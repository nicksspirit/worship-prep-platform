from django.urls import path

from .views import HomePageView, RequestInvitationView

urlpatterns = [
    path("after-sign-in/", HomePageView.as_view(), name="after_sign_in"),
    path("", HomePageView.as_view(), name="home_page"),
    path(
        "request-invitation/",
        RequestInvitationView.as_view(),
        name="request_invitation",
    ),
]
