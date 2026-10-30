"""Password hashing."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.hashers import Argon2PasswordHasher


class PortalArgon2PasswordHasher(Argon2PasswordHasher):
    """Argon2id at a cost that is safe to run on a small container.

    Django's stock Argon2 hasher uses 100 MiB and 8 lanes *per hash*; a handful of simultaneous
    sign-ins would then exhaust a 512 MiB container. The defaults here are OWASP's minimum
    recommendation (19 MiB, 2 iterations, 1 lane) and are tunable through ``ARGON2_*`` settings.
    Hashes created with other parameters keep verifying and are upgraded on the next login.
    """

    time_cost = settings.ARGON2_TIME_COST
    memory_cost = settings.ARGON2_MEMORY_COST_KIB
    parallelism = settings.ARGON2_PARALLELISM
