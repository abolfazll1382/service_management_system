"""Management commands and migration state."""

from __future__ import annotations

import io
import threading
from datetime import timedelta
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, connections
from django.test import override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.catalog.models import Service
from apps.core.demo.seed_data import seed_id
from apps.core.management.commands.migrate_locked import MIGRATION_LOCK_KEY
from apps.requests.models import ServiceRequest
from apps.users.models import AccessToken, User
from tests.helpers import DEMO_PASSWORD, REQ, Api, staff_api, uid

pytestmark = pytest.mark.django_db


def run(*args: Any, **options: Any) -> str:
    out = io.StringIO()
    call_command(*args, stdout=out, stderr=io.StringIO(), **options)
    return out.getvalue()


class TestMigrations:
    def test_models_and_migrations_are_in_sync(self) -> None:
        # Exits with status 1 (SystemExit) when a model change has no migration.
        call_command("makemigrations", check=True, dry_run=True, verbosity=0)

    def test_the_trigram_extension_comes_from_a_migration(self) -> None:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname='pg_trgm'")
            assert cursor.fetchone() == (1,)


class TestMigrateLocked:
    def test_runs_the_migrations_and_leaves_the_lock_free(self) -> None:
        from django.db import connection

        output = run("migrate_locked")
        assert "No migrations to apply" in output
        with connection.cursor() as cursor:
            # Unlocking a lock this session does not hold answers false: nothing is left behind.
            cursor.execute("SELECT pg_advisory_unlock(%s)", [MIGRATION_LOCK_KEY])
            assert cursor.fetchone() == (False,)

    @pytest.mark.concurrency
    @pytest.mark.django_db(transaction=True)
    def test_a_second_process_waits_until_the_first_has_finished(self) -> None:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [MIGRATION_LOCK_KEY])
        finished = threading.Event()
        failures: list[BaseException] = []

        def second_replica() -> None:
            try:
                run("migrate_locked")
                finished.set()
            except BaseException as exc:  # reported to the main thread below
                failures.append(exc)
            finally:
                connections.close_all()

        thread = threading.Thread(target=second_replica)
        thread.start()
        try:
            assert not finished.wait(timeout=1.0), "ran although the lock was held"
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [MIGRATION_LOCK_KEY])
        assert finished.wait(timeout=60), failures
        thread.join(timeout=10)
        assert not failures


class TestSeedDemoData:
    def test_creates_everything_and_a_second_run_creates_nothing(self) -> None:
        first = run("seed_demo_data")
        assert "8 account(s), 8 request(s), 8 service(s) created" in first
        assert "admin, reza, sara, ali, maryam" in first
        assert DEMO_PASSWORD in first
        second = run("seed_demo_data")
        assert "0 account(s), 0 request(s), 0 service(s) created" in second
        assert ServiceRequest.objects.count() == 8

    @override_settings(ENABLE_DEMO_RESET=False)
    def test_refuses_to_create_publicly_known_passwords_unless_demo_mode_is_on(self) -> None:
        with pytest.raises(CommandError, match="Refusing"):
            run("seed_demo_data")
        assert not User.objects.exists()

    def test_reset_with_no_input_restores_the_seed(self) -> None:
        run("seed_demo_data")
        ServiceRequest.objects.filter(pk=REQ.loan_pending).update(status="rejected")
        Service.objects.update(is_active=False)
        output = run("seed_demo_data", "--reset", "--no-input")
        assert "reset to the seed" in output
        assert ServiceRequest.objects.get(pk=REQ.loan_pending).status == "pending_review"
        assert Service.objects.filter(is_active=True).count() == 8
        assert AuditLog.objects.get().action == "demo_reset"
        assert AuditLog.objects.get().actor_id is None  # from the command line, nobody signed in

    def test_reset_asks_first_and_stops_on_anything_but_yes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run("seed_demo_data")
        ServiceRequest.objects.filter(pk=REQ.loan_pending).update(status="rejected")
        monkeypatch.setattr("builtins.input", lambda prompt="": "no")
        with pytest.raises(CommandError, match="cancelled"):
            run("seed_demo_data", "--reset")
        assert ServiceRequest.objects.get(pk=REQ.loan_pending).status == "rejected"

        monkeypatch.setattr("builtins.input", lambda prompt="": " YES ")
        run("seed_demo_data", "--reset")
        assert ServiceRequest.objects.get(pk=REQ.loan_pending).status == "pending_review"

    def test_a_foreign_account_using_a_seed_username_is_reported_as_an_error(self) -> None:
        User.objects.create(
            role="staff",
            username="reza",
            name_fa="جعلی",
            name_en="Impostor",
            department_ids=["loan"],
            password="x",
        )
        with pytest.raises(CommandError, match="username_taken"):
            run("seed_demo_data")

    def test_seeded_accounts_can_sign_in(self) -> None:
        run("seed_demo_data")
        assert staff_api("admin").me().data["role"] == "admin"


class TestSyncCatalog:
    def test_loads_and_refreshes_the_catalogue(self) -> None:
        assert "8 created, 0 updated" in run("sync_catalog")
        assert "0 created, 8 updated" in run("sync_catalog")
        assert Service.objects.count() == 8

    def test_keeps_a_paused_service_paused(self) -> None:
        run("sync_catalog")
        Service.objects.filter(pk="steel-supply").update(is_active=False)
        run("sync_catalog")
        assert Service.objects.get(pk="steel-supply").is_active is False


class TestWaitForDb:
    def test_returns_at_once_when_the_database_is_up(self) -> None:
        assert "Database is ready" in run("wait_for_db", timeout=5)

    def test_gives_up_with_an_error_after_the_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempts: list[int] = []

        def refuse() -> None:
            attempts.append(1)
            raise OperationalError("connection refused")

        monkeypatch.setattr(connections["default"], "ensure_connection", refuse)
        with pytest.raises(CommandError, match="not reachable"):
            run("wait_for_db", timeout=0.3, interval=0.05)
        assert len(attempts) >= 2

    def test_keeps_trying_until_the_database_appears(self, monkeypatch: pytest.MonkeyPatch) -> None:
        state = {"calls": 0}

        def flaky() -> None:
            state["calls"] += 1
            if state["calls"] < 3:
                raise OperationalError("starting up")

        monkeypatch.setattr(connections["default"], "ensure_connection", flaky)
        assert "Database is ready" in run("wait_for_db", timeout=5, interval=0.01)
        assert state["calls"] == 3


class TestPurgeAccessTokens:
    def make(
        self, key: str, *, expires_in: timedelta, revoked_ago: timedelta | None = None
    ) -> None:
        now = timezone.now()
        owner = User.objects.get(pk=seed_id("u-reza"))
        AccessToken.objects.create(
            user=owner,
            key_hash=key * 64,
            created_at=now - timedelta(days=30),
            expires_at=now + expires_in,
            revoked_at=now - revoked_ago if revoked_ago is not None else None,
        )

    @pytest.fixture(autouse=True)
    def tokens(self, demo: None) -> None:
        self.make("1", expires_in=timedelta(hours=1))  # live
        self.make("2", expires_in=-timedelta(days=1))  # expired yesterday (inside the grace period)
        self.make("3", expires_in=-timedelta(days=10))  # expired long ago
        self.make(
            "4", expires_in=timedelta(hours=1), revoked_ago=timedelta(days=10)
        )  # revoked long ago
        self.make(
            "5", expires_in=timedelta(hours=1), revoked_ago=timedelta(minutes=1)
        )  # just revoked

    def remaining(self) -> set[str]:
        return {key[0] for key in AccessToken.objects.values_list("key_hash", flat=True)}

    def test_deletes_only_what_is_dead_beyond_the_grace_period(self) -> None:
        assert "Deleted 2 access token(s)" in run("purge_access_tokens")
        assert self.remaining() == {"1", "2", "5"}

    def test_a_zero_day_grace_period_deletes_everything_dead_but_never_a_live_token(self) -> None:
        run("purge_access_tokens", older_than_days=0)
        assert self.remaining() == {"1"}

    def test_a_negative_grace_period_is_treated_as_zero(self) -> None:
        run("purge_access_tokens", older_than_days=-5)
        assert self.remaining() == {"1"}

    def test_is_repeatable(self) -> None:
        run("purge_access_tokens")
        assert "Deleted 0 access token(s)" in run("purge_access_tokens")


class TestBootstrapAdmin:
    ARGS = ("bootstrap_admin",)
    OPTIONS = {"username": "chief", "name_fa": "رییس", "name_en": "The Chief"}

    def test_creates_an_administrator_who_can_sign_in_and_audits_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Chief1password")
        output = run(*self.ARGS, **self.OPTIONS)
        assert "Administrator 'chief' created" in output
        user = User.objects.get(username="chief")
        assert (user.role, user.department_ids, user.is_active) == ("admin", [], True)
        assert "Chief1password" not in user.password
        reply = Api().post(
            "/api/auth/login/staff/", {"username": "chief", "password": "Chief1password"}
        )
        assert reply.status == 200
        assert reply.data["user"]["role"] == "admin"
        entry = AuditLog.objects.get(action="staff_created")
        assert entry.target == "chief"
        assert entry.actor_id == user.pk

    def test_never_takes_the_password_from_the_command_line(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Chief1password")
        with pytest.raises(CommandError, match="password"):
            call_command("bootstrap_admin", "--password", "Chief1password", **self.OPTIONS)
        assert not User.objects.filter(username="chief").exists()

    def test_prompts_twice_when_no_environment_variable_is_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
        answers = iter(["Chief1password", "Chief1password"])
        monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
        run(*self.ARGS, **self.OPTIONS)
        assert User.objects.filter(username="chief", role="admin").exists()

    def test_a_mismatched_confirmation_creates_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
        answers = iter(["Chief1password", "Chief1passwordX"])
        monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
        with pytest.raises(CommandError, match="do not match"):
            run(*self.ARGS, **self.OPTIONS)
        assert not User.objects.filter(username="chief").exists()

    @pytest.mark.parametrize(
        ("password", "options"),
        [
            ("short1", {}),
            ("alllowercase", {}),
            ("Chief1password", {"username": "Chief"}),
            ("Chief1password", {"username": "ch"}),
            ("Chief1password", {"name_en": "x"}),
        ],
    )
    def test_applies_the_same_rules_as_every_other_account(
        self, monkeypatch: pytest.MonkeyPatch, password: str, options: dict[str, str]
    ) -> None:
        monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", password)
        with pytest.raises(CommandError, match="Invalid input"):
            run(*self.ARGS, **{**self.OPTIONS, **options})
        assert not User.objects.exists()

    @pytest.mark.usefixtures("demo")
    def test_refuses_a_username_that_is_already_taken(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Chief1password")
        with pytest.raises(CommandError, match="username_taken"):
            run(*self.ARGS, **{**self.OPTIONS, "username": "reza"})
        assert User.objects.get(username="reza").role == "staff"
        assert uid("u-reza")  # the seeded account is untouched
