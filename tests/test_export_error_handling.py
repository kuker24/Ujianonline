import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import analytics, exam_exports, monitoring, users
from app.core.export_utils import content_disposition_attachment, safe_ascii_filename
from app.core.feature_flags import HEAVY_EXPORT_DISABLED_MESSAGE, feature_disabled_exception
from app.core.pdf_generator import (
    REPORTLAB_AVAILABLE,
    generate_exam_analytics_pdf,
    generate_exam_results_pdf,
    generate_violations_report_pdf,
)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for frontend parser smoke")
def test_frontend_api_error_parser_handles_strings_objects_validation_and_text() -> None:
    script = r'''
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const storage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
const element = () => ({
  style: {},
  classList: { add() {}, remove() {}, toggle() {} },
  appendChild() {},
  remove() {},
  addEventListener() {},
  set textContent(_) {},
  set innerHTML(_) {},
});
const sandbox = {
  window: {
    location: { origin: 'https://example.test', pathname: '/admin/results.html', search: '', href: '' },
    localStorage: storage,
    URLSearchParams,
    setTimeout: () => 1,
    clearTimeout: () => {},
    addEventListener() {},
    removeEventListener() {},
  },
  localStorage: storage,
  console: { log() {}, debug() {}, info() {}, warn() {}, error() {} },
  document: {
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: element,
    addEventListener() {},
    removeEventListener() {},
    head: { appendChild() {} },
    body: { appendChild() {} },
  },
  setTimeout: () => 1,
  clearTimeout: () => {},
  URLSearchParams,
  FormData: class FormData {},
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  Response,
};
sandbox.window.window = sandbox.window;
sandbox.window.document = sandbox.document;
vm.runInNewContext(fs.readFileSync('static/js/api.js', 'utf8'), sandbox);
const parse = sandbox.window.extractApiErrorMessage;
const read = sandbox.window.readApiErrorMessage;
assert.strictEqual(parse({ detail: 'abc' }), 'abc');
assert.strictEqual(parse({ detail: { message: 'fitur off' } }), 'fitur off');
assert.strictEqual(
  parse({ detail: { error: 'FEATURE_DISABLED', feature: 'heavy_export', message: 'Ekspor berat sedang dinonaktifkan selama mode ujian/puncak.' } }),
  'Ekspor berat sedang dinonaktifkan selama mode ujian/puncak.'
);
assert.strictEqual(
  parse({ detail: [{ loc: ['query', 'format'], msg: 'Input should be csv' }, { msg: 'wajib diisi' }] }),
  'query.format: Input should be csv; wajib diisi'
);
(async () => {
  assert.strictEqual(await read(new Response('plain failure', { status: 503, statusText: 'Service Unavailable' })), 'plain failure');
  console.log(JSON.stringify({ ok: true }));
})().catch((err) => { console.error(err); process.exit(1); });
'''
    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout.strip())["ok"] is True


def test_feature_disabled_exception_has_human_message_for_heavy_export() -> None:
    exc = feature_disabled_exception("heavy_export", status_code=503)

    assert exc.status_code == 503
    assert exc.detail["error"] == "FEATURE_DISABLED"
    assert exc.detail["feature"] == "heavy_export"
    assert exc.detail["message"] == HEAVY_EXPORT_DISABLED_MESSAGE
    assert "[object Object]" not in json.dumps(exc.detail)


@pytest.mark.asyncio
async def test_export_endpoints_return_503_with_human_feature_disabled_message(monkeypatch) -> None:
    for module in (monitoring, exam_exports, analytics, users):
        monkeypatch.setattr(module.settings, "heavy_export_enabled", False)
        monkeypatch.setattr(module.settings, "exam_peak_mode", False)

    dummy_user = SimpleNamespace(id=7, role="admin", is_admin=True)
    dummy_db = SimpleNamespace()

    calls = [
        monitoring.export_violations_dashboard(current_user=dummy_user, db=dummy_db),
        exam_exports.get_exam_results_pdf(exam_id=1, current_user=dummy_user, db=dummy_db),
        exam_exports.get_exam_analytics_pdf(exam_id=1, current_user=dummy_user, db=dummy_db),
        analytics.export_exam_assessment_docx(exam_id=1, current_user=dummy_user, db=dummy_db),
        users.export_users(current_user=dummy_user, db=dummy_db),
    ]

    for coro in calls:
        with pytest.raises(HTTPException) as exc_info:
            await coro
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["message"] == HEAVY_EXPORT_DISABLED_MESSAGE


def _violation_log(**overrides):
    now = overrides.pop("created_at", datetime(2026, 3, 6, 8, 0, tzinfo=timezone.utc))
    user = SimpleNamespace(id=10, full_name="Budi Santoso", username="budi", student_class="XII IPA 1")
    exam = SimpleNamespace(title="Try Out Matematika")
    session = SimpleNamespace(
        id=1001,
        exam_id=101,
        user=user,
        exam=exam,
        archived_exam_title=None,
    )
    payload = {
        "id": 1,
        "session_id": 1001,
        "event_type": "violation_copy",
        "event_data": {"details": "Menekan Ctrl+C", "action": "keyboard_ctrl_c", "source": "web"},
        "created_at": now,
        "session": session,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_export_pdf_generators_return_pdf_bytes() -> None:
    if not REPORTLAB_AVAILABLE:
        pytest.skip("reportlab not installed")

    violation_payload = monitoring._build_violations_dashboard_payload(
        [_violation_log(), _violation_log(id=2, created_at=datetime(2026, 3, 6, 7, 50, tzinfo=timezone.utc))],
        exam_id=None,
        date_from=datetime(2026, 3, 5, tzinfo=timezone.utc),
        date_to=datetime(2026, 3, 6, tzinfo=timezone.utc),
        selected_exam_title=None,
    )
    assert generate_violations_report_pdf(violation_payload).startswith(b"%PDF")

    assert generate_exam_results_pdf(
        exam_title="Ujian / Quote \"Unicode ✓\"",
        exam_date="17 Juni 2026",
        results=[{"student_name": "Siswa A", "student_class": "XI IPA", "score": 88.0, "passed": True}],
        summary={"average": 88, "highest": 88, "lowest": 88, "passed": 1, "failed": 0, "pass_rate": 100},
        creator_name="Guru A",
    ).startswith(b"%PDF")

    analytics_payload = {
        "exam": {"title": "Analitik / Unicode ✓", "subject": "Biologi", "teacher_name": "Guru A", "passing_score": 70},
        "overview": {
            "total_participants": 2,
            "completed_sessions": 2,
            "active_sessions": 0,
            "average_score": 75,
            "highest_score": 90,
            "lowest_score": 60,
            "pass_rate": 50,
            "violation_stats": {"total_violations": 0},
            "score_distribution": {"61-80": 1, "81-100": 1},
        },
        "score_distribution": {"61-80": 1, "81-100": 1},
        "question_analysis": [{"question_number": 1, "question_text": "Contoh soal", "total_answers": 2, "correct_answers": 1, "correct_rate": 50, "difficulty": "medium"}],
        "class_performance": None,
        "class_filter": "XI IPA",
        "generated_at": "Jumat, 19 Juni 2026 08:00 WIB",
    }
    assert generate_exam_analytics_pdf(analytics_payload).startswith(b"%PDF")


def test_content_disposition_sanitizes_ascii_fallback_and_preserves_utf8_filename_star() -> None:
    raw = 'hasil / ujian "Biologi ✓".pdf'
    header = content_disposition_attachment(raw, fallback="hasil.pdf")

    assert 'filename="hasil_ujian_Biologi.pdf"' in header
    assert "filename*=UTF-8''hasil%20%2F%20ujian%20%22Biologi%20%E2%9C%93%22.pdf" in header
    assert '"Biologi ✓"' not in header
    assert safe_ascii_filename('../danger/試験.pdf', fallback='export.pdf') == 'danger.pdf'
