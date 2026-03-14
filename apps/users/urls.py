from django.urls import path

from .views import HomePageView, StartPageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home_page"),
    path("start/", StartPageView.as_view(), name="start_page"),
]
