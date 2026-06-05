from pathlib import Path


MONITORING_API_SOURCE = Path("app/api/monitoring.py").read_text(encoding="utf-8")
MONITORING_JS_SOURCE = Path("static/js/admin/monitoring.js").read_text(encoding="utf-8")
MONITORING_TEMPLATE_SOURCE = Path("templates/admin/monitoring.html").read_text(encoding="utf-8")
API_MODULE_SOURCE = Path("static/js/api/modules/20-endpoints-grading-monitoring-templates.js").read_text(encoding="utf-8")


def _extract_endpoint_function(source: str, function_name: str) -> str:
    marker = f"async def {function_name}"
    start = source.index(marker)
    next_route = source.find("\n@router.", start + len(marker))
    if next_route == -1:
        return source[start:]
    return source[start:next_route]


def test_violation_pipeline_health_endpoint_is_admin_only() -> None:
    assert '@router.get("/violation-pipeline-health")' in MONITORING_API_SOURCE
    fn = _extract_endpoint_function(MONITORING_API_SOURCE, "get_violation_pipeline_health")
    assert "get_current_active_admin" in fn
    assert "get_db_read" in fn


def test_violation_pipeline_health_returns_sanitized_aggregate_fields() -> None:
    fn = _extract_endpoint_function(MONITORING_API_SOURCE, "get_violation_pipeline_health")
    expected_fields = [
        '"enabled"',
        '"mode"',
        '"redis_pending"',
        '"redis_deadletter"',
        '"db_events_last_15m"',
        '"db_events_last_24h"',
        '"security_events_last_24h"',
        '"apk_token_rejected_last_24h"',
        '"sessions_with_violation_count_last_24h"',
        '"suspicious_sessions_last_24h"',
        '"last_violation_event_at"',
        '"last_security_event_at"',
        '"worker_alive"',
        '"warnings"',
    ]
    for field in expected_fields:
        assert field in fn
    forbidden_raw_terms = ["authorization", "cookie", "raw_token", "session_token", "answer_text"]
    lowered = fn.lower()
    for term in forbidden_raw_terms:
        assert term not in lowered


def test_violation_pipeline_health_uses_naive_utc_db_cutoffs() -> None:
    fn = _extract_endpoint_function(MONITORING_API_SOURCE, "get_violation_pipeline_health")
    assert "datetime.utcnow()" in fn
    assert "TIMESTAMP WITHOUT TIME ZONE" in fn
    assert "datetime.now(timezone.utc)" not in fn


def test_violation_pipeline_health_handles_live_schema_suspicious_column_fallback() -> None:
    fn = _extract_endpoint_function(MONITORING_API_SOURCE, "get_violation_pipeline_health")
    assert 'getattr(ExamSession, "is_suspicious", None)' in fn
    assert "select count(*) from exam_sessions" in fn
    assert "is_suspicious = true" in fn


def test_violation_pipeline_health_separates_apk_rejects_from_cheating_events() -> None:
    fn = _extract_endpoint_function(MONITORING_API_SOURCE, "get_violation_pipeline_health")
    assert "SecurityEvent" in fn
    assert 'SecurityEvent.event_type == "APK_TOKEN_REJECTED"' in fn
    assert 'ExamLog.event_type.ilike("violation_%")' in fn
    assert "APK token/signature reject" in fn


def test_monitoring_dashboard_displays_violation_pipeline_summary() -> None:
    assert 'id="ops-violation-pipeline-detail"' in MONITORING_TEMPLATE_SOURCE
    assert "renderViolationPipelineHealth" in MONITORING_JS_SOURCE
    assert "loadViolationPipelineHealth" in MONITORING_JS_SOURCE
    assert "APK token/signature issue" in MONITORING_JS_SOURCE
    assert "Redis pending/deadletter" in MONITORING_JS_SOURCE
    assert "getViolationPipelineHealth" in API_MODULE_SOURCE


def test_violation_pipeline_health_does_not_enable_answer_queue_or_runtime_buffer() -> None:
    fn = _extract_endpoint_function(MONITORING_API_SOURCE, "get_violation_pipeline_health")
    assert "ANSWER_QUEUE_ENABLED" not in fn
    assert "ANSWER_WRITE_MODE" not in fn
    assert "answer_runtime_buffer" not in fn
