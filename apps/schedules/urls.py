from django.urls import path

from apps.schedules.views import ScheduleLandingView, ServicePreviewView

urlpatterns = [
    path("schedule/", ScheduleLandingView.as_view(), name="schedule_landing"),
    path("schedule/<str:date>/preview/", ServicePreviewView.as_view(), name="service_preview"),
]
