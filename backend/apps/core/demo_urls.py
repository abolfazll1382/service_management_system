"""``/api/demo/…``"""

from django.urls import path

from apps.core.demo.views import DemoResetView

app_name = "demo"

urlpatterns = [
    path("reset/", DemoResetView.as_view(), name="reset"),
]
