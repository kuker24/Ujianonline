from pathlib import Path
import re


EXAMS_SOURCE = Path("app/api/exams.py").read_text(encoding="utf-8")
SCHEMA_SOURCE = Path("app/schemas/answer.py").read_text(encoding="utf-8")


def _extract_async_function(source: str, function_name: str) -> str:
    pattern = re.compile(
        rf"async def {re.escape(function_name)}\([\s\S]*?(?=\n@router|\nasync def |\nclass |\Z)",
        re.MULTILINE,
    )
    match = pattern.search(source)
    assert match is not None, f"Function {function_name} not found"
    return match.group(0)


def test_answer_journal_schema_exists() -> None:
    assert "class AnswerJournalEvent" in SCHEMA_SOURCE
    assert "class AnswerJournalSyncRequest" in SCHEMA_SOURCE
    assert "class AnswerJournalSyncResponse" in SCHEMA_SOURCE


def test_sync_answer_journal_uses_hot_path_auth_dependency() -> None:
    fn = _extract_async_function(EXAMS_SOURCE, "sync_answer_journal")
    assert "current_user: AuthenticatedUser = Depends(get_current_user_hot_path)" in fn
    assert "get_db" in fn


def test_sync_answer_journal_has_idempotency_ack_logic() -> None:
    fn = _extract_async_function(EXAMS_SOURCE, "sync_answer_journal")
    assert "already_acked" in fn
    assert "duplicate_in_payload" in fn
    assert "await redis.sadd" in fn
    assert "AnswerJournalAck" in fn


def test_offline_package_endpoint_exists_and_signed() -> None:
    fn = _extract_async_function(EXAMS_SOURCE, "get_offline_exam_package")
    assert "current_user: AuthenticatedUser = Depends(get_current_user_hot_path)" in fn
    assert "signature_algorithm" in fn
    assert "_sign_offline_package_payload" in fn
    assert "questions_payload" in fn
