#!/usr/bin/env python3
"""Read-only consistency checker for Phase 6 runtime answer shadow mirrors.

The checker compares PostgreSQL latest answer payload hashes with Redis shadow
mirror hashes when shadow keys exist. It never prints raw answer content, user
PII, tokens, or Redis values beyond aggregate counts.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare PostgreSQL answers with Redis runtime shadow hashes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum sessions to sample; defaults to app config sample limit.",
    )
    parser.add_argument(
        "--statuses",
        default="in_progress,submitted,completed",
        help="Comma-separated session statuses to sample.",
    )
    parser.add_argument(
        "--include-session-ids",
        action="store_true",
        help="Include numeric session IDs in output for operator debugging; off by default.",
    )
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


async def _load_sample_sessions(db: Any, statuses: Sequence[str], limit: int) -> List[int]:
    from sqlalchemy import select
    from app.models.session import ExamSession

    stmt = (
        select(ExamSession.id)
        .where(ExamSession.status.in_(list(statuses)))
        .order_by(ExamSession.id.desc())
        .limit(max(1, int(limit)))
    )
    rows = await db.execute(stmt)
    return [int(value) for value in rows.scalars().all()]


async def _load_answers(db: Any, session_ids: Sequence[int]) -> Dict[int, Dict[int, Any]]:
    if not session_ids:
        return {}
    from sqlalchemy import select
    from app.models.session import Answer

    rows = await db.execute(select(Answer).where(Answer.session_id.in_(list(session_ids))))
    return _latest_answers_by_session_question(rows.scalars().all())


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


async def _count_stale_shadow_sessions(redis: Any, sampled_session_ids: set[int]) -> int:
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


async def run_check(args: argparse.Namespace) -> Dict[str, Any]:
    from app.config import settings
    from app.database import async_session_read
    from app.core.redis_pubsub import get_redis
    from app.services.answer_runtime_buffer import answer_payload_hash

    statuses = [item.strip() for item in str(args.statuses).split(",") if item.strip()]
    limit = args.limit or int(getattr(settings, "answer_runtime_buffer_consistency_sample_limit", 100))

    summary: Dict[str, Any] = {
        "checked_sessions": 0,
        "checked_answers": 0,
        "missing_in_redis": 0,
        "extra_in_redis": 0,
        "payload_hash_mismatch": 0,
        "stale_runtime_sessions": 0,
        "redis_errors": 0,
    }
    if args.include_session_ids:
        summary["session_ids"] = []

    async with async_session_read() as db:
        session_ids = await _load_sample_sessions(db, statuses, limit)
        summary["checked_sessions"] = len(session_ids)
        if args.include_session_ids:
            summary["session_ids"] = session_ids
        answers_by_session = await _load_answers(db, session_ids)

    try:
        redis = await get_redis()
    except Exception:
        summary["redis_errors"] += 1
        return summary

    sampled_set = set(session_ids)
    try:
        summary["stale_runtime_sessions"] = await _count_stale_shadow_sessions(redis, sampled_set)
    except Exception:
        summary["redis_errors"] += 1

    for session_id in session_ids:
        db_answers = answers_by_session.get(session_id, {})
        try:
            redis_hashes, mirror_exists = await _load_shadow_hashes(redis, session_id)
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


async def async_main() -> int:
    args = build_parser().parse_args()
    summary = await run_check(args)
    print(json.dumps(summary, sort_keys=True))
    if summary.get("payload_hash_mismatch") or summary.get("redis_errors"):
        return 2
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
