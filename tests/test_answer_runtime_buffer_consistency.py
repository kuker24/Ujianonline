from pathlib import Path


SCRIPT_SOURCE = Path("scripts/runtime_buffer_consistency_check.py").read_text(encoding="utf-8")


def test_runtime_buffer_consistency_checker_is_read_only_and_hash_only() -> None:
    assert "payload_hash" in SCRIPT_SOURCE
    assert "answer_payload_hash" in SCRIPT_SOURCE
    assert "raw answer content" in SCRIPT_SOURCE
    assert "print(json.dumps(summary" in SCRIPT_SOURCE
    assert ".answer_text" in SCRIPT_SOURCE  # input to hash only
    assert "await redis.hgetall" in SCRIPT_SOURCE
    assert "await redis.hset" not in SCRIPT_SOURCE
    assert "await redis.set" not in SCRIPT_SOURCE
    assert "await redis.delete" not in SCRIPT_SOURCE
    assert "await redis.expire" not in SCRIPT_SOURCE


def test_runtime_buffer_consistency_checker_outputs_required_summary_fields() -> None:
    required_fields = [
        "checked_sessions",
        "checked_answers",
        "missing_in_redis",
        "extra_in_redis",
        "payload_hash_mismatch",
        "stale_runtime_sessions",
        "redis_errors",
    ]
    for field in required_fields:
        assert f'"{field}"' in SCRIPT_SOURCE


def test_runtime_buffer_consistency_checker_does_not_query_user_pii() -> None:
    assert "username" not in SCRIPT_SOURCE
    assert "full_name" not in SCRIPT_SOURCE
    assert "email" not in SCRIPT_SOURCE
    assert "phone" not in SCRIPT_SOURCE
    assert "join(User" not in SCRIPT_SOURCE
