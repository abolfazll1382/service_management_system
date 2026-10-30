"""Account serializers: input validation (write) and wire shapes (read).

Wire shapes are camelCase and role-dependent, exactly the frontend's ``PublicUser`` union:

* customer – ``{id, role, isActive, createdAt, fullName, nationalId, phone, postalCode, address}``
* staff    – ``{id, role, isActive, createdAt, username, name: {fa, en}, departmentIds}``
* admin    – ``{id, role, isActive, createdAt, username, name: {fa, en}}``

Credentials never appear in any of them.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from apps.core import messages as m
from apps.core.serializers import (
    DepartmentIdsField,
    DigitsField,
    KeyedCharField,
    LocalizedSerializer,
    StrictBooleanField,
    UTCDateTimeField,
)
from apps.core.validators import (
    national_id_validator,
    new_password_validator,
    phone_validator,
    postal_code_validator,
    username_validator,
)
from apps.users.choices import UserRole
from apps.users.models import User

MAX_PASSWORD_LENGTH = 128  # bounds the work (and memory) a single hash can be asked to do


class NewPasswordField(KeyedCharField):
    """A password being *chosen*: 8–128 characters with at least one letter and one digit.

    Never trimmed and never digit-normalised: it is hashed exactly as typed.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            error_key=m.V_PASSWORD_MIN,
            trim_whitespace=False,
            min_length=8,
            max_length=MAX_PASSWORD_LENGTH,
            error_messages={"max_length": m.V_PASSWORD_MAX},
            validators=[new_password_validator],
            **kwargs,
        )


class LoginPasswordField(KeyedCharField):
    """A password being *presented*: any non-empty string up to the maximum length."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            error_key=m.V_REQUIRED,
            trim_whitespace=False,
            max_length=MAX_PASSWORD_LENGTH,
            error_messages={"max_length": m.V_PASSWORD_MAX},
            **kwargs,
        )


# --- Input -----------------------------------------------------------------------------------


class RegisterInputSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """What the server accepts to create a customer. Unknown keys (``role``, ``username``,
    ``departmentIds``, ``isActive`` …) are ignored: a client cannot choose its own privileges."""

    fullName = KeyedCharField(error_key=m.V_FULL_NAME, min_length=2, max_length=100)
    nationalId = DigitsField(
        error_key=m.V_NATIONAL_ID_FORMAT,
        max_length=64,
        validators=[national_id_validator(check_digit=True)],
    )
    phone = DigitsField(error_key=m.V_PHONE, max_length=64, validators=[phone_validator])
    postalCode = DigitsField(
        error_key=m.V_POSTAL_CODE, max_length=64, validators=[postal_code_validator]
    )
    address = KeyedCharField(error_key=m.V_ADDRESS, min_length=5, max_length=200)
    password = NewPasswordField()


class CustomerLoginSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Shape only, not the checksum: a mistyped-but-well-formed ID gets the same generic
    ``invalid_credentials`` as a wrong password, rather than a hint about which part was wrong."""

    nationalId = DigitsField(
        error_key=m.V_NATIONAL_ID_FORMAT,
        max_length=64,
        validators=[national_id_validator(check_digit=False)],
    )
    password = LoginPasswordField()


class StaffLoginSerializer(serializers.Serializer):  # type: ignore[type-arg]
    username = KeyedCharField(
        error_key=m.V_REQUIRED, max_length=150, error_messages={"max_length": m.V_INVALID}
    )
    password = LoginPasswordField()


class CreateStaffSerializer(serializers.Serializer):  # type: ignore[type-arg]
    nameFa = KeyedCharField(error_key=m.V_NAMES, min_length=2, max_length=60)
    nameEn = KeyedCharField(error_key=m.V_NAMES, min_length=2, max_length=60)
    username = KeyedCharField(
        error_key=m.V_USERNAME,
        trim_whitespace=False,  # exactly [a-z][a-z0-9_]{2,19}: " nima" is not a username
        max_length=64,
        validators=[username_validator],
    )
    password = NewPasswordField()
    departmentIds = DepartmentIdsField()


class UpdateStaffSerializer(serializers.Serializer):  # type: ignore[type-arg]
    departmentIds = DepartmentIdsField()
    isActive = StrictBooleanField()


# --- Output ----------------------------------------------------------------------------------


class _ProfileBase(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField(read_only=True)
    isActive = serializers.BooleanField(source="is_active", read_only=True)
    createdAt = UTCDateTimeField(source="created_at", read_only=True)


class CustomerProfileSerializer(_ProfileBase):
    role = serializers.ChoiceField(choices=[UserRole.CUSTOMER.value], read_only=True)
    fullName = serializers.CharField(source="full_name", read_only=True)
    nationalId = serializers.CharField(source="national_id", read_only=True)
    phone = serializers.CharField(read_only=True)
    postalCode = serializers.CharField(source="postal_code", read_only=True)
    address = serializers.CharField(read_only=True)


class _StaffAccountBase(_ProfileBase):
    username = serializers.CharField(read_only=True)
    name = serializers.SerializerMethodField()

    @extend_schema_field(LocalizedSerializer)
    def get_name(self, user: User) -> dict[str, str]:
        return {"fa": user.name_fa or "", "en": user.name_en or ""}


class StaffProfileSerializer(_StaffAccountBase):
    role = serializers.ChoiceField(choices=[UserRole.STAFF.value], read_only=True)
    departmentIds = serializers.ListField(
        source="department_ids", child=serializers.CharField(), read_only=True
    )


class AdminProfileSerializer(_StaffAccountBase):
    role = serializers.ChoiceField(choices=[UserRole.ADMIN.value], read_only=True)


_PROFILE_SERIALIZERS: dict[str, type[serializers.Serializer]] = {  # type: ignore[type-arg]
    UserRole.CUSTOMER: CustomerProfileSerializer,
    UserRole.STAFF: StaffProfileSerializer,
    UserRole.ADMIN: AdminProfileSerializer,
}

#: For OpenAPI only: ``PublicUser`` is a union discriminated by ``role``.
PublicUserSchema = PolymorphicProxySerializer(
    component_name="PublicUser",
    serializers={
        "customer": CustomerProfileSerializer,
        "staff": StaffProfileSerializer,
        "admin": AdminProfileSerializer,
    },
    resource_type_field_name="role",
)

#: ``StaffAccount`` = staff | admin (the team list never contains customers), and the list of them.
StaffAccountListSchema = PolymorphicProxySerializer(
    component_name="StaffAccount",
    serializers={"staff": StaffProfileSerializer, "admin": AdminProfileSerializer},
    resource_type_field_name="role",
    many=True,
)


def public_user_data(user: User) -> dict[str, Any]:
    """The ``PublicUser`` JSON for ``user`` (never includes credentials)."""
    data: dict[str, Any] = _PROFILE_SERIALIZERS[user.role](user).data
    return data


def auth_result_data(token: str, user: User) -> dict[str, Any]:
    """``AuthResult``: ``{token, user}``."""
    return {"token": token, "user": public_user_data(user)}


class AuthResultSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Documentation shape of :func:`auth_result_data`."""

    token = serializers.CharField()
    user = PublicUserSchema
