from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_SOURCE = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
COMPOSE_SOURCE = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
ENV_EXAMPLE_SOURCE = (ROOT / ".env.example").read_text(encoding="utf-8")
SAFE_MODE_DOC = (ROOT / "docs" / "production-safe-mode-deploy-20260603.md").read_text(
    encoding="utf-8"
)


def test_answer_write_defaults_are_direct_and_queue_off() -> None:
    assert 'os.getenv("ANSWER_WRITE_MODE", "direct").lower()' in CONFIG_SOURCE
    assert 'os.getenv("ANSWER_QUEUE_ENABLED", "false").lower() == "true"' in CONFIG_SOURCE
    assert 'os.getenv("ANSWER_QUEUE_PERCENTAGE", "0")' in CONFIG_SOURCE

    assert "ANSWER_WRITE_MODE=direct" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_QUEUE_ENABLED=false" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_QUEUE_PERCENTAGE=0" in ENV_EXAMPLE_SOURCE

    assert "ANSWER_WRITE_MODE=${ANSWER_WRITE_MODE:-direct}" in COMPOSE_SOURCE
    assert "ANSWER_QUEUE_ENABLED=${ANSWER_QUEUE_ENABLED:-false}" in COMPOSE_SOURCE
    assert "ANSWER_QUEUE_PERCENTAGE=${ANSWER_QUEUE_PERCENTAGE:-0}" in COMPOSE_SOURCE


def test_answer_hot_path_timing_defaults_off() -> None:
    assert 'os.getenv("ANSWER_HOT_PATH_TIMING_ENABLED", "false").lower() == "true"' in CONFIG_SOURCE
    assert 'os.getenv("ANSWER_HOT_PATH_TIMING_THRESHOLD_MS", "1000")' in CONFIG_SOURCE
    assert "ANSWER_HOT_PATH_TIMING_ENABLED=${ANSWER_HOT_PATH_TIMING_ENABLED:-false}" in COMPOSE_SOURCE
    assert "ANSWER_HOT_PATH_TIMING_THRESHOLD_MS=${ANSWER_HOT_PATH_TIMING_THRESHOLD_MS:-1000}" in COMPOSE_SOURCE


def test_mobile_first_security_defaults_stay_off_or_safe() -> None:
    assert 'os.getenv("MOBILE_APK_PRIMARY", "true").lower() == "true"' in CONFIG_SOURCE
    assert 'os.getenv("SEB_DESKTOP_LEGACY_ENABLED", "false").lower() == "true"' in CONFIG_SOURCE
    assert 'os.getenv("SEB_QR_ENABLED", "false").lower() == "true"' in CONFIG_SOURCE
    assert 'os.getenv("APK_BUILD_ENDPOINT_ENABLED", "false").lower() == "true"' in CONFIG_SOURCE
    assert 'os.getenv("TELEGRAM_ALERTING_ENABLED", "false").lower() == "true"' in CONFIG_SOURCE
    assert 'os.getenv("VIOLATION_ASYNC_ENABLED", "true").lower() == "true"' in CONFIG_SOURCE
    assert 'os.getenv(\n        "ADMIN_MONITORING_DETAIL_LEVEL",\n        "summary",\n    ).lower()' in CONFIG_SOURCE

    assert "MOBILE_APK_PRIMARY=${MOBILE_APK_PRIMARY:-true}" in COMPOSE_SOURCE
    assert "SEB_DESKTOP_LEGACY_ENABLED=${SEB_DESKTOP_LEGACY_ENABLED:-false}" in COMPOSE_SOURCE
    assert "SEB_QR_ENABLED=${SEB_QR_ENABLED:-false}" in COMPOSE_SOURCE
    assert "APK_BUILD_ENDPOINT_ENABLED=${APK_BUILD_ENDPOINT_ENABLED:-false}" in COMPOSE_SOURCE
    assert "TELEGRAM_ALERTING_ENABLED=${TELEGRAM_ALERTING_ENABLED:-false}" in COMPOSE_SOURCE
    assert "VIOLATION_ASYNC_ENABLED=${VIOLATION_ASYNC_ENABLED:-true}" in COMPOSE_SOURCE
    assert "ADMIN_MONITORING_DETAIL_LEVEL=${ADMIN_MONITORING_DETAIL_LEVEL:-summary}" in COMPOSE_SOURCE
    assert "ADMIN_MONITORING_DETAIL_LEVEL=summary" in ENV_EXAMPLE_SOURCE


def test_production_safe_mode_doc_keeps_hybrid_queue_and_apk_build_disabled() -> None:
    assert "ANSWER_WRITE_MODE=direct" in SAFE_MODE_DOC
    assert "ANSWER_QUEUE_ENABLED=false" in SAFE_MODE_DOC
    assert "ANSWER_QUEUE_PERCENTAGE=0" in SAFE_MODE_DOC
    assert "APK_BUILD_ENDPOINT_ENABLED=false" in SAFE_MODE_DOC
    assert "SEB_DESKTOP_LEGACY_ENABLED=false" in SAFE_MODE_DOC
    assert "SEB_QR_ENABLED=false" in SAFE_MODE_DOC
    assert "TELEGRAM_ALERTING_ENABLED=false" in SAFE_MODE_DOC
    assert "VIOLATION_ASYNC_ENABLED=true" in SAFE_MODE_DOC
    assert "ADMIN_MONITORING_DETAIL_LEVEL=summary" in SAFE_MODE_DOC
    assert "HEAVY_EXPORT_ENABLED=false" in SAFE_MODE_DOC

    assert "ANSWER_WRITE_MODE=hybrid    absent" in SAFE_MODE_DOC
    assert "ANSWER_WRITE_MODE=queue     absent" in SAFE_MODE_DOC
    assert "ANSWER_QUEUE_ENABLED=true   absent" in SAFE_MODE_DOC
    assert "APK_BUILD_ENDPOINT_ENABLED=true absent" in SAFE_MODE_DOC


def test_heavy_export_remains_runtime_configurable_for_peak_mode() -> None:
    assert 'os.getenv("HEAVY_EXPORT_ENABLED", "true").lower() == "true"' in CONFIG_SOURCE
    assert "HEAVY_EXPORT_ENABLED=${HEAVY_EXPORT_ENABLED:-true}" in COMPOSE_SOURCE
    assert "HEAVY_EXPORT_ENABLED=false" in SAFE_MODE_DOC


def test_runtime_buffer_shadow_defaults_are_disabled_and_non_routing() -> None:
    assert 'os.getenv("ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED", "false").lower() == "true"' in CONFIG_SOURCE
    assert 'os.getenv("ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE", "0")' in CONFIG_SOURCE
    assert '"ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS", ""' in CONFIG_SOURCE
    assert '"ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS", ""' in CONFIG_SOURCE
    assert 'os.getenv("ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS", "14400")' in CONFIG_SOURCE
    assert 'os.getenv("ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT", "100")' in CONFIG_SOURCE

    assert "ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS=14400" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT=100" in ENV_EXAMPLE_SOURCE

    expected_shadow_compose_flags = [
        "ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=${ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED:-false}",
        "ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=${ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE:-0}",
        "ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=${ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS:-}",
        "ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=${ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS:-}",
        "ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS=${ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS:-14400}",
        "ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT="
        "${ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT:-100}",
    ]
    for flag in expected_shadow_compose_flags:
        assert flag in COMPOSE_SOURCE


def test_runtime_buffer_shadow_defaults_do_not_enable_queue_or_hybrid() -> None:
    assert "ANSWER_WRITE_MODE=direct" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_QUEUE_ENABLED=false" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_QUEUE_PERCENTAGE=0" in ENV_EXAMPLE_SOURCE
    assert "ANSWER_WRITE_MODE=${ANSWER_WRITE_MODE:-direct}" in COMPOSE_SOURCE
    assert "ANSWER_QUEUE_ENABLED=${ANSWER_QUEUE_ENABLED:-false}" in COMPOSE_SOURCE
    assert "ANSWER_QUEUE_PERCENTAGE=${ANSWER_QUEUE_PERCENTAGE:-0}" in COMPOSE_SOURCE
    assert "ANSWER_WRITE_MODE=queue" not in ENV_EXAMPLE_SOURCE
    assert "ANSWER_WRITE_MODE=hybrid" not in ENV_EXAMPLE_SOURCE
    assert "ANSWER_QUEUE_ENABLED=true" not in ENV_EXAMPLE_SOURCE
