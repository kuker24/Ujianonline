from pathlib import Path
import re


EXAMS_SOURCE = Path("app/api/exams.py").read_text(encoding="utf-8")
ANSWER_PROCESSOR_SOURCE = Path("app/tasks/answer_processor.py").read_text(encoding="utf-8")
ANSWER_SYNC_SERVICE_SOURCE = Path("app/services/answer_sync_service.py").read_text(encoding="utf-8")
UPLOAD_SOURCE = Path("app/api/upload.py").read_text(encoding="utf-8")
BACKUP_SOURCE = Path("app/api/backup.py").read_text(encoding="utf-8")


def _extract_async_function(source: str, function_name: str) -> str:
    pattern = re.compile(
        rf"async def {re.escape(function_name)}\([\s\S]*?(?=\n@router|\nasync def |\ndef |\nclass |\Z)",
        re.MULTILINE,
    )
    match = pattern.search(source)
    assert match is not None, f"Function {function_name} not found"
    return match.group(0)


def test_submit_answer_rechecks_session_under_write_lock() -> None:
    fn = _extract_async_function(EXAMS_SOURCE, "submit_answer")
    assert "session_status != \"in_progress\"" in fn
    assert "Sesi ujian sudah dikumpulkan. Jawaban tambahan diabaikan." in fn
    assert "await validate_seb_headers(request, exam_id, db, require_seb=True)" in fn
    assert "except HTTPException as exc:" in fn


def test_auto_save_batch_serializes_session_writes() -> None:
    endpoint_fn = _extract_async_function(EXAMS_SOURCE, "auto_save_batch")
    assert "get_answer_sync_service" in endpoint_fn
    assert "accept_batch" in endpoint_fn
    assert "_acquire_session_write_lock" in ANSWER_SYNC_SERVICE_SOURCE
    assert "_ensure_session_in_progress_for_user" in ANSWER_SYNC_SERVICE_SOURCE
    assert "write conflict, retrying serialized merge" in ANSWER_SYNC_SERVICE_SOURCE


def test_submit_exam_takes_session_lock_before_finalize() -> None:
    fn = _extract_async_function(EXAMS_SOURCE, "submit_exam")
    assert "_acquire_session_write_lock" in fn
    assert ".with_for_update()" in fn
    assert "finalize_exam_session_submission" in fn


def test_log_violation_uses_atomic_increment() -> None:
    fn = _extract_async_function(EXAMS_SOURCE, "log_violation")
    assert "func.coalesce(ExamSession.violation_count, 0) + increment_value" in fn
    assert ".returning(" in fn


def test_log_violation_ignores_closed_or_transitioned_sessions() -> None:
    fn = _extract_async_function(EXAMS_SOURCE, "log_violation")
    assert "terminal_session_statuses" in fn
    assert "return _ignored_violation_response(" in fn
    assert 'status="ignored"' in EXAMS_SOURCE
    assert "ExamSession.status.in_(active_session_statuses)" in fn
    assert "Ignored violation for closed session" in fn


def test_answer_queue_uses_processing_queue_for_durability() -> None:
    assert 'PROCESSING_QUEUE_KEY = "answer_queue:processing"' in ANSWER_PROCESSOR_SOURCE
    assert "_rescue_stuck_processing_items" in ANSWER_PROCESSOR_SOURCE
    assert "_restore_processing_batch" in ANSWER_PROCESSOR_SOURCE
    assert 'PENDING_QUEUE_KEY,\n            PROCESSING_QUEUE_KEY' in ANSWER_PROCESSOR_SOURCE


def test_upload_stream_is_processed_off_event_loop() -> None:
    assert "asyncio.to_thread(_measure_upload_size, file)" in UPLOAD_SOURCE
    assert "asyncio.to_thread(_save_upload_stream, file, file_path)" in UPLOAD_SOURCE
    assert "await file.read()" not in UPLOAD_SOURCE


def test_backup_export_avoids_blocking_gpg_and_n_plus_one() -> None:
    assert "asyncio.to_thread(" in BACKUP_SOURCE
    assert "_run_gpg_encrypt" in BACKUP_SOURCE
    assert "selectinload(Exam.questions).selectinload(Question.options)" in BACKUP_SOURCE
    assert "selectinload(ExamSession.user)" in BACKUP_SOURCE
