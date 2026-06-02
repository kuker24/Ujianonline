from pathlib import Path


EXAMS_SOURCE = Path("app/api/exams.py").read_text(encoding="utf-8")
ANSWER_SYNC_API_SOURCE = Path("app/api/exam_answer_sync.py").read_text(encoding="utf-8")
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


def test_batch_autosave_schemas_live_in_schema_module() -> None:
    assert "class BatchAnswerItem" not in EXAMS_SOURCE
    assert "class BatchAutoSaveRequest" not in EXAMS_SOURCE
    assert "class BatchAutoSaveResponse" not in EXAMS_SOURCE

    assert "class BatchAnswerItem" in ANSWER_SYNC_SCHEMA_SOURCE
    assert "class BatchAutoSaveRequest" in ANSWER_SYNC_SCHEMA_SOURCE
    assert "class BatchAutoSaveResponse" in ANSWER_SYNC_SCHEMA_SOURCE
