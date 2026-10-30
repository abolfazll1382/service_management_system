"""Deployment configuration: what production refuses to start without, and ``check --deploy``.

Each case starts a fresh interpreter, because settings are read once per process.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
SECRET = "k" * 20 + "Zq9" * 10 + "-unit-test-only-secret-key-value"
GOOD = {"DJANGO_SECRET_KEY": SECRET, "DJANGO_ALLOWED_HOSTS": "api.example.org"}

#: Environment variables this suite controls itself; anything else from the outer shell is dropped.
_OWNED_PREFIXES = ("DJANGO_", "ENABLE_", "DATABASE_", "CORS_", "CACHE_", "THROTTLE_", "NUM_PROXIES")


def _environment(settings_module: str, overrides: dict[str, str]) -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith(_OWNED_PREFIXES)
    }
    environment["DJANGO_SETTINGS_MODULE"] = settings_module
    environment["DATABASE_URL"] = "postgres://portal:portal@localhost:5432/portal"
    environment.update(overrides)
    return environment


def manage(
    *args: str, settings: str = "config.settings.production", **env: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "manage.py", *args],
        cwd=BACKEND,
        env=_environment(settings, env),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def evaluate(
    code: str, *, settings: str = "config.settings.production", **env: str
) -> subprocess.CompletedProcess[str]:
    """Run ``code`` after ``django.setup()`` and return what it printed."""
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", f"import django; django.setup()\n{code}"],
        cwd=BACKEND,
        env=_environment(settings, env),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def printed(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The words on the last line of output (log lines, written to stdout, may precede it)."""
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return lines[-1].split() if lines else []


class TestProductionSettings:
    def test_pass_the_deployment_checks_without_warnings(self) -> None:
        result = manage("check", "--deploy", "--fail-level", "WARNING", **GOOD)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "no issues" in result.stdout

    def test_hsts_preload_is_an_opt_in_that_still_passes_the_checks(self) -> None:
        result = manage(
            "check",
            "--deploy",
            "--fail-level",
            "WARNING",
            DJANGO_SECURE_HSTS_PRELOAD="true",
            **GOOD,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    @pytest.mark.parametrize(
        "weak",
        [
            {"DJANGO_SECURE_HSTS_SECONDS": "3600"},
            {"DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "false"},
        ],
    )
    def test_hsts_preload_refuses_settings_that_browsers_would_reject(
        self, weak: dict[str, str]
    ) -> None:
        result = manage("check", DJANGO_SECURE_HSTS_PRELOAD="true", **weak, **GOOD)
        assert result.returncode != 0
        assert "DJANGO_SECURE_HSTS_PRELOAD" in result.stderr

    def test_refuse_to_start_without_a_secret_key(self) -> None:
        result = manage("check", DJANGO_ALLOWED_HOSTS="api.example.org")
        assert result.returncode != 0
        assert "DJANGO_SECRET_KEY" in result.stderr

    @pytest.mark.parametrize("secret", ["short", "django-insecure-" + "x" * 60])
    def test_refuse_a_weak_or_placeholder_secret_key(self, secret: str) -> None:
        result = manage("check", DJANGO_SECRET_KEY=secret, DJANGO_ALLOWED_HOSTS="api.example.org")
        assert result.returncode != 0
        assert "DJANGO_SECRET_KEY" in result.stderr

    def test_refuse_to_start_without_allowed_hosts(self) -> None:
        result = manage("check", DJANGO_SECRET_KEY=SECRET)
        assert result.returncode != 0
        assert "DJANGO_ALLOWED_HOSTS" in result.stderr

    def test_demo_tools_and_docs_are_off_by_default(self) -> None:
        result = evaluate(
            "from django.conf import settings as s\n"
            "print(s.ENABLE_DEMO_RESET, s.ENABLE_API_DOCS, s.DEBUG)",
            **GOOD,
        )
        assert printed(result) == ["False", "False", "False"]

    def test_demo_tools_and_docs_can_be_switched_on_for_a_demo_deployment(self) -> None:
        result = evaluate(
            "from django.conf import settings as s\nprint(s.ENABLE_DEMO_RESET, s.ENABLE_API_DOCS)",
            ENABLE_DEMO_RESET="true",
            ENABLE_API_DOCS="true",
            **GOOD,
        )
        assert printed(result) == ["True", "True"]

    def test_https_is_enforced_but_probes_are_exempt(self) -> None:
        # /api/auth/me/ answers 401 without touching the database, so no schema is needed here.
        result = evaluate(
            "from django.test import Client\n"
            "client = Client(HTTP_HOST='api.example.org')\n"
            "plain = client.get('/api/auth/me/')\n"
            "probe = client.get('/health/')\n"
            "secure = client.get('/api/auth/me/', secure=True)\n"
            "print(plain.status_code, probe.status_code, secure.status_code,"
            " plain.headers.get('Location'), secure.headers.get('Strict-Transport-Security'))",
            **GOOD,
        )
        plain, probe, secure, location, *hsts = printed(result)  # the header value contains a space
        assert (plain, probe, secure) == ("301", "200", "401")
        assert location == "https://api.example.org/api/auth/me/"
        assert " ".join(hsts) == "max-age=31536000; includeSubDomains"

    def test_an_unlisted_host_is_refused(self) -> None:
        result = evaluate(
            "from django.test import Client\n"
            "print(Client(HTTP_HOST='evil.example').get('/health/', secure=True).status_code)",
            **GOOD,
        )
        assert printed(result) == ["400"]

    def test_the_proxy_header_is_trusted_only_when_declared(self) -> None:
        code = "from django.conf import settings as s\nprint(s.SECURE_PROXY_SSL_HEADER)"
        assert "HTTP_X_FORWARDED_PROTO" in evaluate(code, **GOOD).stdout
        assert printed(evaluate(code, DJANGO_BEHIND_PROXY="false", **GOOD)) == ["None"]

    def test_the_container_health_check_can_reach_the_app_by_loopback(self) -> None:
        result = evaluate("from django.conf import settings as s\nprint(*s.ALLOWED_HOSTS)", **GOOD)
        assert printed(result) == ["api.example.org", "127.0.0.1", "localhost"]


class TestBaseSettings:
    BASE = "config.settings.base"

    def test_nothing_is_enabled_by_accident(self) -> None:
        result = evaluate(
            "from django.conf import settings as s\n"
            "print(s.DEBUG, s.ENABLE_DEMO_RESET, s.ENABLE_API_DOCS, s.APPEND_SLASH,"
            " s.CORS_ALLOW_CREDENTIALS)",
            settings=self.BASE,
            DJANGO_SECRET_KEY=SECRET,
        )
        assert printed(result) == ["False", "False", "False", "False", "False"]

    def test_the_throttle_rates_come_from_the_environment(self) -> None:
        result = evaluate(
            "from django.conf import settings as s\n"
            "print(s.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['auth_login'])",
            settings=self.BASE,
            DJANGO_SECRET_KEY=SECRET,
            THROTTLE_AUTH_LOGIN="7/min",
        )
        assert printed(result) == ["7/min"]

    def test_cors_origins_are_an_explicit_allow_list(self) -> None:
        result = evaluate(
            "from django.conf import settings as s\nprint(*s.CORS_ALLOWED_ORIGINS)",
            settings=self.BASE,
            DJANGO_SECRET_KEY=SECRET,
            CORS_ALLOWED_ORIGINS="https://app.example.org,https://admin.example.org",
        )
        assert printed(result) == ["https://app.example.org", "https://admin.example.org"]

    def test_a_missing_database_url_is_a_clear_error(self) -> None:
        env = _environment(self.BASE, {"DJANGO_SECRET_KEY": SECRET})
        del env["DATABASE_URL"]
        result = subprocess.run(
            [sys.executable, "manage.py", "check"],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode != 0
        assert "DATABASE_URL" in result.stderr
