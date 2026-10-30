"""Bearer-token authentication backed by the ``AccessToken`` table."""

from __future__ import annotations

import hashlib
import re

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.core.http import WWW_AUTHENTICATE
from apps.users.models import AccessToken, User

#: Tokens are ``secrets.token_hex(32)``. Anything else cannot be ours, so it is refused without
#: touching the database.
_TOKEN_SHAPE = re.compile(rb"[0-9a-f]{64}")


def hash_token(raw_token: bytes | str) -> str:
    """The value stored (and looked up) for a token: its SHA-256 hex digest."""
    data = raw_token.encode() if isinstance(raw_token, str) else raw_token
    return hashlib.sha256(data).hexdigest()


class BearerTokenAuthentication(BaseAuthentication):
    """``Authorization: Bearer <token>``.

    * No header, or another scheme → anonymous (a protected view then answers 401 itself).
    * A Bearer header that is malformed, unknown, expired, revoked, or whose owner has been
      deactivated → ``AuthenticationFailed`` (401). A deactivated account is treated exactly like
      no session at all, so switching someone off takes effect on their very next request.
    """

    def authenticate_header(self, request: Request) -> str:
        return WWW_AUTHENTICATE

    def authenticate(self, request: Request) -> tuple[User, AccessToken] | None:
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b"bearer":
            return None
        if len(parts) != 2 or not _TOKEN_SHAPE.fullmatch(parts[1]):
            raise AuthenticationFailed()

        token = (
            AccessToken.objects.select_related("user").filter(key_hash=hash_token(parts[1])).first()
        )
        if (
            token is None
            or token.revoked_at is not None
            or token.expires_at <= timezone.now()
            or not token.user.is_active
        ):
            raise AuthenticationFailed()
        return token.user, token
