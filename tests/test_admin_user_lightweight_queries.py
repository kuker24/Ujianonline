from pathlib import Path


USERS_SOURCE = Path("app/api/users.py").read_text(encoding="utf-8")


def _route_body(source: str, name: str) -> str:
    marker = f"async def {name}("
    start = source.index(marker)
    next_route = source.find("\n@router.", start + len(marker))
    return source[start:] if next_route == -1 else source[start:next_route]


def test_advanced_user_search_uses_column_projection_not_user_orm_rows() -> None:
    body = _route_body(USERS_SOURCE, "advanced_user_search")

    assert "select(*USER_RESPONSE_COLUMNS)" in body
    assert "result.mappings().all()" in body
    assert "_user_response_from_mapping" in body
    assert "select(User)" not in body
    assert "result.scalars().all()" not in body
    assert "UserResponse.model_validate(u)" not in body
    assert "selectinload" not in body


def test_user_detail_uses_lightweight_projection() -> None:
    body = _route_body(USERS_SOURCE, "get_user")

    assert "select(*USER_RESPONSE_COLUMNS).where(User.id == user_id)" in body
    assert "result.mappings().one_or_none()" in body
    assert "_user_response_from_mapping(user)" in body
    assert "select(User)" not in body
    assert "scalar_one_or_none" not in body
    assert "selectinload" not in body


def test_admin_user_mutation_loads_user_without_relationship_cascade() -> None:
    for route_name in ("update_user", "delete_user"):
        body = _route_body(USERS_SOURCE, route_name)
        assert ".options(*USER_RESPONSE_LOAD_OPTIONS)" in body
        assert "selectinload" not in body
        assert ".created_exams" not in body
        assert ".exam_sessions" not in body


def test_user_response_projection_contains_only_response_columns() -> None:
    columns_block = USERS_SOURCE.split("USER_RESPONSE_COLUMNS = (", 1)[1].split(")\n\n\ndef _user_response_from_mapping", 1)[0]

    for field in (
        "User.id",
        "User.username",
        "User.full_name",
        "User.role",
        "User.student_class",
        "User.is_active",
        "User.created_at",
        "User.last_login",
        "User.profile_picture",
        "User.job_title",
    ):
        assert field in columns_block

    assert "password_hash" not in columns_block
    assert "created_exams" not in columns_block
    assert "exam_sessions" not in columns_block
    assert "answers" not in columns_block
    assert "exam_logs" not in columns_block


def test_admin_user_routes_do_not_reference_answer_or_log_relationships() -> None:
    for route_name in ("advanced_user_search", "get_user"):
        body = _route_body(USERS_SOURCE, route_name)
        assert "Answer" not in body
        assert "answers" not in body.lower()
        assert "ExamLog" not in body
        assert "exam_logs" not in body.lower()
