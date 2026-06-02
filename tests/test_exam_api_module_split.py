from pathlib import Path


EXAMS_SOURCE = Path("app/api/exams.py").read_text(encoding="utf-8")
ANSWER_SYNC_API_SOURCE = Path("app/api/exam_answer_sync.py").read_text(encoding="utf-8")
SESSION_RUNTIME_API_SOURCE = Path("app/api/exam_session_runtime.py").read_text(encoding="utf-8")
OFFLINE_PACKAGE_API_SOURCE = Path("app/api/exam_offline_package.py").read_text(encoding="utf-8")
PAUSE_CONTROL_API_SOURCE = Path("app/api/exam_pause_control.py").read_text(encoding="utf-8")
MAIN_SOURCE = Path("app/main.py").read_text(encoding="utf-8")
ANSWER_SYNC_SCHEMA_SOURCE = Path("app/schemas/answer_sync.py").read_text(encoding="utf-8")


def test_answer_sync_routes_live_outside_large_exams_module() -> None:
    assert "async def auto_save_answers" not in EXAMS_SOURCE
    assert "async def auto_save_batch" not in EXAMS_SOURCE
    assert "async def sync_answer_journal" not in EXAMS_SOURCE
    assert "async def get_session_answers" not in EXAMS_SOURCE

    assert "async def auto_save_answers" in ANSWER_SYNC_API_SOURCE
    assert "async def auto_save_batch" in ANSWER_SYNC_API_SOURCE
    assert "async def sync_answer_journal" in ANSWER_SYNC_API_SOURCE
    assert "async def get_session_answers" in ANSWER_SYNC_API_SOURCE


def test_answer_sync_router_is_registered_in_main() -> None:
    assert "exam_answer_sync" in MAIN_SOURCE
    assert "app.include_router(exam_answer_sync.router)" in MAIN_SOURCE


def test_session_runtime_routes_live_outside_large_exams_module() -> None:
    assert "async def get_session_status" not in EXAMS_SOURCE
    assert "async def get_remaining_time" not in EXAMS_SOURCE
    assert "async def resume_session" not in EXAMS_SOURCE
    assert "class PreciseTimerResponse" not in EXAMS_SOURCE
    assert "class SessionResumeResponse" not in EXAMS_SOURCE

    assert "async def get_session_status" in SESSION_RUNTIME_API_SOURCE
    assert "async def get_remaining_time" in SESSION_RUNTIME_API_SOURCE
    assert "async def resume_session" in SESSION_RUNTIME_API_SOURCE
    assert "class PreciseTimerResponse" in SESSION_RUNTIME_API_SOURCE
    assert "class SessionResumeResponse" in SESSION_RUNTIME_API_SOURCE


def test_session_runtime_router_is_registered_in_main() -> None:
    assert "exam_session_runtime" in MAIN_SOURCE
    assert "app.include_router(exam_session_runtime.router)" in MAIN_SOURCE


def test_offline_package_route_lives_outside_large_exams_module() -> None:
    assert "async def get_offline_exam_package" not in EXAMS_SOURCE
    assert "_sign_offline_package_payload" not in EXAMS_SOURCE
    assert "OFFLINE_PACKAGE_TTL_SECONDS" not in EXAMS_SOURCE

    assert "async def get_offline_exam_package" in OFFLINE_PACKAGE_API_SOURCE
    assert "_sign_offline_package_payload" in OFFLINE_PACKAGE_API_SOURCE
    assert "OFFLINE_PACKAGE_TTL_SECONDS" in OFFLINE_PACKAGE_API_SOURCE
    assert "signature_algorithm" in OFFLINE_PACKAGE_API_SOURCE


def test_offline_package_router_is_registered_in_main() -> None:
    assert "exam_offline_package" in MAIN_SOURCE
    assert "app.include_router(exam_offline_package.router)" in MAIN_SOURCE


def test_pause_control_routes_live_outside_large_exams_module() -> None:
    assert "async def pause_exam_globally" not in EXAMS_SOURCE
    assert "async def resume_exam_globally" not in EXAMS_SOURCE
    assert "async def get_pause_status" not in EXAMS_SOURCE
    assert "class PauseResponse" not in EXAMS_SOURCE

    assert "async def pause_exam_globally" in PAUSE_CONTROL_API_SOURCE
    assert "async def resume_exam_globally" in PAUSE_CONTROL_API_SOURCE
    assert "async def get_pause_status" in PAUSE_CONTROL_API_SOURCE
    assert "class PauseResponse" in PAUSE_CONTROL_API_SOURCE


def test_pause_control_router_is_registered_in_main() -> None:
    assert "exam_pause_control" in MAIN_SOURCE
    assert "app.include_router(exam_pause_control.router)" in MAIN_SOURCE


def test_batch_autosave_schemas_live_in_schema_module() -> None:
    assert "class BatchAnswerItem" not in EXAMS_SOURCE
    assert "class BatchAutoSaveRequest" not in EXAMS_SOURCE
    assert "class BatchAutoSaveResponse" not in EXAMS_SOURCE

    assert "class BatchAnswerItem" in ANSWER_SYNC_SCHEMA_SOURCE
    assert "class BatchAutoSaveRequest" in ANSWER_SYNC_SCHEMA_SOURCE
    assert "class BatchAutoSaveResponse" in ANSWER_SYNC_SCHEMA_SOURCE
