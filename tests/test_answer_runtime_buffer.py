from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import answer_runtime_buffer as buffer
from app.services import answer_sync_service


def test_runtime_answer_buffer_keys_match_phase6_spec() -> None:
    assert buffer.PENDING_QUEUE_KEY == "runtime:answer_queue:pending"
    assert buffer.PROCESSING_QUEUE_KEY == "runtime:answer_queue:processing"
    assert buffer.session_answers_key(123) == "runtime:session:123:answers"
    assert buffer.session_dirty_questions_key(123) == "runtime:session:123:dirty_questions"
    assert buffer.session_answered_count_key(123) == "runtime:session:123:answered_count"


def test_runtime_answer_buffer_disabled_by_default() -> None:
    assert buffer.is_runtime_answer_buffer_enabled() is False


class _FakeRuntimeBufferService:
    def __init__(self, db, current_user):
        self.db = db
        self.current_user = current_user

    async def accept_batch(self, batch_data):
        return {
            "status": "buffered",
            "queued_count": len(batch_data.answers),
            "queue_id": "redis-test",
            "timestamp": datetime.now(timezone.utc),
        }

    async def accept_journal_events(self, sync_data, accepted_events):
        return len(accepted_events)


@pytest.mark.asyncio
async def test_answer_sync_service_routes_batch_to_runtime_buffer_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(answer_sync_service, "is_runtime_answer_buffer_enabled", lambda: True)
    monkeypatch.setattr(answer_sync_service, "AnswerRuntimeBufferService", _FakeRuntimeBufferService)

    service = answer_sync_service.AnswerSyncService(db=None, current_user=SimpleNamespace(id=7))
    batch_data = SimpleNamespace(
        session_id=123,
        answers=[SimpleNamespace(question_id=1)],
    )

    result = await service.accept_batch(batch_data)

    assert result["status"] == "buffered"
    assert result["queued_count"] == 1


class _BufferPipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def hset(self, key, mapping):
        self.ops.append(("hset", key, mapping))
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
        return []


class _BufferRedis:
    def __init__(self):
        self.hashes = {}
        self.sets = {}
        self.values = {}
        self.pending = []

    def pipeline(self):
        return _BufferPipeline(self)

    async def hlen(self, key):
        return len(self.hashes.get(key, {}))

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def rpush(self, key, value):
        self.pending.append((key, value))
        return len(self.pending)

    async def expire(self, key, ttl):
        return True


@pytest.mark.asyncio
async def test_runtime_answer_buffer_answered_count_uses_total_hash_size(monkeypatch) -> None:
    fake_redis = _BufferRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(buffer, "get_redis", fake_get_redis)

    first_count = await buffer._write_answer_buffer(
        session_id=123,
        user_id=7,
        exam_id=55,
        answers=[{"question_id": 1}, {"question_id": 2}],
    )
    second_count = await buffer._write_answer_buffer(
        session_id=123,
        user_id=7,
        exam_id=55,
        answers=[{"question_id": 3}],
    )

    assert first_count == 2
    assert second_count == 1
    assert fake_redis.values[buffer.session_answered_count_key(123)] == 3
