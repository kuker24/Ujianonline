import logging
from types import SimpleNamespace

import pytest

from app.services import final_submit_service


async def _noop_invalidate(_exam_id):
    return None


async def _no_session_data(_session_id):
    return None


async def _noop_publish(_exam_id, _payload):
    return None


def _service() -> final_submit_service.FinalSubmitService:
    return final_submit_service.FinalSubmitService(
        db=SimpleNamespace(),
        current_user=SimpleNamespace(
            id=7,
            username="raw-username-must-not-appear",
            full_name="Raw Full Name Must Not Appear",
            email="student@example.invalid",
        ),
    )


def _session() -> SimpleNamespace:
    return SimpleNamespace(id=123, exam_id=55, violation_count=0)


def _patch_non_shadow_best_effort(monkeypatch) -> None:
    monkeypatch.setattr(final_submit_service, "invalidate_exam_results_cache", _noop_invalidate)
    monkeypatch.setattr(final_submit_service, "get_session_data", _no_session_data)
    monkeypatch.setattr(final_submit_service, "_publish_exam_monitor_event", _noop_publish)


@pytest.mark.asyncio
async def test_post_final_shadow_refresh_success_marker_is_warning_visible_and_sanitized(
    monkeypatch,
    caplog,
) -> None:
    async def successful_refresh(_db, _session_id, exam_id=None):
        return {
            "status": "ok",
            "answer_count": 3,
            "refreshed_after_final_submit": True,
        }

    _patch_non_shadow_best_effort(monkeypatch)
    monkeypatch.setattr(final_submit_service, "refresh_runtime_answer_shadow_from_db", successful_refresh)
    caplog.set_level(logging.WARNING, logger=final_submit_service.__name__)

    await _service()._after_submit_best_effort(_session(), percentage=90.0)

    assert "SHADOW_POST_FINAL_REFRESH_OK" in caplog.text
    assert "answer_count=3" in caplog.text
    assert "refreshed_after_final_submit=True" in caplog.text
    assert "raw-username-must-not-appear" not in caplog.text
    assert "Raw Full Name Must Not Appear" not in caplog.text
    assert "student@example.invalid" not in caplog.text
    assert "raw secret answer" not in caplog.text
    assert "session_token" not in caplog.text
    assert "access_token" not in caplog.text


@pytest.mark.asyncio
async def test_post_final_shadow_refresh_skipped_is_not_noisy_at_warning(
    monkeypatch,
    caplog,
) -> None:
    async def skipped_refresh(_db, _session_id, exam_id=None):
        return {"status": "skipped", "reason": "disabled", "answer_count": 0}

    _patch_non_shadow_best_effort(monkeypatch)
    monkeypatch.setattr(final_submit_service, "refresh_runtime_answer_shadow_from_db", skipped_refresh)
    caplog.set_level(logging.WARNING, logger=final_submit_service.__name__)

    await _service()._after_submit_best_effort(_session(), percentage=90.0)

    assert "SHADOW_POST_FINAL_REFRESH_OK" not in caplog.text
    assert "SHADOW_POST_FINAL_REFRESH_SKIPPED" not in caplog.text
    assert "SHADOW_POST_FINAL_REFRESH_FAILED" not in caplog.text


@pytest.mark.asyncio
async def test_post_final_shadow_refresh_failed_marker_is_warning_sanitized_and_best_effort(
    monkeypatch,
    caplog,
) -> None:
    async def failed_refresh(_db, _session_id, exam_id=None):
        return {
            "status": "failed",
            "reason": "RuntimeError",
            "answer_count": 0,
            "raw_message": "raw secret answer token should not be logged",
        }

    _patch_non_shadow_best_effort(monkeypatch)
    monkeypatch.setattr(final_submit_service, "refresh_runtime_answer_shadow_from_db", failed_refresh)
    caplog.set_level(logging.WARNING, logger=final_submit_service.__name__)

    await _service()._after_submit_best_effort(_session(), percentage=90.0)

    assert "SHADOW_POST_FINAL_REFRESH_FAILED" in caplog.text
    assert "reason=RuntimeError" in caplog.text
    assert "raw secret answer" not in caplog.text
    assert "token should not be logged" not in caplog.text
    assert "raw-username-must-not-appear" not in caplog.text


@pytest.mark.asyncio
async def test_post_final_shadow_refresh_exception_marker_uses_class_only(
    monkeypatch,
    caplog,
) -> None:
    async def raising_refresh(_db, _session_id, exam_id=None):
        raise RuntimeError("redis down with raw token and raw answer text")

    _patch_non_shadow_best_effort(monkeypatch)
    monkeypatch.setattr(final_submit_service, "refresh_runtime_answer_shadow_from_db", raising_refresh)
    caplog.set_level(logging.WARNING, logger=final_submit_service.__name__)

    await _service()._after_submit_best_effort(_session(), percentage=90.0)

    assert "SHADOW_POST_FINAL_REFRESH_FAILED" in caplog.text
    assert "error=RuntimeError" in caplog.text
    assert "redis down with raw token" not in caplog.text
    assert "raw answer text" not in caplog.text
