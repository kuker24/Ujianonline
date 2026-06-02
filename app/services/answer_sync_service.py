"""Internal answer sync service for legacy-compatible exam answer endpoints.

Phase 5 starts with direct-write behavior. Queue/hybrid Redis buffering can be
introduced behind feature flags after this service boundary is stable.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exam_runtime_cache import invalidate_session_answer_count_cache
from app.core.exam_runtime_state import (
    add_answered_questions_and_count,
    update_runtime_snapshot_answered_count,
)
from app.core.exam_session_helpers import merge_statement_answer_metadata
from app.core.redis_pubsub import get_redis, update_session_answers
from app.services.answer_runtime_buffer import (
    AnswerRuntimeBufferService,
    is_runtime_answer_buffer_enabled,
)
from app.models.question import Question
from app.models.session import Answer, ExamSession
from app.schemas.answer import (
    AnswerJournalAck,
    AnswerJournalSyncRequest,
    AnswerJournalSyncResponse,
    AutoSaveRequest,
    AutoSaveResponse,
)

logger = logging.getLogger(__name__)

SESSION_WRITE_LOCK_NAMESPACE = 48102
ANSWER_JOURNAL_EVENT_TTL_SECONDS = 48 * 60 * 60
ANSWER_JOURNAL_MAX_SYNC_EVENTS = 250
ANSWER_JOURNAL_EVENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9:_-]{8,118}$")


def _answer_journal_event_set_key(session_id: int) -> str:
    return f"exam:answer-journal:v1:session:{session_id}:event-ids"


def _normalize_answer_journal_event_id(raw_event_id: str) -> str:
    return str(raw_event_id or "").strip().lower()


def _is_valid_answer_journal_event_id(event_id: str) -> bool:
    return bool(ANSWER_JOURNAL_EVENT_ID_RE.match(event_id))


async def _acquire_session_write_lock(db: AsyncSession, session_id: int) -> None:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :session_id)"),
        {"namespace": SESSION_WRITE_LOCK_NAMESPACE, "session_id": session_id},
    )


async def _ensure_session_in_progress_for_user(
    db: AsyncSession,
    *,
    session_id: int,
    user_id: int,
    lock_row: bool = False,
) -> ExamSession:
    query = select(ExamSession).where(
        ExamSession.id == session_id,
        ExamSession.user_id == user_id,
    )
    if lock_row:
        query = query.with_for_update()

    result = await db.execute(query)
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan")
    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Sesi ujian sudah berakhir")
    return session


class AnswerSyncService:
    """Direct-mode answer sync service boundary."""

    def __init__(self, db: AsyncSession, current_user: Any):
        self.db = db
        self.current_user = current_user

    async def accept_single_answer(self, *args: Any, **kwargs: Any) -> None:
        """Reserved service boundary for submit-answer Phase 5 follow-up."""
        raise NotImplementedError("single answer migration is intentionally deferred")

    async def accept_legacy_autosave(self, save_data: AutoSaveRequest) -> AutoSaveResponse:
        """Handle legacy autosave cache updates without direct answer writes."""
        result = await self.db.execute(
            select(ExamSession).where(
                ExamSession.id == save_data.session_id,
                ExamSession.user_id == self.current_user.id,
                ExamSession.status == "in_progress",
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan atau sudah berakhir")

        await update_session_answers(session.id, save_data.answers)
        try:
            answered_count_runtime = await add_answered_questions_and_count(
                session.id,
                list((save_data.answers or {}).keys()),
            )
            if answered_count_runtime is not None:
                await update_runtime_snapshot_answered_count(
                    session.id,
                    expected_user_id=self.current_user.id,
                    answered_count=answered_count_runtime,
                    mark_stale=False,
                    status="in_progress",
                )
        except Exception as runtime_exc:
            logger.debug(
                "AUTO-SAVE | session=%s | runtime answered_count update skipped: %s",
                session.id,
                str(runtime_exc),
            )

        return AutoSaveResponse(
            status="success",
            saved_count=len(save_data.answers),
            timestamp=datetime.now(timezone.utc),
        )

    async def accept_batch(self, batch_data: Any) -> Dict[str, Any]:
        """Persist batch autosave in direct DB mode with no-op update skip."""
        if is_runtime_answer_buffer_enabled():
            return await AnswerRuntimeBufferService(self.db, self.current_user).accept_batch(batch_data)

        result = await self.db.execute(
            select(ExamSession).where(
                ExamSession.id == batch_data.session_id,
                ExamSession.user_id == self.current_user.id,
                ExamSession.status == "in_progress",
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan atau sudah berakhir")

        if not batch_data.answers:
            return {
                "status": "no_changes",
                "queued_count": 0,
                "queue_id": "empty",
                "timestamp": datetime.now(timezone.utc),
            }

        queue_id = str(uuid.uuid4())[:8]
        deduped_answer_map: Dict[int, Any] = {}
        for item in batch_data.answers:
            deduped_answer_map[int(item.question_id)] = item

        deduped_answers = list(deduped_answer_map.values())
        question_ids = [int(answer.question_id) for answer in deduped_answers]
        valid_question_ids: Set[int] = set()
        if question_ids:
            valid_question_result = await self.db.execute(
                select(Question.id).where(
                    Question.exam_id == session.exam_id,
                    Question.id.in_(question_ids),
                )
            )
            valid_question_ids = {int(row[0]) for row in valid_question_result.all()}

        session_id_value = int(session.id)
        if question_ids and len(valid_question_ids) != len(set(question_ids)):
            dropped_count = len(set(question_ids)) - len(valid_question_ids)
            logger.warning(
                "AUTO-SAVE-BATCH | Session %s | dropped %s invalid question_id(s)",
                session_id_value,
                dropped_count,
            )

        valid_answers = [a for a in deduped_answers if int(a.question_id) in valid_question_ids]

        await _acquire_session_write_lock(self.db, session_id_value)
        session = await _ensure_session_in_progress_for_user(
            self.db,
            session_id=session_id_value,
            user_id=self.current_user.id,
            lock_row=True,
        )
        session_id_value = int(session.id)

        existing_answer_map: Dict[int, Answer] = {}
        if valid_question_ids:
            existing_result = await self.db.execute(
                select(Answer).where(
                    Answer.session_id == session_id_value,
                    Answer.question_id.in_(valid_question_ids),
                )
            )
            existing_answer_map = {
                int(answer.question_id): answer for answer in existing_result.scalars().all()
            }

        now_utc = datetime.now(timezone.utc)
        changed_rows = 0
        for answer_data in valid_answers:
            question_id = int(answer_data.question_id)
            existing_answer = existing_answer_map.get(question_id)
            incoming_metadata = dict(answer_data.answer_metadata or {})
            existing_metadata = dict(existing_answer.answer_metadata or {}) if existing_answer else {}
            final_metadata, _ = merge_statement_answer_metadata(
                existing_metadata=existing_metadata,
                incoming_metadata=incoming_metadata,
                incoming_statement_answers=answer_data.statement_answers,
            )

            if existing_answer:
                has_changed = (
                    existing_answer.selected_option_id != answer_data.selected_option_id
                    or existing_answer.selected_option_ids != answer_data.selected_option_ids
                    or existing_answer.answer_text != answer_data.answer_text
                    or dict(existing_answer.answer_metadata or {}) != final_metadata
                )
                if has_changed:
                    existing_answer.selected_option_id = answer_data.selected_option_id
                    existing_answer.selected_option_ids = answer_data.selected_option_ids
                    existing_answer.answer_text = answer_data.answer_text
                    existing_answer.answer_metadata = final_metadata
                    existing_answer.answered_at = now_utc
                    existing_answer.is_correct = None
                    existing_answer.points_earned = None
                    changed_rows += 1
            else:
                self.db.add(
                    Answer(
                        session_id=session_id_value,
                        question_id=question_id,
                        selected_option_id=answer_data.selected_option_id,
                        selected_option_ids=answer_data.selected_option_ids,
                        answer_text=answer_data.answer_text,
                        answer_metadata=final_metadata,
                        answered_at=now_utc,
                        is_correct=None,
                        points_earned=None,
                    )
                )
                changed_rows += 1

        if changed_rows > 0:
            try:
                await self.db.commit()
                invalidate_session_answer_count_cache(session_id_value)
            except Exception as integrity_error:
                logger.warning(
                    "AUTO-SAVE-BATCH | Session %s | write conflict, retrying serialized merge: %s",
                    session_id_value,
                    str(integrity_error),
                )
                await self.db.rollback()
                await self._retry_batch_serialized(session_id_value, valid_answers)
                changed_rows = max(changed_rows, len(valid_answers))

        await update_session_answers(session_id_value, {str(a.question_id): True for a in valid_answers})
        await self._update_runtime_answered_count(
            session_id_value,
            [int(a.question_id) for a in valid_answers],
            log_prefix="AUTO-SAVE-BATCH",
        )

        return {
            "status": "saved_to_db" if changed_rows > 0 else "no_changes",
            "queued_count": len(valid_answers),
            "queue_id": queue_id,
            "timestamp": datetime.now(timezone.utc),
        }

    async def _retry_batch_serialized(self, session_id_value: int, valid_answers: List[Any]) -> None:
        await _acquire_session_write_lock(self.db, session_id_value)
        await _ensure_session_in_progress_for_user(
            self.db,
            session_id=session_id_value,
            user_id=self.current_user.id,
            lock_row=True,
        )
        fallback_timestamp = datetime.now(timezone.utc)
        for answer_data in valid_answers:
            incoming_metadata = dict(answer_data.answer_metadata or {})
            retry_existing_result = await self.db.execute(
                select(Answer)
                .where(
                    Answer.session_id == session_id_value,
                    Answer.question_id == int(answer_data.question_id),
                )
                .with_for_update()
            )
            retry_existing_answer = retry_existing_result.scalar_one_or_none()
            retry_existing_metadata = (
                dict(retry_existing_answer.answer_metadata or {})
                if retry_existing_answer
                else {}
            )
            retry_metadata, _ = merge_statement_answer_metadata(
                existing_metadata=retry_existing_metadata,
                incoming_metadata=incoming_metadata,
                incoming_statement_answers=answer_data.statement_answers,
            )
            if retry_existing_answer:
                retry_existing_answer.selected_option_id = answer_data.selected_option_id
                retry_existing_answer.selected_option_ids = answer_data.selected_option_ids
                retry_existing_answer.answer_text = answer_data.answer_text
                retry_existing_answer.answer_metadata = retry_metadata
                retry_existing_answer.answered_at = fallback_timestamp
                retry_existing_answer.is_correct = None
                retry_existing_answer.points_earned = None
            else:
                self.db.add(
                    Answer(
                        session_id=session_id_value,
                        question_id=int(answer_data.question_id),
                        selected_option_id=answer_data.selected_option_id,
                        selected_option_ids=answer_data.selected_option_ids,
                        answer_text=answer_data.answer_text,
                        answer_metadata=retry_metadata,
                        answered_at=fallback_timestamp,
                        is_correct=None,
                        points_earned=None,
                    )
                )
        await self.db.commit()
        invalidate_session_answer_count_cache(session_id_value)

    async def accept_journal_events(
        self,
        sync_data: AnswerJournalSyncRequest,
    ) -> AnswerJournalSyncResponse:
        """Apply idempotent answer journal events in one transaction."""
        if len(sync_data.events) > ANSWER_JOURNAL_MAX_SYNC_EVENTS:
            raise HTTPException(
                status_code=422,
                detail=f"Maksimal {ANSWER_JOURNAL_MAX_SYNC_EVENTS} event per sinkronisasi",
            )

        result = await self.db.execute(
            select(ExamSession).where(
                ExamSession.id == sync_data.session_id,
                ExamSession.user_id == self.current_user.id,
                ExamSession.status.in_(["in_progress", "active"]),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan atau tidak aktif")

        if not sync_data.events:
            return AnswerJournalSyncResponse(
                status="ok",
                accepted=0,
                duplicates=0,
                invalid=0,
                applied_question_count=0,
                acks=[],
                server_time=datetime.now(timezone.utc),
            )

        requested_question_ids = {int(event.question_id) for event in sync_data.events}
        valid_question_result = await self.db.execute(
            select(Question.id).where(
                Question.exam_id == session.exam_id,
                Question.id.in_(requested_question_ids),
            )
        )
        valid_question_ids = {int(row[0]) for row in valid_question_result.all()}

        redis = await get_redis()
        session_id_value = int(session.id)
        event_set_key = _answer_journal_event_set_key(session_id_value)
        normalized_event_ids = [
            _normalize_answer_journal_event_id(event.event_id) for event in sync_data.events
        ]
        existing_event_ids = await self._read_existing_journal_event_ids(
            redis,
            event_set_key,
            normalized_event_ids,
            session_id_value,
        )

        accepted_events, acks, duplicate_count, invalid_count = self._classify_journal_events(
            sync_data,
            valid_question_ids,
            existing_event_ids,
        )
        if not accepted_events:
            return AnswerJournalSyncResponse(
                status="ok",
                accepted=0,
                duplicates=duplicate_count,
                invalid=invalid_count,
                applied_question_count=0,
                acks=acks,
                server_time=datetime.now(timezone.utc),
            )

        if is_runtime_answer_buffer_enabled():
            buffered_count = await AnswerRuntimeBufferService(
                self.db,
                self.current_user,
            ).accept_journal_events(sync_data, accepted_events)
            accepted_event_ids = [event_id for event_id, _ in accepted_events]
            if accepted_event_ids:
                await redis.sadd(event_set_key, *accepted_event_ids)
                await redis.expire(event_set_key, ANSWER_JOURNAL_EVENT_TTL_SECONDS)
            for event_id, event in accepted_events:
                acks.append(
                    AnswerJournalAck(
                        event_id=event_id,
                        question_id=int(event.question_id),
                        status="applied",
                    )
                )
            return AnswerJournalSyncResponse(
                status="ok",
                accepted=len(accepted_events),
                duplicates=duplicate_count,
                invalid=invalid_count,
                applied_question_count=buffered_count,
                acks=acks,
                server_time=datetime.now(timezone.utc),
            )

        latest_by_question = self._latest_journal_events_by_question(accepted_events)
        await _acquire_session_write_lock(self.db, session_id_value)
        session = await _ensure_session_in_progress_for_user(
            self.db,
            session_id=session_id_value,
            user_id=self.current_user.id,
            lock_row=True,
        )
        session_id_value = int(session.id)

        question_ids_to_apply = list(latest_by_question.keys())
        existing_answer_map = await self._load_existing_answers(session_id_value, question_ids_to_apply)
        changed_rows = self._apply_journal_answers(
            session_id_value,
            latest_by_question,
            existing_answer_map,
        )

        if changed_rows > 0:
            await self.db.commit()
            invalidate_session_answer_count_cache(session_id_value)
        else:
            await self.db.rollback()

        try:
            accepted_event_ids = [event_id for event_id, _ in accepted_events]
            if accepted_event_ids:
                await redis.sadd(event_set_key, *accepted_event_ids)
                await redis.expire(event_set_key, ANSWER_JOURNAL_EVENT_TTL_SECONDS)
        except Exception as exc:
            logger.warning(
                "ANSWER-JOURNAL | Session %s | failed writing idempotency set: %s",
                session_id_value,
                str(exc),
            )

        await update_session_answers(
            session_id_value,
            {str(question_id): True for question_id in question_ids_to_apply},
        )
        await self._update_runtime_answered_count(
            session_id_value,
            question_ids_to_apply,
            log_prefix="ANSWER-JOURNAL",
        )

        for event_id, event in accepted_events:
            acks.append(
                AnswerJournalAck(
                    event_id=event_id,
                    question_id=int(event.question_id),
                    status="applied",
                )
            )

        return AnswerJournalSyncResponse(
            status="ok",
            accepted=len(accepted_events),
            duplicates=duplicate_count,
            invalid=invalid_count,
            applied_question_count=len(question_ids_to_apply),
            acks=acks,
            server_time=datetime.now(timezone.utc),
        )

    async def _read_existing_journal_event_ids(
        self,
        redis: Any,
        event_set_key: str,
        normalized_event_ids: List[str],
        session_id_value: int,
    ) -> Set[str]:
        existing_event_ids: Set[str] = set()
        try:
            if normalized_event_ids:
                pipeline = redis.pipeline()
                for event_id in normalized_event_ids:
                    pipeline.sismember(event_set_key, event_id)
                existing_flags = await pipeline.execute()
                existing_event_ids = {
                    event_id
                    for event_id, flag in zip(normalized_event_ids, existing_flags)
                    if bool(flag)
                }
        except Exception as exc:
            logger.warning(
                "ANSWER-JOURNAL | Session %s | failed checking Redis idempotency set: %s",
                session_id_value,
                str(exc),
            )
        return existing_event_ids

    def _classify_journal_events(
        self,
        sync_data: AnswerJournalSyncRequest,
        valid_question_ids: Set[int],
        existing_event_ids: Set[str],
    ) -> Tuple[List[Tuple[str, Any]], List[AnswerJournalAck], int, int]:
        ordered_events = sorted(
            sync_data.events,
            key=lambda item: (int(item.sequence), int(item.local_timestamp_ms)),
        )
        seen_in_payload: Set[str] = set()
        accepted_events: List[Tuple[str, Any]] = []
        acks: List[AnswerJournalAck] = []
        duplicate_count = 0
        invalid_count = 0

        for event in ordered_events:
            event_id = _normalize_answer_journal_event_id(event.event_id)
            question_id = int(event.question_id)
            if not _is_valid_answer_journal_event_id(event_id):
                invalid_count += 1
                acks.append(AnswerJournalAck(event_id=event_id, question_id=question_id, status="invalid", reason="invalid_event_id"))
                continue
            if event_id in seen_in_payload:
                duplicate_count += 1
                acks.append(AnswerJournalAck(event_id=event_id, question_id=question_id, status="duplicate", reason="duplicate_in_payload"))
                continue
            seen_in_payload.add(event_id)
            if question_id not in valid_question_ids:
                invalid_count += 1
                acks.append(AnswerJournalAck(event_id=event_id, question_id=question_id, status="invalid", reason="invalid_question_id"))
                continue
            if event_id in existing_event_ids:
                duplicate_count += 1
                acks.append(AnswerJournalAck(event_id=event_id, question_id=question_id, status="duplicate", reason="already_acked"))
                continue
            accepted_events.append((event_id, event))
        return accepted_events, acks, duplicate_count, invalid_count

    def _latest_journal_events_by_question(self, accepted_events: List[Tuple[str, Any]]) -> Dict[int, Tuple[str, Any]]:
        latest_by_question: Dict[int, Tuple[str, Any]] = {}
        for event_id, event in accepted_events:
            question_id = int(event.question_id)
            current = latest_by_question.get(question_id)
            if current is None:
                latest_by_question[question_id] = (event_id, event)
                continue
            _, current_event = current
            if (int(event.sequence), int(event.local_timestamp_ms)) >= (
                int(current_event.sequence),
                int(current_event.local_timestamp_ms),
            ):
                latest_by_question[question_id] = (event_id, event)
        return latest_by_question

    async def _load_existing_answers(self, session_id_value: int, question_ids: List[int]) -> Dict[int, Answer]:
        if not question_ids:
            return {}
        existing_result = await self.db.execute(
            select(Answer).where(
                Answer.session_id == session_id_value,
                Answer.question_id.in_(question_ids),
            )
        )
        return {int(answer.question_id): answer for answer in existing_result.scalars().all()}

    def _apply_journal_answers(
        self,
        session_id_value: int,
        latest_by_question: Dict[int, Tuple[str, Any]],
        existing_answer_map: Dict[int, Answer],
    ) -> int:
        now_utc = datetime.now(timezone.utc)
        changed_rows = 0
        for question_id, (event_id, event) in latest_by_question.items():
            existing_answer = existing_answer_map.get(question_id)
            incoming_metadata = dict(event.answer_metadata or {})
            incoming_metadata["client_event_id"] = event_id
            incoming_metadata["client_sequence"] = int(event.sequence)
            incoming_metadata["client_local_timestamp_ms"] = int(event.local_timestamp_ms)
            incoming_metadata["sync_source"] = "answer_journal_v1"
            existing_metadata = dict(existing_answer.answer_metadata or {}) if existing_answer else {}
            final_metadata, _ = merge_statement_answer_metadata(
                existing_metadata=existing_metadata,
                incoming_metadata=incoming_metadata,
                incoming_statement_answers=event.statement_answers,
            )
            if existing_answer:
                has_changed = (
                    existing_answer.selected_option_id != event.selected_option_id
                    or existing_answer.selected_option_ids != event.selected_option_ids
                    or existing_answer.answer_text != event.answer_text
                    or dict(existing_answer.answer_metadata or {}) != final_metadata
                )
                if not has_changed:
                    continue
                existing_answer.selected_option_id = event.selected_option_id
                existing_answer.selected_option_ids = event.selected_option_ids
                existing_answer.answer_text = event.answer_text
                existing_answer.answer_metadata = final_metadata
                existing_answer.answered_at = now_utc
                existing_answer.is_correct = None
                existing_answer.points_earned = None
                changed_rows += 1
            else:
                self.db.add(
                    Answer(
                        session_id=session_id_value,
                        question_id=question_id,
                        selected_option_id=event.selected_option_id,
                        selected_option_ids=event.selected_option_ids,
                        answer_text=event.answer_text,
                        answer_metadata=final_metadata,
                        answered_at=now_utc,
                        is_correct=None,
                        points_earned=None,
                    )
                )
                changed_rows += 1
        return changed_rows

    async def _update_runtime_answered_count(
        self,
        session_id_value: int,
        question_ids: List[int],
        *,
        log_prefix: str,
    ) -> None:
        try:
            answered_count_runtime = await add_answered_questions_and_count(
                session_id_value,
                question_ids,
            )
            if answered_count_runtime is not None:
                await update_runtime_snapshot_answered_count(
                    session_id_value,
                    expected_user_id=self.current_user.id,
                    answered_count=answered_count_runtime,
                    mark_stale=False,
                    status="in_progress",
                )
        except Exception as runtime_exc:
            logger.debug(
                "%s | session=%s | runtime answered_count update skipped: %s",
                log_prefix,
                session_id_value,
                str(runtime_exc),
            )


def get_answer_sync_service(db: AsyncSession, current_user: Any) -> AnswerSyncService:
    return AnswerSyncService(db=db, current_user=current_user)
