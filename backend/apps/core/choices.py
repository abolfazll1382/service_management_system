"""Vocabulary shared by several apps."""

from __future__ import annotations

from django.db import models


class Department(models.TextChoices):
    """The unit of authorisation: every request belongs to exactly one department and every staff
    member is granted a set of them. Mirrors ``DEPARTMENT_IDS`` in the frontend."""

    LOAN = "loan", "Loan"
    RAW_MATERIAL = "raw_material", "Raw material"
    VEHICLE = "vehicle", "Vehicle"
    HOUSING = "housing", "Housing"


#: Department ids in their canonical (frontend) order.
DEPARTMENT_IDS: tuple[str, ...] = tuple(Department.values)
