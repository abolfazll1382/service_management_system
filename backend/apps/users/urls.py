"""``/api/auth/…``"""

from django.urls import path

from apps.users.views import (
    CustomerLoginView,
    LogoutView,
    MeView,
    RegisterView,
    StaffLoginView,
)

app_name = "auth"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/customer/", CustomerLoginView.as_view(), name="login-customer"),
    path("login/staff/", StaffLoginView.as_view(), name="login-staff"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
