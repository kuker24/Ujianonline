from pathlib import Path


MONITORING_SOURCE = Path("app/api/monitoring.py").read_text(encoding="utf-8")
SCHEMAS_SOURCE = Path("app/api/monitoring_schemas.py").read_text(encoding="utf-8")
MONITORING_JS_SOURCE = Path("static/js/admin/monitoring.js").read_text(encoding="utf-8")
API_MODULE_SOURCE = Path("static/js/api/modules/20-endpoints-grading-monitoring-templates.js").read_text(encoding="utf-8")


def test_restart_safe_has_distributed_exec_lock_guard() -> None:
    assert "RESTART_SAFE_EXEC_LOCK_KEY" in MONITORING_SOURCE
    assert "RESTART_ALREADY_IN_PROGRESS" in MONITORING_SOURCE
    assert "_acquire_restart_safe_exec_lock(current_user.username)" in MONITORING_SOURCE


def test_restart_safe_has_full_restart_cooldown_guard() -> None:
    assert "RESTART_SAFE_FULL_COOLDOWN_SECONDS" in MONITORING_SOURCE
    assert "RESTART_COOLDOWN_ACTIVE" in MONITORING_SOURCE
    assert '"cooldown": cooldown_state' in MONITORING_SOURCE


def test_restart_safe_allows_short_inter_session_gap_with_warning() -> None:
    assert "minimum_gap_minutes = 5" in MONITORING_SOURCE
    assert "imminent_exams_count == 0" in MONITORING_SOURCE
    assert "upcoming_exams_count == 0" not in MONITORING_SOURCE.split("guard_ok =", 1)[1].split("if not guard_ok", 1)[0]
    assert '"warnings": warnings' in MONITORING_SOURCE
    assert "Ada ujian terjadwal dalam buffer operator" in MONITORING_SOURCE


def test_restart_safe_defaults_do_not_restart_data_services() -> None:
    assert "include_data_services: bool = False" in SCHEMAS_SOURCE
    assert "includeDataServices = false" in API_MODULE_SOURCE
    assert "const includeDataServices = false" in MONITORING_JS_SOURCE
    assert "Restart DB/Redis/PgBouncer" in MONITORING_JS_SOURCE


def test_restart_button_runs_dry_run_preflight_before_execution() -> None:
    assert "const preflight = await runRestartRequest(true)" in MONITORING_JS_SOURCE
    assert "const result = await runRestartRequest(false)" in MONITORING_JS_SOURCE
    assert "Preflight aman" in MONITORING_JS_SOURCE
