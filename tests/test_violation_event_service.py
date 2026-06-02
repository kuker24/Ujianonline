from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.answer import ViolationLog
from app.services import violation_event_service as service


class _FakeMappings:
    def __init__(self, row):
        self._row = row

    def one_or_none(self):
        return self._row


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return _FakeMappings(self._row)


class _FakeDb:
    def __init__(self, row):
        self.row = row
        self.execute_calls = 0

    async def execute(self, _stmt):
        self.execute_calls += 1
        return _FakeResult(self.row)


class _FakeRedis:
    def __init__(self, *, duplicate: bool = False):
        self.duplicate = duplicate
        self.pending = []
        self.hashes = {}
        self.lists = {}

    async def set(self, key, value, nx=False, ex=None):
        if self.duplicate:
            return False
        return True

    async def rpush(self, key, value):
        self.pending.append((key, value))
        return len(self.pending)

    async def expire(self, key, seconds):
        return True

    async def hincrby(self, key, field, amount):
        self.hashes.setdefault(key, {})[field] = self.hashes.setdefault(key, {}).get(field, 0) + amount
        return self.hashes[key][field]

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    async def ltrim(self, key, start, end):
        self.lists[key] = self.lists.get(key, [])[start : end + 1]
        return True


class _FailingRedis(_FakeRedis):
    async def set(self, key, value, nx=False, ex=None):
        raise RuntimeError("redis down")


async def _fake_get_redis(redis):
    return redis


def _session_row(status="in_progress", violation_count=2):
    return {
        "id": 10,
        "exam_id": 99,
        "violation_count": violation_count,
        "status": status,
        "end_time": None,
    }


def _violation_log():
    return ViolationLog(
        session_id=10,
        exam_id=0,
        event_type="tab_switch",
        event_data={"source": "apk", "reason": "test"},
        timestamp=datetime.now(timezone.utc),
        user_agent="SXB-Client test",
        screen_resolution="1080x1920",
    )


@pytest.mark.asyncio
async def test_enqueue_violation_event_queues_and_updates_runtime_cache(monkeypatch) -> None:
    fake_redis = _FakeRedis()
    monkeypatch.setattr(service, "get_redis", lambda: _fake_get_redis(fake_redis))

    result = await service.enqueue_violation_event(
        _FakeDb(_session_row()),
        _violation_log(),
        SimpleNamespace(id=7, username="student01"),
    )

    assert result.status == "queued"
    assert result.violation_count == 2
    assert fake_redis.pending[0][0] == service.PENDING_KEY
    assert service.AGGREGATE_KEY_TEMPLATE.format(exam_id=99) in fake_redis.hashes
    assert service.SESSION_KEY_TEMPLATE.format(session_id=10) in fake_redis.hashes


@pytest.mark.asyncio
async def test_enqueue_violation_event_dedupes_burst_without_queueing(monkeypatch) -> None:
    fake_redis = _FakeRedis(duplicate=True)
    monkeypatch.setattr(service, "get_redis", lambda: _fake_get_redis(fake_redis))

    result = await service.enqueue_violation_event(
        _FakeDb(_session_row()),
        _violation_log(),
        SimpleNamespace(id=7, username="student01"),
    )

    assert result.status == "duplicate"
    assert fake_redis.pending == []


@pytest.mark.asyncio
async def test_enqueue_violation_event_drops_best_effort_when_redis_fails(monkeypatch) -> None:
    fake_redis = _FailingRedis()
    monkeypatch.setattr(service, "get_redis", lambda: _fake_get_redis(fake_redis))

    result = await service.enqueue_violation_event(
        _FakeDb(_session_row()),
        _violation_log(),
        SimpleNamespace(id=7, username="student01"),
    )

    assert result.status == "dropped"
    assert result.violation_count == 2


@pytest.mark.asyncio
async def test_enqueue_violation_event_ignores_terminal_session(monkeypatch) -> None:
    fake_redis = _FakeRedis()
    monkeypatch.setattr(service, "get_redis", lambda: _fake_get_redis(fake_redis))

    result = await service.enqueue_violation_event(
        _FakeDb(_session_row(status="submitted")),
        _violation_log(),
        SimpleNamespace(id=7, username="student01"),
    )

    assert result.status == "ignored"
    assert fake_redis.pending == []
