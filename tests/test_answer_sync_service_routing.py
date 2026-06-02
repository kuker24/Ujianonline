from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api import exams
from app.schemas.answer import (
    AnswerJournalSyncRequest,
    AnswerJournalSyncResponse,
    AutoSaveRequest,
    AutoSaveResponse,
)


class _FakeAnswerSyncService:
    def __init__(self):
        self.called = None

    async def accept_legacy_autosave(self, save_data):
        self.called = ("legacy_autosave", save_data.session_id)
        return AutoSaveResponse(
            status="success",
            saved_count=len(save_data.answers),
            timestamp=datetime.now(timezone.utc),
        )

    async def accept_batch(self, batch_data):
        self.called = ("batch", batch_data.session_id)
        return {
            "status": "saved_to_db",
            "queued_count": len(batch_data.answers),
            "queue_id": "test",
            "timestamp": datetime.now(timezone.utc),
        }

    async def accept_journal_events(self, sync_data):
        self.called = ("journal", sync_data.session_id)
        return AnswerJournalSyncResponse(
            status="ok",
            accepted=0,
            duplicates=0,
            invalid=0,
            applied_question_count=0,
            acks=[],
            server_time=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_legacy_autosave_endpoint_routes_to_answer_sync_service(monkeypatch) -> None:
    fake_service = _FakeAnswerSyncService()
    monkeypatch.setattr(exams, "get_answer_sync_service", lambda db, user: fake_service)

    response = await exams.auto_save_answers(
        AutoSaveRequest(
            session_id=123,
            answers={1: "A"},
            timestamp=datetime.now(timezone.utc),
        ),
        request=None,
        current_user=SimpleNamespace(id=7),
        db=None,
    )

    assert response.status == "success"
    assert fake_service.called == ("legacy_autosave", 123)


@pytest.mark.asyncio
async def test_batch_autosave_endpoint_routes_to_answer_sync_service(monkeypatch) -> None:
    fake_service = _FakeAnswerSyncService()
    monkeypatch.setattr(exams, "get_answer_sync_service", lambda db, user: fake_service)

    response = await exams.auto_save_batch(
        exams.BatchAutoSaveRequest(
            session_id=123,
            answers=[exams.BatchAnswerItem(question_id=1, selected_option_id=2)],
        ),
        request=None,
        current_user=SimpleNamespace(id=7),
        db=None,
    )

    assert response["status"] == "saved_to_db"
    assert fake_service.called == ("batch", 123)


@pytest.mark.asyncio
async def test_answer_journal_endpoint_routes_to_answer_sync_service(monkeypatch) -> None:
    fake_service = _FakeAnswerSyncService()
    monkeypatch.setattr(exams, "get_answer_sync_service", lambda db, user: fake_service)

    response = await exams.sync_answer_journal(
        AnswerJournalSyncRequest(session_id=123, events=[]),
        current_user=SimpleNamespace(id=7),
        db=None,
    )

    assert response.status == "ok"
    assert fake_service.called == ("journal", 123)
