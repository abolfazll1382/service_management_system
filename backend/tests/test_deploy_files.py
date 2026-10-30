"""The deployment files are part of the product: keep them valid, safe and in step with the code."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class TestEntrypoint:
    def test_is_executable_and_valid_bash(self) -> None:
        path = ROOT / "entrypoint.sh"
        assert path.stat().st_mode & stat.S_IXUSR, "entrypoint.sh must be executable"
        bash = shutil.which("bash")
        assert bash, "bash is needed to check the entrypoint"
        result = subprocess.run(  # noqa: S603
            [bash, "-n", str(path)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stderr

    def test_fails_fast_and_hands_over_with_exec(self) -> None:
        script = read("entrypoint.sh")
        assert "set -Eeuo pipefail" in script
        assert script.rstrip().endswith('exec "$@"')

    def test_waits_for_the_database_before_touching_it(self) -> None:
        script = read("entrypoint.sh")
        assert script.index("wait_for_db") < script.index("migrate_locked")
        assert script.index("migrate_locked") < script.index("sync_catalog")
        assert script.index("sync_catalog") < script.index("seed_demo_data")

    def test_demo_seeding_is_off_unless_asked_for(self) -> None:
        assert "SEED_DEMO_DATA:-false" in read("entrypoint.sh")


class TestDockerfile:
    def test_is_multi_stage_with_pinned_python_and_a_non_root_runtime(self) -> None:
        text = read("Dockerfile")
        assert len(re.findall(r"^FROM ", text, flags=re.M)) >= 2
        assert ":latest" not in text
        assert "ARG PYTHON_VERSION=3." in text
        user = re.findall(r"^USER (\S+)", text, flags=re.M)
        assert user, "the image must drop root"
        assert user[-1] not in {"root", "0", "0:0"}
        assert text.index("USER ") < text.index("ENTRYPOINT")

    def test_has_a_health_check_that_needs_no_extra_tools(self) -> None:
        text = read("Dockerfile")
        assert "HEALTHCHECK" in text
        instruction = text[text.index("HEALTHCHECK") :].split("\n\n", 1)[0]
        assert "curl" not in instruction  # the slim image has none; Python is already there
        assert "/health/" in instruction

    def test_installs_only_wheels_and_no_secrets_are_baked_in(self) -> None:
        text = read("Dockerfile")
        assert "--only-binary=:all:" in text
        assert not re.search(r"(SECRET|PASSWORD)\s*=\s*\S", text)
        ignored = read(".dockerignore").split()
        assert ".env" in ignored
        assert "tests" in ignored


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    loaded = yaml.safe_load(read("docker-compose.yml"))
    assert isinstance(loaded, dict)
    return loaded


class TestCompose:
    def test_postgres_16_and_the_api_wait_for_it_to_be_healthy(
        self, compose: dict[str, Any]
    ) -> None:
        services = compose["services"]
        assert str(services["db"]["image"]).startswith("postgres:16")
        assert "healthcheck" in services["db"]
        assert services["web"]["depends_on"]["db"]["condition"] == "service_healthy"

    def test_the_demo_stack_is_only_reachable_from_this_machine(
        self, compose: dict[str, Any]
    ) -> None:
        for service in compose["services"].values():
            for published in service.get("ports", []):
                assert str(published).startswith("127.0.0.1:"), published

    def test_the_demo_settings_are_explicit_and_the_container_is_locked_down(
        self,
        compose: dict[str, Any],
    ) -> None:
        web = compose["services"]["web"]
        env = web["environment"]
        assert env["DJANGO_SETTINGS_MODULE"] == "config.settings.production"
        assert env["SEED_DEMO_DATA"] == "true"
        assert env["ENABLE_DEMO_RESET"] == "true"
        assert env["DJANGO_SECURE_SSL_REDIRECT"] == "false"  # plain HTTP on localhost
        assert web["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in web["security_opt"]

    def test_the_placeholder_secret_passes_the_production_check(
        self, compose: dict[str, Any]
    ) -> None:
        default = re.search(
            r"\$\{DJANGO_SECRET_KEY:-([^}]+)\}",
            compose["services"]["web"]["environment"]["DJANGO_SECRET_KEY"],
        )
        assert default is not None
        value = default.group(1)
        assert len(value) >= 50
        assert not value.startswith("django-insecure")


def _variables_read_by_the_code() -> set[str]:
    """Every environment variable the settings, gunicorn config and entrypoint look at."""
    names: set[str] = set()
    for path in [*(ROOT / "config" / "settings").glob("*.py"), ROOT / "gunicorn.conf.py"]:
        if path.name == "test.py":
            continue
        text = path.read_text(encoding="utf-8")
        names |= set(
            re.findall(r'env\.(?:str|int|bool|list|db|cache)\(\s*"([A-Z][A-Z0-9_]+)"', text)
        )
        names |= set(re.findall(r'_int\(\s*"([A-Z][A-Z0-9_]+)"', text))
        names |= set(re.findall(r'os\.environ\.get\(\s*"([A-Z][A-Z0-9_]+)"', text))
    names |= set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)[:}-]", read("entrypoint.sh")))
    names.discard("DJANGO_SETTINGS_MODULE")  # set by the image / manage.py, not a tuning knob
    return names


class TestDocumentationKeepsUp:
    def test_the_scan_really_finds_the_settings(self) -> None:
        found = _variables_read_by_the_code()
        assert {"DJANGO_SECRET_KEY", "DATABASE_URL", "WEB_CONCURRENCY", "RUN_MIGRATIONS"} <= found
        assert len(found) >= 25

    def test_every_variable_the_code_reads_is_in_env_example(self) -> None:
        documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", read(".env.example"), flags=re.M))
        missing = _variables_read_by_the_code() - documented
        assert not missing, f"add to .env.example: {sorted(missing)}"

    def test_every_variable_the_code_reads_is_in_the_readme(self) -> None:
        readme = read("README.md")
        missing = {name for name in _variables_read_by_the_code() if f"`{name}`" not in readme}
        assert not missing, f"add to the README configuration table: {sorted(missing)}"

    def test_env_example_never_ships_a_real_looking_secret(self) -> None:
        for line in read(".env.example").splitlines():
            if line.startswith("DJANGO_SECRET_KEY="):
                assert line == "DJANGO_SECRET_KEY=", "leave the secret key empty in the example"
        assert "Demo@1234" not in read(".env.example")


def test_the_access_log_never_records_query_strings() -> None:
    """``search`` may hold a national ID or phone number: log the path, not the request line."""
    config = read("gunicorn.conf.py")
    match = re.search(r"^access_log_format = (.+)$", config, flags=re.M)
    assert match, "gunicorn.conf.py must set access_log_format"
    log_format = match.group(1)
    assert "%(r)s" not in log_format  # the full request line includes ?query
    assert "%(q)s" not in log_format
    assert "%(U)s" in log_format


def test_the_scripts_are_not_world_writable() -> None:
    for name in ("entrypoint.sh", "gunicorn.conf.py", "manage.py"):
        mode = (ROOT / name).stat().st_mode
        assert not mode & stat.S_IWOTH, f"{name} is world-writable ({oct(mode)})"
    assert os.access(ROOT / "manage.py", os.R_OK)
