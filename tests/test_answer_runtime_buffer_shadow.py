import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.services import answer_runtime_buffer as buffer


def test_runtime_answer_buffer_shadow_disabled_by_default() -> None:
    assert buffer.is_runtime_answer_buffer_shadow_enabled() is False
    assert buffer.is_runtime_answer_buffer_shadow_enabled_for_session(123, user_id=7, exam_id=55) is False
    assert buffer._answer_shadow_percentage() == 0
    assert buffer.runtime_answer_shadow_ttl_seconds() == 14400


def test_runtime_answer_buffer_shadow_enabled_with_zero_percent_and_empty_allowlist_does_not_shadow(monkeypatch) -> None:
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 0)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_session_ids", "")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_exam_ids", "")

    assert buffer.runtime_answer_shadow_session_allowlist() == set()
    assert buffer.runtime_answer_shadow_exam_allowlist() == set()
    assert buffer.is_runtime_answer_buffer_shadow_enabled_for_session(123, user_id=7, exam_id=55) is False


def test_runtime_answer_buffer_shadow_session_allowlist_overrides_zero_percentage(monkeypatch) -> None:
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 0)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_session_ids", "123, 456, bad, -1")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_exam_ids", "")

    assert buffer.runtime_answer_shadow_session_allowlist() == {123, 456}
    assert buffer.is_runtime_answer_buffer_shadow_enabled_for_session(123, user_id=7, exam_id=55) is True
    assert buffer.is_runtime_answer_buffer_shadow_enabled_for_session(999, user_id=7, exam_id=55) is False


def test_runtime_answer_buffer_shadow_exam_allowlist_overrides_zero_percentage(monkeypatch) -> None:
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 0)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_session_ids", "")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_exam_ids", "55, 77")

    assert buffer.runtime_answer_shadow_exam_allowlist() == {55, 77}
    assert buffer.is_runtime_answer_buffer_shadow_enabled_for_session(123, user_id=7, exam_id=55) is True
    assert buffer.is_runtime_answer_buffer_shadow_enabled_for_session(123, user_id=7, exam_id=88) is False


def test_runtime_answer_buffer_shadow_percentage_is_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 10)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_session_ids", "")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_exam_ids", "")

    decisions = [
        buffer.is_runtime_answer_buffer_shadow_enabled_for_session(123, user_id=7, exam_id=55)
        for _ in range(20)
    ]
    eligible = [
        session_id
        for session_id in range(1, 1001)
        if buffer.is_runtime_answer_buffer_shadow_enabled_for_session(
            session_id,
            user_id=7,
            exam_id=55,
        )
    ]

    assert len(set(decisions)) == 1
    assert 50 <= len(eligible) <= 150


def test_answer_payload_hash_normalizes_decimal_and_float_points() -> None:
    base_payload = {
        "selected_option_id": 1,
        "selected_option_ids": None,
        "answer_text": None,
        "statement_answers": None,
        "answer_metadata": {"phase": "6.2"},
        "is_correct": False,
    }

    assert buffer.answer_payload_hash({**base_payload, "points_earned": Decimal("0.00")}) == (
        buffer.answer_payload_hash({**base_payload, "points_earned": 0.0})
    )
    assert buffer.answer_payload_hash({**base_payload, "points_earned": Decimal("1.00")}) == (
        buffer.answer_payload_hash({**base_payload, "points_earned": 1.0})
    )
    assert buffer.answer_payload_hash({**base_payload, "points_earned": Decimal("0.50")}) == (
        buffer.answer_payload_hash({**base_payload, "points_earned": 0.5})
    )


def test_final_submit_service_does_not_read_runtime_shadow_keys() -> None:
    final_submit_source = Path("app/services/final_submit_service.py").read_text(encoding="utf-8")

    assert "shadow_session_answers_key" not in final_submit_source
    assert "runtime:answer_shadow" not in final_submit_source
    assert "record_runtime_answer_shadow" not in final_submit_source


def test_answer_payload_hash_is_stable_and_hides_raw_text() -> None:
    payload = {
        "question_id": 1,
        "selected_option_id": None,
        "selected_option_ids": [3, 2],
        "answer_text": "jawaban rahasia",
        "statement_answers": {"1": True},
        "answer_metadata": {"source": "apk"},
        "is_correct": True,
        "points_earned": 1,
    }

    digest = buffer.answer_payload_hash(payload)

    assert digest == buffer.answer_payload_hash(dict(payload))
    assert len(digest) == 64
    assert "jawaban rahasia" not in digest


class _ShadowPipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def hset(self, key, mapping=None, **_kwargs):
        self.ops.append(("hset", key, dict(mapping or {})))
        return self

    def sadd(self, key, *values):
        self.ops.append(("sadd", key, values))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    async def execute(self):
        for op in self.ops:
            if op[0] == "hset":
                _, key, mapping = op
                self.redis.hashes.setdefault(key, {}).update(mapping)
            elif op[0] == "sadd":
                _, key, values = op
                self.redis.sets.setdefault(key, set()).update(values)
            elif op[0] == "expire":
                _, key, ttl = op
                self.redis.ttls[key] = ttl
        return []


class _ShadowRedis:
    def __init__(self):
        self.hashes = {}
        self.sets = {}
        self.ttls = {}

    def pipeline(self):
        return _ShadowPipeline(self)


@pytest.mark.asyncio
async def test_record_runtime_answer_shadow_is_hash_only_and_best_effort(monkeypatch) -> None:
    fake_redis = _ShadowRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 100)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_session_ids", "")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_exam_ids", "")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_ttl_seconds", 3600)
    monkeypatch.setattr(buffer, "get_redis", fake_get_redis)

    count = await buffer.record_runtime_answer_shadow(
        session_id=123,
        user_id=7,
        exam_id=55,
        answers=[
            {
                "question_id": 9,
                "answer_text": "raw secret answer",
                "answer_metadata": {"source": "apk"},
            }
        ],
        log_prefix="TEST",
    )

    assert count == 1
    stored = fake_redis.hashes[buffer.shadow_session_answers_key(123)]["9"]
    decoded = json.loads(stored)
    assert set(decoded) == {"question_id", "payload_hash", "updated_at"}
    assert decoded["question_id"] == 9
    assert len(decoded["payload_hash"]) == 64
    assert "raw secret answer" not in stored
    assert "123" in fake_redis.sets[buffer.SHADOW_SESSION_INDEX_KEY]
    assert fake_redis.ttls[buffer.shadow_session_answers_key(123)] == 3600


@pytest.mark.asyncio
async def test_record_runtime_answer_shadow_failure_does_not_raise(monkeypatch) -> None:
    async def failing_get_redis():
        raise RuntimeError("redis down")

    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 100)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_session_ids", "")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_exam_ids", "")
    monkeypatch.setattr(buffer, "get_redis", failing_get_redis)

    count = await buffer.record_runtime_answer_shadow(
        session_id=123,
        user_id=7,
        exam_id=55,
        answers=[{"question_id": 9, "answer_text": "raw"}],
    )

    assert count == 0
