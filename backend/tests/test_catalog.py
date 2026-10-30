"""The service catalogue: built-in definitions, definition validation, details validation, sync."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.definitions import SERVICE_DEFINITIONS
from apps.catalog.fields import clean_details, find_definition_problems, validate_field_definitions
from apps.catalog.models import Service
from apps.catalog.services import CatalogService
from apps.core import messages as m
from apps.core.choices import DEPARTMENT_IDS
from apps.core.exceptions import ValidationFailedError
from tests.helpers import Api

LANGUAGES = ("fa", "en")


def both_languages(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(LANGUAGES)
        and all(isinstance(value[lang], str) and value[lang].strip() for lang in LANGUAGES)
    )


class TestBuiltInDefinitions:
    def test_there_are_eight_services_with_unique_ids(self) -> None:
        ids = [definition.id for definition in SERVICE_DEFINITIONS]
        assert len(ids) == 8
        assert len(set(ids)) == len(ids)

    def test_every_service_points_at_a_real_department_and_every_department_has_a_service(
        self,
    ) -> None:
        departments = {definition.department for definition in SERVICE_DEFINITIONS}
        assert departments == set(DEPARTMENT_IDS)

    def test_services_are_fully_translated(self) -> None:
        for definition in SERVICE_DEFINITIONS:
            for text in (definition.title, definition.summary, definition.description):
                assert both_languages(text), definition.id
            assert definition.requirements, definition.id
            assert all(both_languages(item) for item in definition.requirements), definition.id
            assert definition.eta_days > 0

    def test_every_field_definition_is_well_formed(self) -> None:
        for definition in SERVICE_DEFINITIONS:
            assert find_definition_problems(list(definition.fields)) == [], definition.id

    def test_number_bounds_and_select_options_are_sensible(self) -> None:
        for definition in SERVICE_DEFINITIONS:
            for field in definition.fields:
                if field["kind"] == "number":
                    assert field["min"] < field["max"], f"{definition.id}.{field['key']}"
                if field["kind"] == "select":
                    values = [option["value"] for option in field["options"]]
                    assert values
                    assert len(set(values)) == len(values)

    def test_an_empty_submission_is_rejected_whenever_something_is_required(self) -> None:
        for definition in SERVICE_DEFINITIONS:
            cleaned, errors = clean_details(definition.fields, {})
            has_required = any(field["required"] for field in definition.fields)
            assert (not errors) is (not has_required), definition.id
            assert cleaned == {}


class TestFindDefinitionProblems:
    base: dict[str, Any] = {
        "kind": "text",
        "key": "purpose",
        "label": {"fa": "هدف", "en": "Purpose"},
        "required": True,
        "maxLength": 50,
    }

    def problems(self, **changes: Any) -> list[str]:
        definition = {**copy.deepcopy(self.base), **changes}
        return find_definition_problems([definition])

    def test_a_valid_definition_has_no_problems(self) -> None:
        assert self.problems() == []

    @pytest.mark.parametrize("value", [None, {}, "text", 5])
    def test_definitions_must_be_a_list(self, value: object) -> None:
        assert find_definition_problems(value)

    def test_entries_must_be_objects(self) -> None:
        assert find_definition_problems(["text"])

    @pytest.mark.parametrize(
        "changes",
        [
            {"kind": "checkbox"},
            {"kind": None},
            {"key": ""},
            {"key": "1abc"},
            {"key": "has space"},
            {"key": "x" * 65},
            {"key": 5},
            {"label": {"fa": "هدف"}},
            {"label": {"fa": "هدف", "en": "  "}},
            {"label": {"fa": "هدف", "en": "Purpose", "de": "Zweck"}},
            {"label": "Purpose"},
            {"required": "yes"},
            {"required": None},
            {"maxLength": 0},
            {"maxLength": 2001},
            {"maxLength": True},
            {"maxLength": "50"},
            {"unexpected": 1},
        ],
    )
    def test_rejects_malformed_text_fields(self, changes: dict[str, Any]) -> None:
        assert self.problems(**changes), changes

    def test_rejects_duplicate_keys(self) -> None:
        assert find_definition_problems([self.base, self.base])

    def test_number_fields_need_finite_ordered_bounds(self) -> None:
        number = {
            "kind": "number",
            "key": "amount",
            "label": {"fa": "مبلغ", "en": "Amount"},
            "required": True,
            "min": 1,
            "max": 10,
        }
        assert find_definition_problems([number]) == []
        for bad in (
            {**number, "min": 10, "max": 1},
            {**number, "min": "1"},
            {**number, "max": float("inf")},
            {**number, "min": float("nan")},
            {**number, "min": True},
            {**number, "unit": {"fa": "ریال"}},
            {**number, "maxLength": 5},
        ):
            assert find_definition_problems([bad]), bad
        assert find_definition_problems([{**number, "min": 5, "max": 5}]) == []

    def test_select_fields_need_unique_labelled_options(self) -> None:
        option = {"value": "a", "label": {"fa": "الف", "en": "A"}}
        select = {
            "kind": "select",
            "key": "kind",
            "label": {"fa": "نوع", "en": "Kind"},
            "required": False,
            "options": [option],
        }
        assert find_definition_problems([select]) == []
        for bad in (
            {**select, "options": []},
            {**select, "options": "a"},
            {**select, "options": [option, option]},
            {**select, "options": [{"value": "", "label": option["label"]}]},
            {**select, "options": [{"value": 1, "label": option["label"]}]},
            {**select, "options": [{"value": "b", "label": {"fa": "ب"}}]},
            {**select, "options": [{"value": "b"}]},
            {**select, "options": [{**option, "extra": 1}]},
        ):
            assert find_definition_problems([bad]), bad

    def test_validate_field_definitions_raises_a_django_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            validate_field_definitions([{"kind": "nope"}])
        validate_field_definitions([self.base])


class TestCleanDetails:
    definitions: list[dict[str, Any]] = [
        {
            "kind": "number",
            "key": "amount",
            "label": {"fa": "مبلغ", "en": "Amount"},
            "required": True,
            "min": 10,
            "max": 1000,
        },
        {
            "kind": "select",
            "key": "term",
            "label": {"fa": "مدت", "en": "Term"},
            "required": True,
            "options": [{"value": "12", "label": {"fa": "۱۲", "en": "12"}}],
        },
        {
            "kind": "text",
            "key": "purpose",
            "label": {"fa": "هدف", "en": "Purpose"},
            "required": True,
            "maxLength": 10,
        },
        {
            "kind": "text",
            "key": "note",
            "label": {"fa": "یادداشت", "en": "Note"},
            "required": False,
            "maxLength": 10,
        },
    ]
    ok: dict[str, Any] = {"amount": 50, "term": "12", "purpose": "Wedding"}

    def test_accepts_valid_details_and_strips_unknown_keys(self) -> None:
        cleaned, errors = clean_details(self.definitions, {**self.ok, "extra": "ignored"})
        assert errors == {}
        assert cleaned == self.ok

    def test_text_is_trimmed_and_empty_optional_values_are_dropped(self) -> None:
        cleaned, errors = clean_details(
            self.definitions, {**self.ok, "purpose": "  Trip  ", "note": "   "}
        )
        assert errors == {}
        assert cleaned == {**self.ok, "purpose": "Trip"}

    @pytest.mark.parametrize(
        ("override", "field", "key"),
        [
            ({"amount": 9}, "amount", m.V_NUMBER_MIN),
            ({"amount": 1001}, "amount", m.V_NUMBER_MAX),
            ({"amount": "50"}, "amount", m.V_NUMBER_INVALID),
            ({"amount": True}, "amount", m.V_NUMBER_INVALID),
            ({"amount": None}, "amount", m.V_NUMBER_INVALID),
            ({"amount": float("inf")}, "amount", m.V_NUMBER_INVALID),
            ({"amount": float("nan")}, "amount", m.V_NUMBER_INVALID),
            ({"term": "13"}, "term", m.V_SELECT),
            ({"term": 12}, "term", m.V_SELECT),
            ({"term": None}, "term", m.V_SELECT),
            ({"purpose": "   "}, "purpose", m.V_REQUIRED),
            ({"purpose": ""}, "purpose", m.V_REQUIRED),
            ({"purpose": 5}, "purpose", m.V_REQUIRED),
            ({"purpose": "x" * 11}, "purpose", m.V_TEXT_MAX),
            ({"purpose": "bad\x00text"}, "purpose", m.V_INVALID),
            ({"purpose": "lone\ud800surrogate"}, "purpose", m.V_INVALID),
            ({"note": "x" * 11}, "note", m.V_TEXT_MAX),
        ],
    )
    def test_reports_the_first_problem_of_each_field_by_key(
        self, override: dict[str, Any], field: str, key: str
    ) -> None:
        cleaned, errors = clean_details(self.definitions, {**self.ok, **override})
        assert errors == {f"details.{field}": [key]}
        assert field not in cleaned

    def test_missing_required_fields_are_reported_under_the_right_key(self) -> None:
        _, errors = clean_details(self.definitions, {})
        assert errors == {
            "details.amount": [m.V_REQUIRED],
            "details.term": [m.V_SELECT],
            "details.purpose": [m.V_REQUIRED],
        }

    def test_bounds_are_inclusive(self) -> None:
        for amount in (10, 1000, 10.5):
            cleaned, errors = clean_details(self.definitions, {**self.ok, "amount": amount})
            assert errors == {}
            assert cleaned["amount"] == amount

    def test_the_text_limit_counts_characters_after_trimming(self) -> None:
        cleaned, errors = clean_details(
            self.definitions, {**self.ok, "purpose": " " + "ن" * 10 + " "}
        )
        assert errors == {}
        assert cleaned["purpose"] == "ن" * 10


@pytest.mark.django_db
class TestCatalogService:
    def test_clean_details_raises_a_validation_error_carrying_the_field_keys(self) -> None:
        CatalogService.sync_definitions()
        service = Service.objects.get(pk="personal-loan")
        with pytest.raises(ValidationFailedError) as caught:
            CatalogService.clean_details(service, {"amount": 5})
        assert caught.value.field_errors["details.amount"] == [m.V_NUMBER_MIN]
        assert "details.termMonths" in caught.value.field_errors

    def test_sync_is_idempotent_and_keeps_availability(self) -> None:
        first = CatalogService.sync_definitions()
        assert (first.created, first.updated) == (8, 0)
        Service.objects.filter(pk="steel-supply").update(is_active=False)
        second = CatalogService.sync_definitions()
        assert (second.created, second.updated) == (0, 8)
        assert Service.objects.get(pk="steel-supply").is_active is False
        assert Service.objects.count() == 8

    def test_sync_can_reset_availability(self) -> None:
        CatalogService.sync_definitions()
        Service.objects.update(is_active=False)
        CatalogService.sync_definitions(reset_availability=True)
        assert Service.objects.filter(is_active=True).count() == 8

    def test_sync_restores_edited_definitions_but_leaves_unknown_services_alone(self) -> None:
        CatalogService.sync_definitions()
        Service.objects.filter(pk="personal-loan").update(eta_days=99)
        Service.objects.create(
            id="custom-service",
            department="loan",
            title={"fa": "الف", "en": "A"},
            summary={"fa": "الف", "en": "A"},
            description={"fa": "الف", "en": "A"},
            eta_days=3,
        )
        CatalogService.sync_definitions()
        assert Service.objects.get(pk="personal-loan").eta_days == 5
        assert Service.objects.filter(pk="custom-service").exists()

    def test_sync_refuses_a_malformed_definition(self) -> None:
        from dataclasses import replace

        broken = replace(
            SERVICE_DEFINITIONS[0],
            fields=({"kind": "text", "key": "x"},),
        )
        with pytest.raises(ValidationError):
            CatalogService.sync_definitions([broken])


@pytest.mark.django_db
@pytest.mark.usefixtures("demo")
class TestCatalogApi:
    def test_listing_is_public_ordered_and_complete(self) -> None:
        reply = Api().get("/api/catalog/services/")
        assert reply.status == 200
        services = reply.data
        assert [service["id"] for service in services] == [d.id for d in SERVICE_DEFINITIONS]
        assert all(service["isActive"] for service in services)
        first = services[0]
        assert set(first) == {
            "id",
            "departmentId",
            "title",
            "summary",
            "description",
            "requirements",
            "etaDays",
            "fields",
            "isActive",
        }
        assert first["departmentId"] == "loan"
        assert first["fields"][0]["key"] == "amount"

    def test_a_single_service_is_public_and_unknown_ones_are_not_found(self) -> None:
        assert Api().get("/api/catalog/services/personal-loan/").status == 200
        missing = Api().get("/api/catalog/services/nope/")
        assert (missing.status, missing.code) == (404, "not_found")

    def test_a_bad_token_is_not_even_looked_at_on_public_routes(self) -> None:
        reply = Api("0" * 64).get("/api/catalog/services/")
        assert reply.status == 200

    def test_the_whole_catalogue_matches_the_definitions_in_code(self) -> None:
        by_id = {service["id"]: service for service in Api().get("/api/catalog/services/").data}
        for definition in SERVICE_DEFINITIONS:
            assert by_id[definition.id]["fields"] == list(definition.fields)
            assert by_id[definition.id]["title"] == definition.title
