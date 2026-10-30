"""``/api/staff/…``"""

from django.urls import path

from apps.users.views import StaffDetailView, StaffListCreateView

app_name = "staff"

urlpatterns = [
    path("", StaffListCreateView.as_view(), name="list-create"),
    path("<str:staff_id>/", StaffDetailView.as_view(), name="detail"),
]
