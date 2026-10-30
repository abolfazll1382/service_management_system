"""Object-level access to a request: the ``loadAuthorized`` rule of the original mock server.

Two different refusals, on purpose:

* someone who may not even *read* the request gets ``not_found`` if they are a customer (ids and
  tracking codes must not be probeable) and ``forbidden`` if they are staff (an explicit "that
  belongs to another department" is the useful answer for an insider);
* someone who can read it but not do this particular thing gets ``forbidden``.
"""

from __future__ import annotations

from apps.core.exceptions import ForbiddenError, NotFoundError
from apps.requests.models import ServiceRequest
from apps.users.choices import UserRole
from apps.users.models import User
from apps.users.policies import Action, PolicyResource, can


def resource_of(request: ServiceRequest) -> PolicyResource:
    return PolicyResource(department_id=request.department, owner_id=request.customer_id)


def authorize_request_action(
    actor: User, request: ServiceRequest | None, action: Action
) -> ServiceRequest:
    """Return ``request`` if ``actor`` may perform ``action`` on it; otherwise raise the right
    domain error (see the module docstring). A missing request is always ``not_found``."""
    if request is None:
        raise NotFoundError()
    resource = resource_of(request)
    if not can(actor, Action.REQUEST_READ, resource):
        raise NotFoundError() if actor.role == UserRole.CUSTOMER else ForbiddenError()
    if not can(actor, action, resource):
        raise ForbiddenError()
    return request
