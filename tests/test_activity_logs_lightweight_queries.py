from pathlib import Path


ACTIVITY_SOURCE = Path("app/api/activity.py").read_text(encoding="utf-8")


def _route_body(name: str) -> str:
    marker = f"async def {name}("
    start = ACTIVITY_SOURCE.index(marker)
    next_route = ACTIVITY_SOURCE.find("\n@router.", start + len(marker))
    return ACTIVITY_SOURCE[start:] if next_route == -1 else ACTIVITY_SOURCE[start:next_route]


def test_activity_logs_list_uses_projection_and_outer_join() -> None:
    body = _route_body("get_activity_logs")

    assert "select(" in body
    assert "UserActivityLog.id" in body
    assert "UserActivityLog.user_id" in body
    assert 'User.full_name.label("user_name")' in body
    assert 'User.role.label("user_role")' in body
    assert ".outerjoin(User, UserActivityLog.user_id == User.id)" in body
    assert "result.mappings().all()" in body


def test_activity_logs_list_does_not_instantiate_orm_rows_or_eager_load_user() -> None:
    body = _route_body("get_activity_logs")

    assert "selectinload" not in ACTIVITY_SOURCE
    assert "select(UserActivityLog)" not in body
    assert "result.scalars().all()" not in body
    assert ".options(" not in body
    assert ".user." not in body
    assert "log.user" not in body
    assert "User.created_exams" not in body
    assert "User.exam_sessions" not in body


def test_activity_logs_count_query_is_simple_activity_log_count() -> None:
    body = _route_body("get_activity_logs")

    assert "count_query = select(func.count(UserActivityLog.id))" in body
    assert "select_from(query.subquery())" not in body
    assert "count_query = count_query.where(*filters)" in body


def test_activity_logs_response_shape_remains_frontend_compatible() -> None:
    body = _route_body("get_activity_logs")

    for key in (
        '"logs"',
        '"id"',
        '"user_id"',
        '"user_name"',
        '"user_role"',
        '"event_type"',
        '"event_data"',
        '"ip_address"',
        '"created_at"',
        '"total"',
        '"page"',
        '"per_page"',
        '"total_pages"',
    ):
        assert key in body

    assert 'log["user_name"] or "Unknown"' in body
    assert 'log["event_data"] or {}' in body


def test_my_activity_logs_uses_projection_not_orm_rows() -> None:
    body = _route_body("get_my_activity_logs")

    assert "db: AsyncSession = Depends(get_db_read)" in body
    assert "select(" in body
    assert "UserActivityLog.id" in body
    assert "result.mappings().all()" in body
    assert "select(UserActivityLog)" not in body
    assert "result.scalars().all()" not in body
