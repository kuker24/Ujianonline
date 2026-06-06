from pathlib import Path


ACTIVITY_SOURCE = Path("app/api/activity.py").read_text(encoding="utf-8")


def _route_body(name: str) -> str:
    marker = f"async def {name}("
    start = ACTIVITY_SOURCE.index(marker)
    next_route = ACTIVITY_SOURCE.find("\n@router.", start + len(marker))
    return ACTIVITY_SOURCE[start:] if next_route == -1 else ACTIVITY_SOURCE[start:next_route]


def test_activity_logs_list_endpoint_uses_read_dependency() -> None:
    body = _route_body("get_activity_logs")

    assert "db: AsyncSession = Depends(get_db_read)" in body
    assert "Depends(get_db)" not in body
    assert "Depends(get_db_write)" not in body


def test_activity_logs_list_endpoint_has_no_prune_or_write_side_effects() -> None:
    body = _route_body("get_activity_logs")

    forbidden_write_markers = (
        "_maybe_auto_prune_activity_logs",
        "_smart_prune_activity_logs",
        "delete(",
        "TRUNCATE TABLE",
        ".delete(",
        ".add(",
        ".commit(",
        "get_db_write",
    )
    for marker in forbidden_write_markers:
        assert marker not in body


def test_activity_log_prune_is_explicit_admin_maintenance_path() -> None:
    reset_body = _route_body("reset_activity_logs")

    assert '@router.delete("/logs/reset")' in ACTIVITY_SOURCE
    assert "current_user: User = Depends(get_current_active_admin)" in reset_body
    assert "db: AsyncSession = Depends(get_db_write)" in reset_body
    assert "TRUNCATE TABLE user_activity_logs" in reset_body
    assert "_smart_prune_activity_logs(" in reset_body


def test_read_only_activity_get_endpoints_do_not_call_auto_prune() -> None:
    for route_name in ("get_activity_logs", "get_activity_stats", "get_event_types", "get_my_activity_logs"):
        body = _route_body(route_name)
        assert "_maybe_auto_prune_activity_logs" not in body
        assert "_smart_prune_activity_logs" not in body
        assert "TRUNCATE TABLE" not in body


def test_activity_logs_per_page_cap_remains_bounded() -> None:
    body = _route_body("get_activity_logs")

    assert "per_page: int = Query(50, ge=1, le=200)" in body
