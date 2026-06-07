from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import final_submit_service


@pytest.mark.asyncio
async def test_after_submit_refreshes_shadow_best_effort_after_commit(monkeypatch) -> None:
    calls = {}

    async def fake_refresh(db, session_id, exam_id=None):
        calls["refresh"] = {"db": db, "session_id": session_id, "exam_id": exam_id}
        return {"status": "ok", "answer_count": 2}

    async def noop_invalidate(_exam_id):
        calls["invalidate"] = True

    async def no_session_data(_session_id):
        return None

    async def noop_publish(_exam_id, _payload):
        calls["publish"] = True

    monkeypatch.setattr(final_submit_service, "refresh_runtime_answer_shadow_from_db", fake_refresh)
    monkeypatch.setattr(final_submit_service, "invalidate_exam_results_cache", noop_invalidate)
    monkeypatch.setattr(final_submit_service, "get_session_data", no_session_data)
    monkeypatch.setattr(final_submit_service, "_publish_exam_monitor_event", noop_publish)

    fake_db = SimpleNamespace(name="db-after-commit")
    service = final_submit_service.FinalSubmitService(
        db=fake_db,
        current_user=SimpleNamespace(id=7, username="student"),
    )
    await service._after_submit_best_effort(
        SimpleNamespace(id=123, exam_id=55, violation_count=0),
        percentage=90.0,
    )

    assert calls["refresh"] == {"db": fake_db, "session_id": 123, "exam_id": 55}
    assert calls["invalidate"] is True
    assert calls["publish"] is True


@pytest.mark.asyncio
async def test_after_submit_shadow_refresh_failure_cannot_fail_final_submit(monkeypatch, caplog) -> None:
    async def failing_refresh(_db, _session_id, exam_id=None):
        raise RuntimeError("redis unavailable after commit")

    async def noop_invalidate(_exam_id):
        return None

    async def no_session_data(_session_id):
        return None

    async def noop_publish(_exam_id, _payload):
        return None

    monkeypatch.setattr(final_submit_service, "refresh_runtime_answer_shadow_from_db", failing_refresh)
    monkeypatch.setattr(final_submit_service, "invalidate_exam_results_cache", noop_invalidate)
    monkeypatch.setattr(final_submit_service, "get_session_data", no_session_data)
    monkeypatch.setattr(final_submit_service, "_publish_exam_monitor_event", noop_publish)

    service = final_submit_service.FinalSubmitService(
        db=SimpleNamespace(),
        current_user=SimpleNamespace(id=7, username="student"),
    )

    await service._after_submit_best_effort(
        SimpleNamespace(id=123, exam_id=55, violation_count=0),
        percentage=90.0,
    )

    assert "SHADOW_POST_FINAL_REFRESH_FAILED" in caplog.text
    assert "redis unavailable after commit" not in caplog.text


def test_final_submit_service_does_not_read_runtime_shadow_keys() -> None:
    source = Path("app/services/final_submit_service.py").read_text(encoding="utf-8")

    assert "shadow_session_answers_key" not in source
    assert "runtime:answer_shadow" not in source
    assert ".hgetall(" not in source
    assert ".hget(" not in source
    assert ".smembers(" not in source


def test_final_submit_shadow_refresh_is_post_commit_best_effort_source_only() -> None:
    source = Path("app/services/final_submit_service.py").read_text(encoding="utf-8")

    assert "await self.db.commit()" in source
    assert "await self._after_submit_best_effort(session, finalize_result.percentage)" in source
    assert "refresh_runtime_answer_shadow_from_db" in source
    assert "except Exception as shadow_refresh_exc" in source
