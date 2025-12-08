from django.urls import path
from .views import homepage, StartPageView

urlpatterns = [
    path("", homepage, name="home_page"),
    path("start/", StartPageView.as_view(), name="start_page"),
]
