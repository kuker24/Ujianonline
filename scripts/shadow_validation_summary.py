#!/usr/bin/env python3
"""Read-only Phase 6 shadow validation summary.

Summarizes PostgreSQL-vs-Redis shadow consistency and Redis shadow key health.
It never mutates Redis/DB and never prints raw answer content, tokens, or PII.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SHADOW_ANSWERS_PATTERN = "runtime:answer_shadow:session:*:answers"
SHADOW_ALL_PATTERN = "runtime:answer_shadow:*"
RUNTIME_BUFFER_PATTERN = "runtime:session:*:answers"
ANSWER_QUEUE_PATTERN = "runtime:answer_queue:*"
LEGACY_ANSWER_QUEUE_PATTERN = "answer_queue:*"
LOG_MARKER_EXPECTED_NOTE = (
    "When post-final shadow refresh runs, Docker/app logs should contain "
    "SHADOW_POST_FINAL_REFRESH_OK; failures should contain "
    "SHADOW_POST_FINAL_REFRESH_FAILED."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only summary of Phase 6 Redis shadow validation evidence.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum sessions to sample.")
    parser.add_argument(
        "--statuses",
        default="in_progress,submitted,completed",
        help="Comma-separated session statuses to sample.",
    )
    parser.add_argument("--session-id", type=int, default=None, help="Restrict to one session ID.")
    parser.add_argument("--exam-id", type=int, default=None, help="Restrict sampled sessions to one exam ID.")
    parser.add_argument("--json", action="store_true", default=True, help="Emit JSON output (default).")
    parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="Exit non-zero on mismatch, Redis errors, queue keys, buffer keys, or TTL issues.",
    )
    parser.add_argument("--redact", dest="redact", action="store_true", default=True)
    parser.add_argument("--no-redact", dest="redact", action="store_false")
    return parser


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_loads(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    try:
        decoded = json.loads(str(raw))
    except Exception:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _redact_id(value: int) -> str:
    text = str(int(value))
    return "***" + text[-2:]


def _format_session_ids(session_ids: Iterable[int], *, redact: bool) -> List[Any]:
    values = sorted({int(item) for item in session_ids})
    if redact:
        return [_redact_id(item) for item in values]
    return values


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_seconds(timestamp: datetime, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return max(0, int((now - timestamp).total_seconds()))


def _statement_answers_from_metadata(answer_metadata: Mapping[str, Any] | None) -> Any:
    if isinstance(answer_metadata, Mapping):
        return answer_metadata.get("statement_answers")
    return None


def _answer_payload(answer: Any) -> Dict[str, Any]:
    metadata = dict(answer.answer_metadata or {})
    return {
        "selected_option_id": answer.selected_option_id,
        "selected_option_ids": list(answer.selected_option_ids or []) or None,
        "answer_text": answer.answer_text,
        "statement_answers": _statement_answers_from_metadata(metadata),
        "answer_metadata": metadata,
        "is_correct": answer.is_correct,
        "points_earned": answer.points_earned,
    }


def _latest_answers_by_session_question(answers: Iterable[Any]) -> Dict[int, Dict[int, Any]]:
    latest: Dict[int, Dict[int, Any]] = defaultdict(dict)
    for answer in answers:
        session_id = int(answer.session_id)
        question_id = int(answer.question_id)
        current = latest[session_id].get(question_id)
        if current is None:
            latest[session_id][question_id] = answer
            continue
        answer_ts = answer.answered_at or answer.id or 0
        current_ts = current.answered_at or current.id or 0
        if (answer_ts, answer.id or 0) >= (current_ts, current.id or 0):
            latest[session_id][question_id] = answer
    return latest


async def _scan_keys(redis: Any, pattern: str) -> List[str]:
    keys: List[str] = []
    async for raw_key in redis.scan_iter(match=pattern):
        keys.append(raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key))
    return keys


async def _count_pattern(redis: Any, pattern: str) -> int:
    return len(await _scan_keys(redis, pattern))


def _session_id_from_shadow_answers_key(key: str) -> int | None:
    match = re.search(r"runtime:answer_shadow:session:(\d+):answers$", key)
    if not match:
        return None
    return _safe_int(match.group(1))


async def _load_shadow_hashes(redis: Any, session_id: int) -> Tuple[Dict[int, str], bool]:
    from app.services.answer_runtime_buffer import shadow_session_answers_key

    raw = await redis.hgetall(shadow_session_answers_key(session_id))
    if not raw:
        return {}, False
    hashes: Dict[int, str] = {}
    for raw_question_id, raw_payload in dict(raw).items():
        raw_question_value = (
            raw_question_id.decode() if isinstance(raw_question_id, bytes) else raw_question_id
        )
        question_id = _safe_int(raw_question_value)
        if question_id is None:
            continue
        payload = _json_loads(raw_payload)
        payload_hash = str(payload.get("payload_hash") or "")
        if payload_hash:
            hashes[question_id] = payload_hash
    return hashes, True


async def _count_stale_shadow_sessions(redis: Any, sampled_session_ids: Set[int]) -> int:
    from app.services.answer_runtime_buffer import SHADOW_SESSION_INDEX_KEY

    try:
        raw_ids = await redis.smembers(SHADOW_SESSION_INDEX_KEY)
    except Exception:
        return 0
    stale = 0
    for raw_id in raw_ids or []:
        value = raw_id.decode() if isinstance(raw_id, bytes) else raw_id
        session_id = _safe_int(value)
        if session_id is not None and session_id not in sampled_session_ids:
            stale += 1
    return stale


async def _load_sample_sessions(
    db: Any,
    *,
    statuses: Sequence[str],
    limit: int,
    session_id: int | None,
    exam_id: int | None,
) -> List[int]:
    from sqlalchemy import select
    from app.models.session import ExamSession

    if session_id is not None:
        stmt = select(ExamSession.id).where(ExamSession.id == int(session_id)).limit(1)
    else:
        stmt = select(ExamSession.id).where(ExamSession.status.in_(list(statuses)))
        if exam_id is not None:
            stmt = stmt.where(ExamSession.exam_id == int(exam_id))
        stmt = stmt.order_by(ExamSession.id.desc()).limit(max(1, int(limit)))
    rows = await db.execute(stmt)
    return [int(value) for value in rows.scalars().all()]


async def _load_answers(db: Any, session_ids: Sequence[int]) -> Dict[int, Dict[int, Any]]:
    if not session_ids:
        return {}
    from sqlalchemy import select
    from app.models.session import Answer

    rows = await db.execute(select(Answer).where(Answer.session_id.in_(list(session_ids))))
    return _latest_answers_by_session_question(rows.scalars().all())


async def _consistency_summary(
    db: Any,
    redis: Any,
    *,
    statuses: Sequence[str],
    limit: int,
    session_id: int | None,
    exam_id: int | None,
) -> Dict[str, Any]:
    from app.services.answer_runtime_buffer import answer_payload_hash

    session_ids = await _load_sample_sessions(
        db,
        statuses=statuses,
        limit=limit,
        session_id=session_id,
        exam_id=exam_id,
    )
    answers_by_session = await _load_answers(db, session_ids)
    summary: Dict[str, Any] = {
        "checked_sessions": len(session_ids),
        "checked_answers": 0,
        "missing_in_redis": 0,
        "extra_in_redis": 0,
        "payload_hash_mismatch": 0,
        "stale_runtime_sessions": 0,
        "redis_errors": 0,
    }
    sampled_set = set(session_ids)
    try:
        summary["stale_runtime_sessions"] = await _count_stale_shadow_sessions(redis, sampled_set)
    except Exception:
        summary["redis_errors"] += 1

    for sampled_session_id in session_ids:
        db_answers = answers_by_session.get(sampled_session_id, {})
        try:
            redis_hashes, mirror_exists = await _load_shadow_hashes(redis, sampled_session_id)
        except Exception:
            summary["redis_errors"] += 1
            continue
        if not mirror_exists:
            continue
        db_hashes = {
            question_id: answer_payload_hash(_answer_payload(answer))
            for question_id, answer in db_answers.items()
        }
        summary["checked_answers"] += len(db_hashes)
        db_questions = set(db_hashes)
        redis_questions = set(redis_hashes)
        summary["missing_in_redis"] += len(db_questions - redis_questions)
        summary["extra_in_redis"] += len(redis_questions - db_questions)
        for question_id in db_questions & redis_questions:
            if db_hashes[question_id] != redis_hashes[question_id]:
                summary["payload_hash_mismatch"] += 1
    return summary


async def _redis_shadow_summary(
    redis: Any,
    *,
    allowed_session_ids: Set[int] | None = None,
    redact: bool = True,
) -> Dict[str, Any]:
    from app.services.answer_runtime_buffer import shadow_session_meta_key

    runtime_shadow_keys_count = await _count_pattern(redis, SHADOW_ALL_PATTERN)
    runtime_answer_buffer_keys_count = await _count_pattern(redis, RUNTIME_BUFFER_PATTERN)
    answer_queue_keys_count = await _count_pattern(redis, ANSWER_QUEUE_PATTERN)
    legacy_answer_queue_keys_count = await _count_pattern(redis, LEGACY_ANSWER_QUEUE_PATTERN)

    shadow_answer_keys = await _scan_keys(redis, SHADOW_ANSWERS_PATTERN)
    sessions_with_shadow_set: Set[int] = set()
    ages: List[int] = []
    ttls: List[int] = []
    keys_without_ttl = 0
    post_final_refresh_meta_count = 0
    post_final_refresh_missing_count = 0

    now = datetime.now(timezone.utc)
    for key in shadow_answer_keys:
        sid = _session_id_from_shadow_answers_key(key)
        if sid is None:
            continue
        if allowed_session_ids is not None and sid not in allowed_session_ids:
            continue
        sessions_with_shadow_set.add(sid)
        ttl = await redis.ttl(key)
        if ttl == -1:
            keys_without_ttl += 1
        elif ttl is not None and int(ttl) >= 0:
            ttls.append(int(ttl))
        raw_answers = await redis.hgetall(key)
        for raw_payload in raw_answers.values():
            payload = _json_loads(raw_payload)
            timestamp = _parse_datetime(payload.get("updated_at"))
            if timestamp is not None:
                ages.append(_age_seconds(timestamp, now=now))

        meta_key = shadow_session_meta_key(sid)
        meta_ttl = await redis.ttl(meta_key)
        if meta_ttl == -1:
            keys_without_ttl += 1
        elif meta_ttl is not None and int(meta_ttl) >= 0:
            ttls.append(int(meta_ttl))
        meta = _json_loads_dict(await redis.hgetall(meta_key))
        for timestamp_key in ("refreshed_at", "updated_at"):
            timestamp = _parse_datetime(meta.get(timestamp_key))
            if timestamp is not None:
                ages.append(_age_seconds(timestamp, now=now))
        if str(meta.get("refreshed_after_final_submit") or "").lower() == "true":
            post_final_refresh_meta_count += 1
        else:
            post_final_refresh_missing_count += 1

    return {
        "runtime_shadow_keys_count": runtime_shadow_keys_count,
        "runtime_answer_buffer_keys_count": runtime_answer_buffer_keys_count,
        "answer_queue_keys_count": answer_queue_keys_count,
        "legacy_answer_queue_keys_count": legacy_answer_queue_keys_count,
        "oldest_shadow_key_age_seconds": max(ages) if ages else None,
        "newest_shadow_key_age_seconds": min(ages) if ages else None,
        "ttl_min_seconds": min(ttls) if ttls else None,
        "ttl_max_seconds": max(ttls) if ttls else None,
        "shadow_keys_without_ttl": keys_without_ttl,
        "sessions_with_shadow": len(sessions_with_shadow_set),
        "shadow_session_ids": _format_session_ids(sessions_with_shadow_set, redact=redact),
        "post_final_refresh_meta_count": post_final_refresh_meta_count,
        "post_final_refresh_missing_count": post_final_refresh_missing_count,
        "log_marker_expected_note": LOG_MARKER_EXPECTED_NOTE,
    }


def _json_loads_dict(raw_hash: Mapping[Any, Any]) -> Dict[str, Any]:
    decoded: Dict[str, Any] = {}
    for raw_key, raw_value in dict(raw_hash or {}).items():
        key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
        value = raw_value.decode() if isinstance(raw_value, bytes) else raw_value
        decoded[key] = value
    return decoded


def should_fail(summary: Mapping[str, Any]) -> bool:
    return any(
        int(summary.get(field) or 0) > 0
        for field in (
            "payload_hash_mismatch",
            "redis_errors",
            "shadow_keys_without_ttl",
            "answer_queue_keys_count",
            "legacy_answer_queue_keys_count",
            "runtime_answer_buffer_keys_count",
        )
    )


async def run_summary(args: argparse.Namespace) -> Dict[str, Any]:
    from app.database import async_session_read
    from app.core.redis_pubsub import get_redis

    statuses = [item.strip() for item in str(args.statuses).split(",") if item.strip()]
    redis = await get_redis()
    async with async_session_read() as db:
        session_ids = await _load_sample_sessions(
            db,
            statuses=statuses,
            limit=max(1, int(args.limit)),
            session_id=args.session_id,
            exam_id=args.exam_id,
        )
        consistency = await _consistency_summary(
            db,
            redis,
            statuses=statuses,
            limit=max(1, int(args.limit)),
            session_id=args.session_id,
            exam_id=args.exam_id,
        )
    allowed = set(session_ids) if (args.session_id is not None or args.exam_id is not None) else None
    redis_summary = await _redis_shadow_summary(redis, allowed_session_ids=allowed, redact=bool(args.redact))
    summary = {**consistency, **redis_summary}
    summary["filters"] = {
        "session_id": _redact_id(args.session_id) if args.session_id and args.redact else args.session_id,
        "exam_id": _redact_id(args.exam_id) if args.exam_id and args.redact else args.exam_id,
        "limit": max(1, int(args.limit)),
        "statuses": statuses,
        "redact": bool(args.redact),
    }
    summary["sampled_session_ids"] = _format_session_ids(session_ids, redact=bool(args.redact))
    summary["read_only"] = True
    return summary


def main() -> int:
    args = build_parser().parse_args()
    summary = asyncio.run(run_summary(args))
    print(json.dumps(summary, sort_keys=True, default=str))
    if args.fail_on_mismatch and should_fail(summary):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
