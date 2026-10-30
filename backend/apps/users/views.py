"""Thin HTTP layer for authentication and team management.

Each view: authenticate → coarse permission → validate input with a *write* serializer → call one
service → shape the result with a *read* serializer. No business rule lives here.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authentication import get_authorization_header
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.serializers import validate_input
from apps.users.permissions import allows, require_actor
from apps.users.policies import Action
from apps.users.selectors import UserSelector
from apps.users.serializers import (
    AuthResultSerializer,
    CreateStaffSerializer,
    CustomerLoginSerializer,
    PublicUserSchema,
    RegisterInputSerializer,
    StaffAccountListSchema,
    StaffLoginSerializer,
    StaffProfileSerializer,
    UpdateStaffSerializer,
    auth_result_data,
    public_user_data,
)
from apps.users.services import AuthService, StaffService


class _PublicAuthView(APIView):
    """Sign-in/registration endpoints: no token is required (or even looked at) and they are
    throttled per client address through DRF's scoped throttle."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]


class RegisterView(_PublicAuthView):
    throttle_scope = "auth_register"

    @extend_schema(
        tags=["auth"],
        request=RegisterInputSerializer,
        responses={201: AuthResultSerializer},
        summary="Register a customer account and sign in",
    )
    def post(self, request: Request) -> Response:
        data = validate_input(RegisterInputSerializer, request.data)
        result = AuthService.register(
            full_name=data["fullName"],
            national_id=data["nationalId"],
            phone=data["phone"],
            postal_code=data["postalCode"],
            address=data["address"],
            password=data["password"],
        )
        return Response(auth_result_data(result.token, result.user), status=status.HTTP_201_CREATED)


class CustomerLoginView(_PublicAuthView):
    throttle_scope = "auth_login"

    @extend_schema(
        tags=["auth"],
        request=CustomerLoginSerializer,
        responses={200: AuthResultSerializer},
        summary="Customer sign-in (national ID + password)",
    )
    def post(self, request: Request) -> Response:
        data = validate_input(CustomerLoginSerializer, request.data)
        result = AuthService.login_customer(
            national_id=data["nationalId"], password=data["password"]
        )
        return Response(auth_result_data(result.token, result.user))


class StaffLoginView(_PublicAuthView):
    throttle_scope = "auth_login"

    @extend_schema(
        tags=["auth"],
        request=StaffLoginSerializer,
        responses={200: AuthResultSerializer},
        summary="Staff / administrator sign-in (username + password)",
    )
    def post(self, request: Request) -> Response:
        data = validate_input(StaffLoginSerializer, request.data)
        result = AuthService.login_staff(username=data["username"], password=data["password"])
        return Response(auth_result_data(result.token, result.user))


class LogoutView(APIView):
    """Idempotent: always 204, for any (or no) token. It never authenticates the caller, so a
    client holding a dead token can still tidy up and learns nothing from the answer."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        request=None,
        responses={
            204: OpenApiResponse(description="Signed out (or there was nothing to sign out).")
        },
        summary="Sign out: revoke the presented bearer token",
    )
    def post(self, request: Request) -> Response:
        parts = get_authorization_header(request).split()
        if len(parts) == 2 and parts[0].lower() == b"bearer":
            AuthService.logout(raw_token=parts[1].decode("latin-1"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(
        tags=["auth"], responses={200: PublicUserSchema}, summary="Who does this token belong to?"
    )
    def get(self, request: Request) -> Response:
        user = require_actor(request)
        return Response(public_user_data(user))


class StaffListCreateView(APIView):
    permission_classes = [allows(Action.STAFF_MANAGE)]

    @extend_schema(
        tags=["staff"],
        responses={200: StaffAccountListSchema},
        summary="List staff and administrator accounts (admin only)",
    )
    def get(self, request: Request) -> Response:
        accounts = UserSelector.staff_accounts()
        return Response([public_user_data(account) for account in accounts])

    @extend_schema(
        tags=["staff"],
        request=CreateStaffSerializer,
        responses={201: StaffProfileSerializer},
        summary="Create a staff account (admin only)",
    )
    def post(self, request: Request) -> Response:
        data = validate_input(CreateStaffSerializer, request.data)
        staff = StaffService.create(
            actor=require_actor(request),
            name_fa=data["nameFa"],
            name_en=data["nameEn"],
            username=data["username"],
            password=data["password"],
            department_ids=data["departmentIds"],
        )
        return Response(public_user_data(staff), status=status.HTTP_201_CREATED)


class StaffDetailView(APIView):
    permission_classes = [allows(Action.STAFF_MANAGE)]

    @extend_schema(
        tags=["staff"],
        request=UpdateStaffSerializer,
        responses={200: StaffProfileSerializer},
        summary="Change a staff member's departments / switch the account on or off (admin only)",
    )
    def patch(self, request: Request, staff_id: str) -> Response:
        data = validate_input(UpdateStaffSerializer, request.data)
        staff = StaffService.update(
            actor=require_actor(request),
            staff_id=staff_id,
            department_ids=data["departmentIds"],
            is_active=data["isActive"],
        )
        return Response(public_user_data(staff))
