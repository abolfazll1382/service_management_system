"""OpenAPI description of the bearer-token scheme (loaded from ``UsersConfig.ready``)."""

from __future__ import annotations

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema


class BearerTokenAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.users.authentication.BearerTokenAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, Any]:
        return {
            "type": "http",
            "scheme": "bearer",
            "description": (
                "Opaque token returned by the register / sign-in endpoints, sent as "
                "`Authorization: Bearer <token>`. It is revoked by `POST /api/auth/logout/`, "
                "expires after the configured lifetime (8 hours by default) and stops working "
                "at once if the account is deactivated."
            ),
        }
