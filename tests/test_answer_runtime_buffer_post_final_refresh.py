import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import answer_runtime_buffer as buffer


class _ScalarRows:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _AnswerResult:
    def __init__(self, answers):
        self._answers = list(answers)

    def scalars(self):
        return _ScalarRows(self._answers)


class _FakeDb:
    def __init__(self, answers=None):
        self.answers = list(answers or [])
        self.execute_calls = 0

    async def execute(self, _stmt):
        self.execute_calls += 1
        return _AnswerResult(self.answers)


class _ShadowPipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def delete(self, key):
        self.ops.append(("delete", key))
        return self

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
            if op[0] == "delete":
                _, key = op
                self.redis.hashes.pop(key, None)
            elif op[0] == "hset":
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


def _answer(**overrides):
    values = {
        "id": 1,
        "session_id": 123,
        "question_id": 9,
        "selected_option_id": 2,
        "selected_option_ids": None,
        "answer_text": "raw secret answer",
        "answer_metadata": {
            "phase": "6.2c",
            "token": "raw-token-must-not-be-stored",
            "full_name": "Student Secret",
        },
        "is_correct": False,
        "points_earned": Decimal("0.00"),
        "answered_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _payload_from_answer(answer):
    metadata = dict(answer.answer_metadata or {})
    return {
        "selected_option_id": answer.selected_option_id,
        "selected_option_ids": list(answer.selected_option_ids or []) or None,
        "answer_text": answer.answer_text,
        "statement_answers": metadata.get("statement_answers"),
        "answer_metadata": metadata,
        "is_correct": answer.is_correct,
        "points_earned": answer.points_earned,
    }


@pytest.mark.asyncio
async def test_post_final_shadow_refresh_default_disabled_noops(monkeypatch) -> None:
    async def fail_get_redis():
        raise AssertionError("Redis must not be touched when shadow is disabled")

    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", False)
    monkeypatch.setattr(buffer, "get_redis", fail_get_redis)
    db = _FakeDb(answers=[_answer()])

    result = await buffer.refresh_runtime_answer_shadow_from_db(db, 123, exam_id=55)

    assert result == {"status": "skipped", "reason": "disabled", "answer_count": 0}
    assert db.execute_calls == 0


@pytest.mark.asyncio
async def test_post_final_shadow_refresh_allowlisted_session_writes_hash_only(monkeypatch) -> None:
    fake_redis = _ShadowRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 0)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_session_ids", "123")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_exam_ids", "")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_ttl_seconds", 3600)
    monkeypatch.setattr(buffer, "get_redis", fake_get_redis)

    result = await buffer.refresh_runtime_answer_shadow_from_db(
        _FakeDb(answers=[_answer()]),
        123,
        exam_id=55,
    )

    assert result == {"status": "ok", "answer_count": 1}
    stored = fake_redis.hashes[buffer.shadow_session_answers_key(123)]["9"]
    decoded = json.loads(stored)
    assert set(decoded) == {"question_id", "payload_hash", "updated_at"}
    assert decoded["question_id"] == 9
    assert len(decoded["payload_hash"]) == 64
    assert "raw secret answer" not in stored
    assert "raw-token-must-not-be-stored" not in stored
    assert "Student Secret" not in stored
    assert "answer_metadata" not in stored
    assert "answer_text" not in stored

    meta = fake_redis.hashes[buffer.shadow_session_meta_key(123)]
    assert meta["refreshed_from_db"] == "true"
    assert meta["refreshed_after_final_submit"] == "true"
    assert meta["answer_count"] == "1"
    assert fake_redis.ttls[buffer.shadow_session_answers_key(123)] == 3600
    assert "123" in fake_redis.sets[buffer.SHADOW_SESSION_INDEX_KEY]


@pytest.mark.asyncio
async def test_post_final_shadow_refresh_updates_stale_hash_to_match_committed_db(monkeypatch) -> None:
    fake_redis = _ShadowRedis()
    stale_answer = _answer(is_correct=False, points_earned=Decimal("0.00"))
    stale_hash = buffer.answer_payload_hash(_payload_from_answer(stale_answer))
    fake_redis.hashes[buffer.shadow_session_answers_key(123)] = {
        "9": json.dumps(
            {"question_id": 9, "payload_hash": stale_hash, "updated_at": "old"},
            separators=(",", ":"),
        )
    }
    committed_answer = _answer(
        is_correct=True,
        points_earned=Decimal("1.00"),
        answer_metadata={"phase": "final_submit", "step": "graded"},
    )

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 0)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_session_ids", "123")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_exam_ids", "")
    monkeypatch.setattr(buffer, "get_redis", fake_get_redis)

    result = await buffer.refresh_runtime_answer_shadow_from_db(
        _FakeDb(answers=[committed_answer]),
        123,
        exam_id=55,
    )

    assert result["status"] == "ok"
    stored = json.loads(fake_redis.hashes[buffer.shadow_session_answers_key(123)]["9"])
    committed_hash = buffer.answer_payload_hash(_payload_from_answer(committed_answer))
    assert stored["payload_hash"] == committed_hash
    assert stored["payload_hash"] != stale_hash

    db_hashes = {9: committed_hash}
    redis_hashes = {9: stored["payload_hash"]}
    payload_hash_mismatch = sum(
        1 for question_id in db_hashes if db_hashes[question_id] != redis_hashes[question_id]
    )
    assert payload_hash_mismatch == 0


@pytest.mark.asyncio
async def test_post_final_shadow_refresh_redis_failure_is_caught(monkeypatch, caplog) -> None:
    async def failing_get_redis():
        raise RuntimeError("redis down")

    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_enabled", True)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_percentage", 0)
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_session_ids", "123")
    monkeypatch.setattr(buffer.settings, "answer_runtime_buffer_shadow_exam_ids", "")
    monkeypatch.setattr(buffer, "get_redis", failing_get_redis)

    result = await buffer.refresh_runtime_answer_shadow_from_db(
        _FakeDb(answers=[_answer()]),
        123,
        exam_id=55,
    )

    assert result["status"] == "failed"
    assert result["reason"] == "RuntimeError"
    assert "SHADOW_POST_FINAL_REFRESH_FAILED" in caplog.text
    assert "raw secret answer" not in caplog.text
    assert "raw-token-must-not-be-stored" not in caplog.text
