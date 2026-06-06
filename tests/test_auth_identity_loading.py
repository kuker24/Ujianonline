from pathlib import Path


SECURITY_SOURCE = Path("app/core/security.py").read_text(encoding="utf-8")
AUTH_SOURCE = Path("app/api/auth.py").read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    marker = f"async def {name}("
    start = source.index(marker)
    next_def = source.find("\nasync def ", start + len(marker))
    if next_def == -1:
        next_def = source.find("\ndef ", start + len(marker))
    return source[start:] if next_def == -1 else source[start:next_def]


def test_auth_identity_load_options_disable_heavy_user_relationships() -> None:
    options_block = SECURITY_SOURCE.split("USER_IDENTITY_LOAD_OPTIONS = (", 1)[1].split(")\n\nUSER_RESPONSE_LOAD_OPTIONS", 1)[0]

    assert "load_only(" in options_block
    assert "User.id" in options_block
    assert "User.username" in options_block
    assert "User.role" in options_block
    assert "User.is_active" in options_block
    assert "noload(User.created_exams)" in options_block
    assert "noload(User.exam_sessions)" in options_block
    assert "selectinload" not in options_block


def test_resolve_authenticated_user_uses_lightweight_identity_options() -> None:
    body = _function_body(SECURITY_SOURCE, "_resolve_authenticated_user")

    assert "decode_token(token, verify_exp=True)" in body
    assert ".options(*USER_IDENTITY_LOAD_OPTIONS)" in body
    assert "select(User)" in body
    assert "User.id == token_data.user_id" in body
    assert "selectinload" not in body
    assert ".created_exams" not in body
    assert ".exam_sessions" not in body


def test_refresh_user_lookup_uses_lightweight_identity_options() -> None:
    body = _function_body(SECURITY_SOURCE, "get_current_user_for_refresh")

    assert "decode_token(token, verify_exp=False)" in body
    assert ".options(*USER_IDENTITY_LOAD_OPTIONS)" in body
    assert "User.id == token_data.user_id" in body
    assert "selectinload" not in body
    assert ".created_exams" not in body
    assert ".exam_sessions" not in body


def test_auth_response_lookup_uses_response_load_options() -> None:
    body = _function_body(AUTH_SOURCE, "_load_user_response")

    assert ".options(*USER_RESPONSE_LOAD_OPTIONS)" in body
    assert "select(User)" in body
    assert "User.id == user_id" in body
    assert "selectinload" not in body


def test_auth_identity_lookup_does_not_reference_answer_or_log_relationships() -> None:
    for name in ("_resolve_authenticated_user", "get_current_user_for_refresh"):
        body = _function_body(SECURITY_SOURCE, name)
        assert "Answer" not in body
        assert "answers" not in body.lower()
        assert "ExamLog" not in body
        assert "exam_logs" not in body.lower()
