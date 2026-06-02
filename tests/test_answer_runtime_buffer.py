from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import answer_runtime_buffer as buffer
from app.services import answer_sync_service


def test_runtime_answer_buffer_keys_match_phase6_spec() -> None:
    assert buffer.PENDING_QUEUE_KEY == "runtime:answer_queue:pending"
    assert buffer.PROCESSING_QUEUE_KEY == "runtime:answer_queue:processing"
    assert buffer.session_answers_key(123) == "runtime:session:123:answers"
    assert buffer.session_dirty_questions_key(123) == "runtime:session:123:dirty_questions"
    assert buffer.session_answered_count_key(123) == "runtime:session:123:answered_count"


def test_runtime_answer_buffer_disabled_by_default() -> None:
    assert buffer.is_runtime_answer_buffer_enabled() is False


class _FakeRuntimeBufferService:
    def __init__(self, db, current_user):
        self.db = db
        self.current_user = current_user

    async def accept_batch(self, batch_data):
        return {
            "status": "buffered",
            "queued_count": len(batch_data.answers),
            "queue_id": "redis-test",
            "timestamp": datetime.now(timezone.utc),
        }

    async def accept_journal_events(self, sync_data, accepted_events):
        return len(accepted_events)


@pytest.mark.asyncio
async def test_answer_sync_service_routes_batch_to_runtime_buffer_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(answer_sync_service, "is_runtime_answer_buffer_enabled", lambda: True)
    monkeypatch.setattr(answer_sync_service, "AnswerRuntimeBufferService", _FakeRuntimeBufferService)

    service = answer_sync_service.AnswerSyncService(db=None, current_user=SimpleNamespace(id=7))
    batch_data = SimpleNamespace(
        session_id=123,
        answers=[SimpleNamespace(question_id=1)],
    )

    result = await service.accept_batch(batch_data)

    assert result["status"] == "buffered"
    assert result["queued_count"] == 1
