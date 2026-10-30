"""HTTP-level constants shared by modules that must not import DRF views.

Kept dependency-free on purpose: ``apps.users.authentication`` is imported *by* DRF while it builds
``APIView`` (through ``DEFAULT_AUTHENTICATION_CLASSES``), so it cannot import anything that imports
``rest_framework.views`` itself (such as ``apps.core.exceptions``) without a circular import.
"""

from __future__ import annotations

from typing import Final

#: Sent with every 401 so clients (and proxies) know how to authenticate.
WWW_AUTHENTICATE: Final = 'Bearer realm="api"'
