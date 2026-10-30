"""The authorisation policy matrix (port of the frontend's ``policies.test.ts``).

Pure functions over unsaved ``User`` instances: no database.
"""

from __future__ import annotations

import uuid

import pytest

from apps.core.choices import DEPARTMENT_IDS
from apps.users.choices import UserRole
from apps.users.models import User
from apps.users.policies import Action, PolicyResource, can, can_assign_to, visible_departments

ALL_ACTIONS = list(Action)
DEPARTMENT_SCOPED = [
    Action.REQUEST_READ,
    Action.REQUEST_COMMENT,
    Action.REQUEST_COMMENT_INTERNAL,
    Action.REQUEST_TRANSITION,
    Action.REQUEST_ASSIGN,
]


def admin(*, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(), role=UserRole.ADMIN, username="admin", is_active=active, department_ids=[]
    )


def staff(departments: list[str], *, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        role=UserRole.STAFF,
        username="staff",
        is_active=active,
        department_ids=departments,
    )


def customer(*, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        role=UserRole.CUSTOMER,
        full_name="Customer",
        national_id="0045813922",
        is_active=active,
        department_ids=[],
    )


reza = staff(["loan"])
sara = staff(["raw_material"])
multi = staff(["loan", "housing"])


def test_the_action_list_is_what_the_matrix_below_expects() -> None:
    assert {action.value for action in Action} == {
        "console.access",
        "request.create",
        "request.read",
        "request.comment",
        "request.comment_internal",
        "request.transition",
        "request.assign",
        "staff.manage",
        "service.manage",
        "audit.read",
        "demo.reset",
    }


class TestDefaultDeny:
    @pytest.mark.parametrize("action", ALL_ACTIONS)
    def test_nobody_signed_in_may_do_nothing(self, action: Action) -> None:
        assert not can(None, action, PolicyResource(department_id="loan", owner_id=uuid.uuid4()))

    @pytest.mark.parametrize("action", ALL_ACTIONS)
    def test_a_deactivated_account_may_do_nothing_whatever_its_role(self, action: Action) -> None:
        for actor in (staff(["loan"], active=False), customer(active=False), admin(active=False)):
            resource = PolicyResource(department_id="loan", owner_id=actor.id)
            assert not can(actor, action, resource), f"{actor.role}:{action}"

    def test_an_unknown_role_is_denied(self) -> None:
        stranger = User(id=uuid.uuid4(), role="auditor", is_active=True, department_ids=[])
        for action in ALL_ACTIONS:
            assert not can(stranger, action, PolicyResource(department_id="loan"))


class TestStaffAreConfinedToTheirDepartments:
    @pytest.mark.parametrize("action", DEPARTMENT_SCOPED)
    def test_allowed_only_inside_a_granted_department(self, action: Action) -> None:
        for actor in (reza, sara, multi):
            for department in DEPARTMENT_IDS:
                assert can(actor, action, PolicyResource(department_id=department)) == (
                    department in actor.department_ids
                ), f"{actor.department_ids} {action} {department}"

    @pytest.mark.parametrize("action", DEPARTMENT_SCOPED)
    def test_a_department_scoped_action_with_no_department_is_denied(self, action: Action) -> None:
        assert not can(reza, action, PolicyResource())

    @pytest.mark.parametrize("action", DEPARTMENT_SCOPED)
    def test_a_made_up_department_is_denied(self, action: Action) -> None:
        assert not can(reza, action, PolicyResource(department_id="treasury"))

    def test_staff_enter_the_console_but_never_the_administration(self) -> None:
        assert can(reza, Action.CONSOLE_ACCESS)
        for action in (
            Action.STAFF_MANAGE,
            Action.SERVICE_MANAGE,
            Action.AUDIT_READ,
            Action.DEMO_RESET,
            Action.REQUEST_CREATE,
        ):
            assert not can(reza, action, PolicyResource(department_id="loan")), action

    def test_a_multi_department_member_has_exactly_the_union_of_their_grants(self) -> None:
        assert visible_departments(multi) == ("loan", "housing")
        assert can(multi, Action.REQUEST_READ, PolicyResource(department_id="housing"))
        assert not can(multi, Action.REQUEST_READ, PolicyResource(department_id="vehicle"))


class TestCustomersTouchOnlyTheirOwnRequests:
    amir = customer()

    def test_may_create_requests(self) -> None:
        assert can(self.amir, Action.REQUEST_CREATE)

    @pytest.mark.parametrize("action", [Action.REQUEST_READ, Action.REQUEST_COMMENT])
    def test_may_read_and_comment_on_their_own_request_only(self, action: Action) -> None:
        own = PolicyResource(department_id="loan", owner_id=self.amir.id)
        other = PolicyResource(department_id="loan", owner_id=uuid.uuid4())
        assert can(self.amir, action, own)
        assert not can(self.amir, action, other)
        assert not can(self.amir, action, PolicyResource(department_id="loan"))

    def test_can_never_act_as_staff_even_on_their_own_request(self) -> None:
        own = PolicyResource(department_id="loan", owner_id=self.amir.id)
        for action in (
            Action.CONSOLE_ACCESS,
            Action.REQUEST_COMMENT_INTERNAL,
            Action.REQUEST_TRANSITION,
            Action.REQUEST_ASSIGN,
            Action.STAFF_MANAGE,
            Action.SERVICE_MANAGE,
            Action.AUDIT_READ,
            Action.DEMO_RESET,
        ):
            assert not can(self.amir, action, own), action


class TestAdministrators:
    @pytest.mark.parametrize("action", ALL_ACTIONS)
    def test_may_do_everything_except_file_a_request_as_an_applicant(self, action: Action) -> None:
        resource = PolicyResource(department_id="vehicle")
        assert can(admin(), action, resource) == (action is not Action.REQUEST_CREATE)

    def test_sees_every_department(self) -> None:
        assert visible_departments(admin()) == DEPARTMENT_IDS


class TestVisibleDepartments:
    def test_is_empty_for_customers_nobody_and_inactive_staff(self) -> None:
        assert visible_departments(None) == ()
        assert visible_departments(customer()) == ()
        assert visible_departments(staff(["loan"], active=False)) == ()
        assert visible_departments(admin(active=False)) == ()


class TestCanAssignTo:
    colleague = staff(["loan"])

    def test_staff_may_claim_for_themselves_but_not_hand_over_to_a_colleague(self) -> None:
        assert can_assign_to(reza, reza, "loan")
        assert not can_assign_to(reza, self.colleague, "loan")

    def test_an_administrator_may_assign_to_any_active_staff_member_of_that_department(
        self,
    ) -> None:
        assert can_assign_to(admin(), reza, "loan")
        assert can_assign_to(admin(), self.colleague, "loan")

    def test_never_assigns_outside_the_assignees_own_departments(self) -> None:
        assert not can_assign_to(admin(), reza, "vehicle")
        assert not can_assign_to(reza, reza, "vehicle")  # not even to himself: not his department

    def test_customers_admins_and_deactivated_staff_are_not_eligible_assignees(self) -> None:
        root = admin()
        assert not can_assign_to(root, customer(), "loan")
        assert not can_assign_to(root, admin(), "loan")
        assert not can_assign_to(root, staff(["loan"], active=False), "loan")

    def test_unassigning_needs_only_the_right_to_assign_in_that_department(self) -> None:
        assert can_assign_to(reza, None, "loan")
        assert not can_assign_to(reza, None, "vehicle")
        assert not can_assign_to(customer(), None, "loan")
        assert not can_assign_to(None, None, "loan")
        assert not can_assign_to(None, reza, "loan")
