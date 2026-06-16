from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from scripts.normalize_siab1_branding import (
    LEGACY_APP_NAMES,
    TARGET_APP_NAME,
    async_database_url,
    redacted_database_url,
    run_cli,
    safe_database_label,
)


@dataclass
class FakeRow:
    id: int
    app_name: str


class FakeStatement(str):
    def bindparams(self, *_args, **_kwargs):
        return self


class FakeResult(list):
    rowcount: int | None = None


def fake_text(sql: str) -> FakeStatement:
    return FakeStatement(sql)


def fake_bindparam(*_args, **_kwargs):
    return object()


class FakeConn:
    def __init__(self, rows: list[dict[str, object]], *, fail: bool = False):
        self.rows = rows
        self.fail = fail
        self.updates: list[dict[str, object]] = []

    async def execute(self, stmt, params=None):
        if self.fail:
            raise RuntimeError("database unavailable")
        sql = str(stmt)
        params = params or {}
        if sql.startswith("SELECT"):
            legacy = set(params["legacy_names"])
            return FakeResult(
                [FakeRow(int(row["id"]), str(row["app_name"])) for row in self.rows if row["app_name"] in legacy]
            )
        if sql.startswith("UPDATE"):
            self.updates.append(dict(params))
            count = 0
            for row in self.rows:
                if row["id"] == params["id"] and row["app_name"] == params["before"]:
                    row["app_name"] = params["after"]
                    count += 1
            result = FakeResult()
            result.rowcount = count
            return result
        raise AssertionError(f"unexpected SQL: {sql}")


class FakeContext:
    def __init__(self, conn: FakeConn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_args):
        return False


class FakeEngine:
    def __init__(self, conn: FakeConn):
        self.conn = conn
        self.disposed = False

    def connect(self):
        return FakeContext(self.conn)

    def begin(self):
        return FakeContext(self.conn)

    async def dispose(self):
        self.disposed = True


def fake_settings(database_url="postgresql://user:secret-pass@db.example:5432/prod"):
    return SimpleNamespace(database_url=database_url, db_pool_pre_ping=True)


def make_sqlalchemy_loader(conn: FakeConn):
    def create_async_engine(url, **kwargs):
        conn.engine_url = url
        conn.engine_kwargs = kwargs
        return FakeEngine(conn)

    return lambda: (create_async_engine, fake_text, fake_bindparam)


def run_with_fake(argv, conn, settings=fake_settings()):
    out: list[str] = []
    err: list[str] = []
    code = run_cli(
        argv,
        settings_loader=lambda: settings,
        sqlalchemy_loader=make_sqlalchemy_loader(conn),
        print_fn=out.append,
        error_print_fn=err.append,
    )
    return code, out, err


def test_top_level_import_does_not_require_env():
    import scripts.normalize_siab1_branding as module

    assert module.TARGET_APP_NAME == "SIAB1"


def test_incomplete_application_environment_returns_controlled_error_without_traceback():
    err: list[str] = []
    code = run_cli(
        ["--dry-run"],
        settings_loader=lambda: (_ for _ in ()).throw(RuntimeError("Konfigurasi aplikasi tidak dapat dimuat.")),
        sqlalchemy_loader=lambda: (_ for _ in ()).throw(AssertionError("should not load SQLAlchemy")),
        print_fn=lambda _message: None,
        error_print_fn=err.append,
    )

    assert code != 0
    assert err == ["ERROR: Konfigurasi aplikasi tidak dapat dimuat."]
    assert "Traceback" not in "".join(err)


def test_error_output_does_not_print_database_credentials():
    err: list[str] = []
    code = run_cli(
        ["--dry-run"],
        settings_loader=lambda: fake_settings("postgresql://user:super-secret@db.example/prod"),
        sqlalchemy_loader=lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
        print_fn=lambda _message: None,
        error_print_fn=err.append,
    )

    assert code == 2
    assert "super-secret" not in "\n".join(err)


def test_dry_run_does_not_execute_update():
    conn = FakeConn([{"id": 1, "app_name": LEGACY_APP_NAMES[0]}])

    code, out, err = run_with_fake(["--dry-run"], conn)

    assert code == 0
    assert err == []
    assert conn.updates == []
    assert any("[DRY-RUN]" in line for line in out)


def test_apply_only_changes_exact_legacy_values_and_keeps_custom_app_name():
    conn = FakeConn(
        [
            {"id": 1, "app_name": "Ujian Online"},
            {"id": 2, "app_name": "Sistem Ujian Online"},
            {"id": 3, "app_name": "Custom School Exam"},
        ]
    )

    code, out, err = run_with_fake(["--apply"], conn)

    assert code == 0
    assert err == []
    assert conn.rows == [
        {"id": 1, "app_name": TARGET_APP_NAME},
        {"id": 2, "app_name": TARGET_APP_NAME},
        {"id": 3, "app_name": "Custom School Exam"},
    ]
    assert len(conn.updates) == 2
    assert any("Updated 2 row(s)" in line for line in out)


def test_apply_is_idempotent_after_first_run():
    conn = FakeConn([{"id": 1, "app_name": "Ujian Online"}])

    first_code, _first_out, _first_err = run_with_fake(["--apply"], conn)
    second_code, second_out, second_err = run_with_fake(["--apply"], conn)

    assert first_code == 0
    assert second_code == 0
    assert second_err == []
    assert any("No legacy app_name values found" in line for line in second_out)
    assert any("Updated 0 row(s)" in line for line in second_out)


def test_empty_result_is_success():
    conn = FakeConn([])

    code, out, err = run_with_fake(["--dry-run"], conn)

    assert code == 0
    assert err == []
    assert any("No legacy app_name values found" in line for line in out)


def test_database_error_returns_non_zero():
    conn = FakeConn([], fail=True)

    code, _out, err = run_with_fake(["--dry-run"], conn)

    assert code == 2
    assert err == ["ERROR: database unavailable"]


def test_safe_database_label_does_not_show_username_or_password():
    label = safe_database_label("postgresql://user:secret@db.example:5432/prod")

    assert label == "db.example:5432/prod"
    assert "user" not in label
    assert "secret" not in label


def test_redacted_database_url_removes_credentials():
    redacted = redacted_database_url("postgresql://user:secret@db.example:5432/prod")

    assert redacted == "postgresql://db.example:5432/prod"


def test_postgresql_url_is_converted_to_asyncpg():
    assert async_database_url("postgresql://user:pass@localhost/db") == "postgresql+asyncpg://user:pass@localhost/db"


def test_async_url_is_not_converted_again():
    url = "postgresql+asyncpg://user:pass@localhost/db"

    assert async_database_url(url) == url


def test_no_database_connection_on_argument_error():
    called = {"settings": False, "sqlalchemy": False}

    code = run_cli(
        [],
        settings_loader=lambda: called.__setitem__("settings", True),
        sqlalchemy_loader=lambda: called.__setitem__("sqlalchemy", True),
        print_fn=lambda _message: None,
        error_print_fn=lambda _message: None,
    )

    assert code != 0
    assert called == {"settings": False, "sqlalchemy": False}
