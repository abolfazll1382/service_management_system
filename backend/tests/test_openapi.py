"""The generated API description and the docs page."""

from __future__ import annotations

import io
import json
import re
from typing import Any

import pytest
import yaml
from django.core.management import call_command

from tests.helpers import Api

EXPECTED_OPERATIONS = {
    ("/api/auth/register/", "post"),
    ("/api/auth/login/customer/", "post"),
    ("/api/auth/login/staff/", "post"),
    ("/api/auth/logout/", "post"),
    ("/api/auth/me/", "get"),
    ("/api/catalog/services/", "get"),
    ("/api/catalog/services/{service_id}/", "get"),
    ("/api/catalog/services/{service_id}/active/", "patch"),
    ("/api/requests/", "post"),
    ("/api/requests/mine/", "get"),
    ("/api/requests/queue/", "get"),
    ("/api/requests/assignable-staff/", "get"),
    ("/api/requests/{request_id}/", "get"),
    ("/api/requests/{request_id}/transition/", "post"),
    ("/api/requests/{request_id}/assign/", "post"),
    ("/api/requests/{request_id}/messages/", "post"),
    ("/api/staff/", "get"),
    ("/api/staff/", "post"),
    ("/api/staff/{staff_id}/", "patch"),
    ("/api/audit/", "get"),
    ("/api/demo/reset/", "post"),
    ("/health/", "get"),
}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    out = io.StringIO()
    call_command("spectacular", validate=True, fail_on_warn=True, format="openapi-json", stdout=out)
    loaded: dict[str, Any] = json.loads(out.getvalue())
    return loaded


def test_the_schema_validates_without_a_single_warning(schema: dict[str, Any]) -> None:
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"]


def test_every_documented_endpoint_is_described_and_nothing_else(schema: dict[str, Any]) -> None:
    operations = {
        (path, method)
        for path, item in schema["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert operations == EXPECTED_OPERATIONS


def test_the_bearer_scheme_is_defined_and_applied_to_protected_operations_only(
    schema: dict[str, Any],
) -> None:
    assert schema["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    paths = schema["paths"]
    assert {"bearerAuth": []} in paths["/api/requests/queue/"]["get"]["security"]
    assert {"bearerAuth": []} in paths["/api/staff/"]["get"]["security"]
    for public in (
        paths["/api/auth/login/staff/"]["post"],
        paths["/api/auth/register/"]["post"],
        paths["/api/catalog/services/"]["get"],
        paths["/health/"]["get"],
    ):
        # ``[{}]`` is OpenAPI's way of saying "no credentials needed".
        assert not any(public.get("security", [])), public["operationId"]


def test_every_operation_documents_the_shared_error_body(schema: dict[str, Any]) -> None:
    assert schema["components"]["schemas"]["ApiError"]["required"] == ["code", "detail", "errors"]
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            default = operation["responses"]["default"]
            ref = default["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ApiError"), (path, method)


def test_operations_that_take_input_document_400_and_protected_ones_401(
    schema: dict[str, Any],
) -> None:
    post = schema["paths"]["/api/requests/"]["post"]["responses"]
    assert {"201", "400", "401", "default"} <= set(post)
    assert "401" not in schema["paths"]["/api/auth/login/staff/"]["post"]["responses"]


def test_the_error_codes_in_the_schema_are_the_ones_the_code_defines(
    schema: dict[str, Any],
) -> None:
    from apps.core.exceptions import ApiErrorCode

    assert set(schema["components"]["schemas"]["ApiError"]["properties"]["code"]["enum"]) == {
        code.value for code in ApiErrorCode
    }


def test_each_value_set_has_one_stable_name(schema: dict[str, Any]) -> None:
    names = set(schema["components"]["schemas"])
    assert {"DepartmentEnum", "RequestStatusEnum", "MessageVisibilityEnum"} <= names
    assert not any(name.endswith("Enum") and name.startswith(("To", "From")) for name in names)


def test_the_timeline_and_the_user_are_discriminated_unions(schema: dict[str, Any]) -> None:
    schemas = schema["components"]["schemas"]
    assert schemas["TimelineEvent"]["discriminator"]["propertyName"] == "kind"
    assert set(schemas["TimelineEvent"]["discriminator"]["mapping"]) == {
        "submitted",
        "status_changed",
        "assigned",
        "message",
    }
    assert schemas["PublicUser"]["discriminator"]["propertyName"] == "role"
    assert "from" in schemas["StatusChangedEvent"]["properties"]


def test_the_queue_documents_its_filters_and_counts(schema: dict[str, Any]) -> None:
    queue = schema["paths"]["/api/requests/queue/"]["get"]
    parameters = {parameter["name"] for parameter in queue["parameters"]}
    assert parameters == {"status", "departmentId", "assignment", "search", "page", "pageSize"}
    page = schema["components"]["schemas"]["RequestPage"]
    assert set(page["properties"]) == {"items", "total", "page", "pageSize", "counts"}


def test_the_checked_in_schema_file_is_not_expected_to_exist() -> None:
    # The schema is generated from the code (`make schema`); a stale copy would be a second truth.
    from pathlib import Path

    assert not (Path(__file__).resolve().parent.parent / "openapi.yml").exists()


class TestDocsPage:
    def test_the_schema_is_served_as_yaml_and_json(self) -> None:
        yaml_reply = Api().client.get("/api/schema/")
        assert yaml_reply.status_code == 200
        assert yaml.safe_load(yaml_reply.content)["openapi"].startswith("3.")
        json_reply = Api().client.get("/api/schema/?format=json")
        assert json_reply.json()["info"]["title"]

    def test_the_swagger_page_loads_pinned_assets(self) -> None:
        reply = Api().client.get("/api/docs/")
        assert reply.status_code == 200
        html = reply.content.decode()
        assert "swagger-ui-dist@5.17.14" in html
        assert "@latest" not in html
        assert re.search(r"/api/schema/", html)

    def test_the_docs_are_off_unless_enabled(self) -> None:
        import subprocess
        import sys

        code = (
            "import django;django.setup();"
            "from django.test import Client;"
            "print(Client().get('/api/docs/').status_code)"
        )
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=_env(
                {"DJANGO_SETTINGS_MODULE": "config.settings.base", "ENABLE_API_DOCS": "false"}
            ),
            check=False,
        )
        assert result.stdout.strip() == "404", result.stderr


def _env(extra: dict[str, str]) -> dict[str, str]:
    import os

    env = {**os.environ, **extra}
    env.setdefault("DATABASE_URL", "postgres://portal:portal@localhost:5432/portal")
    env.setdefault("DJANGO_SECRET_KEY", "x" * 60)
    env.setdefault("DJANGO_ALLOWED_HOSTS", "testserver")
    return env
