import json

import pytest

from app.services import answer_runtime_buffer as buffer


def test_runtime_answer_buffer_shadow_disabled_by_default() -> None:
    assert buffer.is_runtime_answer_buffer_shadow_enabled() is False
    assert buffer.is_runtime_answer_buffer_shadow_enabled_for_session(123, user_id=7, exam_id=55) is False
    assert buffer._answer_shadow_percentage() == 0
    assert buffer.runtime_answer_shadow_ttl_seconds() == 14400


def test_runtime_answer_buffer_shadow_percentage_is_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 10)

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
    monkeypatch.setattr(buffer, "get_redis", failing_get_redis)

    count = await buffer.record_runtime_answer_shadow(
        session_id=123,
        user_id=7,
        exam_id=55,
        answers=[{"question_id": 9, "answer_text": "raw"}],
    )

    assert count == 0
