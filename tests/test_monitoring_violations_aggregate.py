from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import monitoring


@pytest.mark.asyncio
async def test_violations_dashboard_auto_uses_aggregate_when_peak_mode(monkeypatch) -> None:
    called = {}

    async def fake_title(db, exam_id, current_user):
        return "Exam A"

    async def fake_aggregate(db, **kwargs):
        called.update(kwargs)
        return {"aggregate_only": True, "summary_only": True}

    monkeypatch.setattr(monitoring.settings, "exam_peak_mode", True)
    monkeypatch.setattr(monitoring.settings, "admin_monitoring_detail_level", "standard")
    monkeypatch.setattr(monitoring, "_resolve_selected_exam_title", fake_title)
    monkeypatch.setattr(monitoring, "_build_violations_aggregate_payload", fake_aggregate)

    result = await monitoring.get_violations_dashboard(
        exam_id=123,
        date_from=datetime.now(timezone.utc),
        date_to=datetime.now(timezone.utc),
        detail_level="auto",
        current_user=SimpleNamespace(id=7, role="teacher"),
        db=SimpleNamespace(),
    )

    assert result["aggregate_only"] is True
    assert called["exam_id"] == 123
    assert called["selected_exam_title"] == "Exam A"


@pytest.mark.asyncio
async def test_violations_dashboard_rejects_invalid_detail_level() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await monitoring.get_violations_dashboard(
            detail_level="full",
            current_user=SimpleNamespace(id=7, role="teacher"),
            db=SimpleNamespace(),
        )

    assert exc_info.value.status_code == 400
