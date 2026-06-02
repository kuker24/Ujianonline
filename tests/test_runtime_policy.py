import pytest

from app.api import runtime as runtime_api
from app.config import settings
from app.core import runtime_policy


def test_build_mobile_runtime_policy_normal_shape() -> None:
    policy = runtime_policy.build_mobile_runtime_policy(
        "normal",
        internal_policy={"resource_mode": "normal", "degrade_mode": False},
    )

    assert policy["mode"] == "normal"
    assert policy["answer_sync_interval_seconds"] == 15
    assert policy["answer_sync_batch_size"] == 30
    assert policy["command_poll_seconds"] == 25
    assert policy["violation_flush_seconds"] == 30
    assert policy["retry_after_seconds"] == 8
    assert policy["cheating_detection_enabled"] is True
    assert policy["cheating_detail_level"] == "aggregate"
    assert policy["final_submit_priority"] is True


def test_resolve_mobile_runtime_mode_busy_and_degraded(monkeypatch) -> None:
    monkeypatch.setattr(settings, "exam_peak_mode", False)

    assert runtime_policy.resolve_mobile_runtime_mode({"resource_mode": "normal"}) == "normal"
    assert runtime_policy.resolve_mobile_runtime_mode({"resource_mode": "high"}) == "busy"
    assert runtime_policy.resolve_mobile_runtime_mode({"degrade_mode": True}) == "busy"
    assert runtime_policy.resolve_mobile_runtime_mode({"resource_mode": "extreme"}) == "degraded"


def test_resolve_mobile_runtime_mode_exam_peak_flag(monkeypatch) -> None:
    monkeypatch.setattr(settings, "exam_peak_mode", True)

    assert runtime_policy.resolve_mobile_runtime_mode({"resource_mode": "normal"}) == "exam_peak"


@pytest.mark.asyncio
async def test_runtime_policy_endpoint_returns_no_store_json(monkeypatch) -> None:
    async def fake_policy(force_refresh=False):
        assert force_refresh is False
        return runtime_policy.build_mobile_runtime_policy(
            "busy",
            internal_policy={"resource_mode": "high", "degrade_mode": True},
        )

    monkeypatch.setattr(runtime_api, "get_mobile_runtime_policy", fake_policy)

    response = await runtime_api.get_runtime_policy_endpoint()

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["X-Runtime-Policy-Version"] == "20260602-mobile-runtime-v1"
    assert b'"mode":"busy"' in response.body
    assert b'"answer_sync_interval_seconds":25' in response.body
