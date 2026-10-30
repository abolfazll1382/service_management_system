"""``/api/catalog/…``

Service ids are slugs; the ``slug`` converter also keeps NUL and other junk out of the database
(a non-matching path is a plain JSON 404).
"""

from django.urls import path

from apps.catalog.views import ServiceActiveView, ServiceDetailView, ServiceListView

app_name = "catalog"

urlpatterns = [
    path("services/", ServiceListView.as_view(), name="service-list"),
    path("services/<slug:service_id>/", ServiceDetailView.as_view(), name="service-detail"),
    path("services/<slug:service_id>/active/", ServiceActiveView.as_view(), name="service-active"),
]
