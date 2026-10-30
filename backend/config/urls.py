"""Root URL configuration: ``/health/`` plus everything under ``/api/``.

No ``/api/v1`` prefix: the paths are exactly the ones the frontend's API layer calls.
"""

from __future__ import annotations

from django.conf import settings
from django.urls import include, path

from apps.core.views import HealthView

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("api/auth/", include("apps.users.urls")),
    path("api/staff/", include("apps.users.staff_urls")),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/requests/", include("apps.requests.urls")),
    path("api/audit/", include("apps.audit.urls")),
    path("api/demo/", include("apps.core.demo_urls")),
]

if settings.ENABLE_API_DOCS:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    ]
