from django.urls import path

from apps.catalog.views import catalog_import

app_name = "catalog"

urlpatterns = [path("imports", catalog_import, name="import")]
