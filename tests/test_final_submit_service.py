from types import SimpleNamespace

import pytest

from app.api import exams
from app.schemas.answer import ExamSubmitRequest, ExamSubmitResponse
from app.services import final_submit_service


class _FakeFinalSubmitService:
    def __init__(self):
        self.called = None

    async def submit_exam(self, submit_data, request):
        self.called = (submit_data.session_id, request)
        return ExamSubmitResponse(
            session_id=submit_data.session_id,
            status="submitted",
            message="ok",
        )


@pytest.mark.asyncio
async def test_submit_exam_endpoint_routes_to_final_submit_service(monkeypatch) -> None:
    fake_service = _FakeFinalSubmitService()
    monkeypatch.setattr(exams, "get_final_submit_service", lambda db, user: fake_service)

    response = await exams.submit_exam(
        ExamSubmitRequest(session_id=123),
        request=None,
        current_user=SimpleNamespace(id=7, username="student"),
        db=None,
    )

    assert response.status == "submitted"
    assert fake_service.called == (123, None)


@pytest.mark.asyncio
async def test_final_submit_preflushes_runtime_answer_buffer_when_enabled(monkeypatch) -> None:
    flushed = {}

    async def fake_flush(db, session_id):
        flushed["db"] = db
        flushed["session_id"] = session_id
        return 2

    monkeypatch.setattr(final_submit_service, "_answer_write_mode", lambda: "direct")
    monkeypatch.setattr(final_submit_service, "is_runtime_answer_buffer_enabled", lambda: True)
    monkeypatch.setattr(final_submit_service, "flush_runtime_answer_buffer_for_session", fake_flush)

    fake_db = SimpleNamespace()
    service = final_submit_service.FinalSubmitService(
        db=fake_db,
        current_user=SimpleNamespace(id=7, username="student"),
    )

    await service._flush_answer_buffers_before_submit(123)

    assert flushed == {"db": fake_db, "session_id": 123}
