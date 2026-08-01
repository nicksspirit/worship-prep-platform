from django.urls import path

from .views import HomePageView, RequestInvitationView

urlpatterns = [
    path("", HomePageView.as_view(), name="home_page"),
    path(
        "request-invitation/",
        RequestInvitationView.as_view(),
        name="request_invitation",
    ),
]
