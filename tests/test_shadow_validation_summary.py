import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from scripts import shadow_validation_summary as summary


class _FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.ttls = {}
        self.sets = {}

    async def scan_iter(self, match=None):
        import fnmatch
        for key in sorted(self.hashes):
            if match is None or fnmatch.fnmatch(key, match):
                yield key
        for key in sorted(self.sets):
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def ttl(self, key):
        return self.ttls.get(key, -2)

    async def smembers(self, key):
        return set(self.sets.get(key, set()))


def _shadow_payload(question_id=1, *, seconds_ago=30):
    updated_at = (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()
    return json.dumps(
        {"question_id": question_id, "payload_hash": "a" * 64, "updated_at": updated_at},
        separators=(",", ":"),
    )


def _add_shadow_session(redis, session_id, *, ttl=3600, refreshed=True, raw_secret=False):
    answer_key = f"runtime:answer_shadow:session:{session_id}:answers"
    meta_key = f"runtime:answer_shadow:session:{session_id}:meta"
    redis.hashes[answer_key] = {"1": _shadow_payload(1)}
    redis.ttls[answer_key] = ttl
    redis.hashes[meta_key] = {
        "session_id": str(session_id),
        "exam_id": "55",
        "answer_count": "1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "refreshed_after_final_submit": "true" if refreshed else "false",
        "refreshed_from_db": "true" if refreshed else "false",
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
    if raw_secret:
        redis.hashes[meta_key]["debug_raw_token"] = "SECRET_TOKEN_SHOULD_NOT_APPEAR"
    redis.ttls[meta_key] = ttl
    return answer_key, meta_key


@pytest.mark.asyncio
async def test_redis_shadow_summary_contains_required_fields_and_redacts_ids() -> None:
    redis = _FakeRedis()
    _add_shadow_session(redis, 12345, ttl=3600, refreshed=True)

    result = await summary._redis_shadow_summary(redis, redact=True)

    required = {
        "runtime_shadow_keys_count",
        "runtime_answer_buffer_keys_count",
        "answer_queue_keys_count",
        "legacy_answer_queue_keys_count",
        "oldest_shadow_key_age_seconds",
        "newest_shadow_key_age_seconds",
        "ttl_min_seconds",
        "ttl_max_seconds",
        "shadow_keys_without_ttl",
        "sessions_with_shadow",
        "post_final_refresh_meta_count",
        "post_final_refresh_missing_count",
        "log_marker_expected_note",
    }
    assert required <= set(result)
    assert result["sessions_with_shadow"] == 1
    assert result["shadow_session_ids"] == ["***45"]
    assert result["post_final_refresh_meta_count"] == 1
    assert result["post_final_refresh_missing_count"] == 0
    assert result["ttl_min_seconds"] == 3600
    assert result["ttl_max_seconds"] == 3600


@pytest.mark.asyncio
async def test_redis_shadow_summary_no_keys_handles_ttl_and_age_as_none() -> None:
    result = await summary._redis_shadow_summary(_FakeRedis(), redact=True)

    assert result["runtime_shadow_keys_count"] == 0
    assert result["sessions_with_shadow"] == 0
    assert result["ttl_min_seconds"] is None
    assert result["ttl_max_seconds"] is None
    assert result["oldest_shadow_key_age_seconds"] is None
    assert result["newest_shadow_key_age_seconds"] is None
    assert result["shadow_keys_without_ttl"] == 0


@pytest.mark.asyncio
async def test_redis_shadow_summary_counts_keys_without_ttl_and_production_keys() -> None:
    redis = _FakeRedis()
    _add_shadow_session(redis, 123, ttl=-1, refreshed=False)
    redis.hashes["runtime:session:123:answers"] = {"1": "raw-buffer"}
    redis.hashes["runtime:answer_queue:pending"] = {"x": "y"}
    redis.hashes["answer_queue:legacy"] = {"x": "y"}

    result = await summary._redis_shadow_summary(redis, redact=True)

    assert result["shadow_keys_without_ttl"] == 2
    assert result["runtime_answer_buffer_keys_count"] == 1
    assert result["answer_queue_keys_count"] == 1
    assert result["legacy_answer_queue_keys_count"] == 1
    assert result["post_final_refresh_meta_count"] == 0
    assert result["post_final_refresh_missing_count"] == 1


@pytest.mark.asyncio
async def test_redis_shadow_summary_filters_by_session_id() -> None:
    redis = _FakeRedis()
    _add_shadow_session(redis, 101, ttl=100, refreshed=True)
    _add_shadow_session(redis, 202, ttl=200, refreshed=True)

    result = await summary._redis_shadow_summary(redis, allowed_session_ids={202}, redact=False)

    assert result["runtime_shadow_keys_count"] == 4  # global count remains visible
    assert result["sessions_with_shadow"] == 1
    assert result["shadow_session_ids"] == [202]
    assert result["ttl_min_seconds"] == 200
    assert result["ttl_max_seconds"] == 200


def test_fail_on_mismatch_conditions() -> None:
    base = {
        "payload_hash_mismatch": 0,
        "redis_errors": 0,
        "shadow_keys_without_ttl": 0,
        "answer_queue_keys_count": 0,
        "legacy_answer_queue_keys_count": 0,
        "runtime_answer_buffer_keys_count": 0,
    }
    assert summary.should_fail(base) is False
    for key in base:
        mutated = dict(base)
        mutated[key] = 1
        assert summary.should_fail(mutated) is True


def test_redaction_helpers_default_to_masked_ids() -> None:
    assert summary._format_session_ids([12345], redact=True) == ["***45"]
    assert summary._format_session_ids([12345], redact=False) == [12345]


def test_source_is_read_only_and_does_not_store_raw_sensitive_values() -> None:
    source = Path("scripts/shadow_validation_summary.py").read_text(encoding="utf-8")

    forbidden_write_markers = [
        ".set(",
        ".hset(",
        ".delete(",
        ".expire(",
        ".rpush(",
        ".sadd(",
        "update ",
        "insert ",
        "delete from",
    ]
    for marker in forbidden_write_markers:
        assert marker not in source.lower()

    assert "answer_text" not in source or "raw answer content" in source
    assert "session_token" not in source
    assert "access_token" not in source
    assert "full_name" not in source
    assert "email" not in source


def test_parser_supports_required_options() -> None:
    parser = summary.build_parser()
    args = parser.parse_args([
        "--session-id",
        "123",
        "--exam-id",
        "55",
        "--fail-on-mismatch",
        "--no-redact",
    ])

    assert args.session_id == 123
    assert args.exam_id == 55
    assert args.fail_on_mismatch is True
    assert args.redact is False
