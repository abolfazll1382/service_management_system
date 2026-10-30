"""``/api/requests/…``

The fixed paths (``mine/``, ``queue/``, ``assignable-staff/``) come *before* ``<request_id>/`` so
they are never mistaken for an id. The id segment is a plain string on purpose: a malformed id is
answered exactly like an unknown one (``not_found``) by the service, not by the router.
"""

from django.urls import path

from apps.requests.views import (
    AssignableStaffView,
    AssignView,
    MessageCreateView,
    MyRequestsView,
    QueueView,
    RequestCollectionView,
    RequestDetailView,
    TransitionView,
)

app_name = "requests"

urlpatterns = [
    path("", RequestCollectionView.as_view(), name="request-create"),
    path("mine/", MyRequestsView.as_view(), name="request-mine"),
    path("queue/", QueueView.as_view(), name="request-queue"),
    path("assignable-staff/", AssignableStaffView.as_view(), name="request-assignable-staff"),
    path("<str:request_id>/", RequestDetailView.as_view(), name="request-detail"),
    path("<str:request_id>/transition/", TransitionView.as_view(), name="request-transition"),
    path("<str:request_id>/assign/", AssignView.as_view(), name="request-assign"),
    path("<str:request_id>/messages/", MessageCreateView.as_view(), name="request-messages"),
]
