"""
Exam management API endpoints.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Set, Tuple
import asyncio
import csv
import html
import io
import secrets
import logging
import random
import hashlib  # Added for stable seeding
import hmac
import re
import time
from types import SimpleNamespace
import sqlalchemy
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, or_, and_, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload, joinedload, noload
from pydantic import BaseModel
import pytz
import uuid

from app.database import get_db, get_db_read
from app.models.user import User
from app.models.exam import Exam
from app.models.exam_template import ExamTemplate
from app.models.question import Question, QuestionOption
from app.models.session import ExamSession, Answer, ExamLog
from app.models.activity_log import UserActivityLog
from app.schemas.exam import (
    ExamCreate, ExamResponse, ExamListResponse,
    QuestionResponse, QuestionOptionResponse,
    ExamStartResponse, ExamAnalytics
)
from app.schemas.answer import (
    AnswerSubmit, AnswerResponse,
    ExamSubmitRequest, ExamSubmitResponse, ViolationLog, ViolationResponse,
    SessionStatusResponse,
)
from app.core.security import (
    AuthenticatedUser,
    get_current_user,
    get_current_user_hot_path,
    get_current_teacher,
    create_session_poll_token,
    is_pengawas_user,
)
from app.middleware.seb_validation import validate_seb_headers, get_client_info
from app.core.redis_pubsub import (
    publish_message, store_session_data, get_session_data,
    update_session_answers, get_redis, update_session_activity
)
from app.core.client_ip import get_client_ip
from app.core.answer_review_helpers import (
    QUESTION_TYPE_LABELS,
    build_option_map as _build_option_map,
    coerce_bool as _coerce_bool,
    resolve_question_statements as _resolve_question_statements,
    resolve_statement_keys as _resolve_statement_keys,
    status_from_answer as _status_from_answer,
)
from app.core.exam_access_policy import (
    ensure_exam_participant_access as _ensure_exam_participant_access,
    is_exam_participant_role as _is_exam_participant_role,
    participant_has_exam_access as _participant_has_exam_access,
)
from app.core.exam_answer_validation import (
    get_question_validation_payload_cached as _get_question_validation_payload_cached,
    validate_answer_with_cached_payload as _validate_answer_with_cached_payload,
)
from app.core.exam_results_cache import (
    build_exam_results_cache_key as _build_exam_results_cache_key,
    build_exam_results_viewer_scope as _build_exam_results_viewer_scope,
    get_cached_exam_results as _get_cached_exam_results,
    invalidate_exam_results_cache as _invalidate_exam_results_cache,
    set_cached_exam_results as _set_cached_exam_results,
)
from app.core.exam_runtime_cache import (
    answer_has_meaningful_content_clause as _answer_has_meaningful_content_clause,
    get_exam_question_count_cached as _get_exam_question_count_cached,
    get_session_answer_count_cached as _get_session_answer_count_cached,
    get_user_display_name_cached as _get_user_display_name_cached,
    invalidate_session_answer_count_cache as _invalidate_session_answer_count_cache,
    should_publish_progress_update as _should_publish_progress_update,
    should_update_session_activity as _should_update_session_activity,
)
from app.core.exam_runtime_state import (
    add_answered_questions_and_count as _add_answered_questions_and_count,
    get_answered_count_from_set as _get_answered_count_from_set,
    update_runtime_snapshot_answered_count as _update_runtime_snapshot_answered_count,
)
from app.core.monitoring_delta import publish_monitoring_delta
from app.core.exam_session_helpers import (
    calculate_effective_timer,
    merge_statement_answer_metadata,
    parse_iso_datetime_utc,
    resolve_timer_context,
    safe_int,
)
from app.core.roles import (
    ROLE_ADMIN,
    ROLE_DEVELOPER,
    is_developer_exam_hidden_for_viewer,
    is_developer_role,
    normalize_role,
)
from app.core.violation_metadata import (
    canonical_violation_event_type,
    get_violation_metadata,
    get_violation_warning_message,
    strip_violation_prefix,
)
from app.core.violation_scoring import (
    is_violation_event_disabled,
    should_count_violation_for_score,
)
from app.core.session_recovery import evaluate_session_recovery
from app.config import settings
from app.core.feature_flags import require_feature_enabled
from app.core.rate_limiter import RateLimiters, check_rate_limit
from app.services.exam_service import ExamService
from app.services.exam_submission_service import finalize_exam_session_submission
from app.services.final_submit_service import get_final_submit_service
from app.services.violation_event_service import enqueue_violation_event
from app.tasks.answer_processor import drain_answer_queue, enqueue_answer_payload
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/exams", tags=["Exams"])
public_router = APIRouter(prefix="/api/exams", tags=["Exams"])

# Admin Audit Logging Helper
async def log_admin_action(
    db: AsyncSession,
    admin_user: User,
    action: str,
    target_type: str,
    target_id: int,
    target_name: str,
    details: Optional[Dict[str, Any]] = None
):

    """Log admin actions for audit trail."""
    if normalize_role(admin_user.role) in {ROLE_ADMIN, ROLE_DEVELOPER}:
        log_entry = UserActivityLog(
            user_id=admin_user.id,
            event_type=f"admin_{action}",
            event_data={
                "admin_username": admin_user.username,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "target_name": target_name,
                "details": details or {}
            }
        )
        db.add(log_entry)
        await db.commit()
        logger.warning(f"🚨 ADMIN ACTION: {admin_user.username} {action} {target_type} '{target_name}' (ID: {target_id})")


EXAM_CRITICAL_METADATA_FIELDS = (
    "start_time",
    "end_time",
    "allowed_classes",
    "allowed_students",
)

EXAM_AUDIT_FIELDS = (
    "title",
    "description",
    "duration_minutes",
    "start_time",
    "end_time",
    "passing_score",
    "max_attempts",
    "shuffle_questions",
    "shuffle_options",
    "show_results",
    "allow_review",
    "is_published",
    "subject",
    "exam_type",
    "academic_year",
    "show_teacher_name",
    "allowed_classes",
    "allowed_students",
)


def _normalize_csv_restriction_for_compare(value: Optional[str]) -> Tuple[str, ...]:
    if not value:
        return tuple()
    return tuple(sorted({part.strip().upper() for part in value.split(",") if part.strip()}))


def _datetime_for_compare(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=timezone.utc)
    else:
        normalized = value.astimezone(timezone.utc)
    return normalized.replace(microsecond=0)


def _exam_datetime_changed(current_value: Optional[datetime], new_value: Optional[datetime]) -> bool:
    return _datetime_for_compare(current_value) != _datetime_for_compare(new_value)


def _exam_critical_metadata_changes(exam: Exam, exam_data: ExamCreate) -> List[str]:
    changed: List[str] = []
    if _exam_datetime_changed(exam.start_time, exam_data.start_time):
        changed.append("start_time")
    if _exam_datetime_changed(exam.end_time, exam_data.end_time):
        changed.append("end_time")
    if _normalize_csv_restriction_for_compare(exam.allowed_classes) != _normalize_csv_restriction_for_compare(exam_data.allowed_classes):
        changed.append("allowed_classes")
    if _normalize_csv_restriction_for_compare(exam.allowed_students) != _normalize_csv_restriction_for_compare(exam_data.allowed_students):
        changed.append("allowed_students")
    return changed


def _json_safe_audit_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_audit_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe_audit_value(item) for key, item in value.items()}
    return str(value)


def _collect_exam_update_changes(original_values: Dict[str, Any], exam_data: ExamCreate) -> Dict[str, Dict[str, Any]]:
    changes: Dict[str, Dict[str, Any]] = {}
    for field in EXAM_AUDIT_FIELDS:
        old_value = original_values.get(field)
        new_value = getattr(exam_data, field)
        if field in {"start_time", "end_time"}:
            changed = _exam_datetime_changed(old_value, new_value)
        elif field in {"allowed_classes", "allowed_students"}:
            changed = _normalize_csv_restriction_for_compare(old_value) != _normalize_csv_restriction_for_compare(new_value)
        else:
            changed = _json_safe_audit_value(old_value) != _json_safe_audit_value(new_value)
        if changed:
            changes[field] = {
                "old": _json_safe_audit_value(old_value),
                "new": _json_safe_audit_value(new_value),
            }
    return changes


def _student_summary_entry(row: Any) -> Dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": row["username"] or "",
        "full_name": row["full_name"] or row["username"] or "",
        "student_class": row["student_class"] or "",
    }


def _format_wib_datetime(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    wib = pytz.timezone("Asia/Jakarta")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(wib).strftime("%Y-%m-%d %H:%M:%S WIB")

def get_exam_service(db: AsyncSession = Depends(get_db)) -> ExamService:
    return ExamService(db)

def get_exam_service_read(db: AsyncSession = Depends(get_db_read)) -> ExamService:
    """Service using Read Replica"""
    return ExamService(db)


async def _get_exam_creator_role(db: AsyncSession, creator_id: Optional[int]) -> Optional[str]:
    if not creator_id:
        return None

    creator_role_result = await db.execute(
        select(User.role).where(User.id == creator_id)
    )
    return creator_role_result.scalar_one_or_none()


def _raise_hidden_exam_error() -> None:
    raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")


def _enforce_developer_exam_visibility(current_user: User, exam_creator_role: Optional[str]) -> None:
    if is_developer_exam_hidden_for_viewer(current_user.role, exam_creator_role):
        _raise_hidden_exam_error()


async def _enforce_exam_owner_or_admin_access(
    db: AsyncSession,
    current_user: User,
    exam_creator_id: int,
    *,
    allow_pengawas: bool = False,
) -> str:
    creator_role = await _get_exam_creator_role(db, exam_creator_id)
    _enforce_developer_exam_visibility(current_user, creator_role)

    if exam_creator_id == current_user.id:
        return str(creator_role or "")

    if bool(getattr(current_user, "is_admin", False)):
        return str(creator_role or "")

    if allow_pengawas and is_pengawas_user(current_user):
        return str(creator_role or "")

    raise HTTPException(status_code=403, detail="Tidak memiliki akses")


def _pick_latest_scored_exam_session_per_user(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Pick one session row per user for exam result views.

    Selection rule:
    1. Prefer latest row with non-null score for each user.
    2. Fallback to the user's latest row when all scores are null.
    """
    latest_any: Dict[int, Dict[str, Any]] = {}
    latest_scored: Dict[int, Dict[str, Any]] = {}

    for row in rows:
        user_id = int(row["user_id"])
        if user_id not in latest_any:
            latest_any[user_id] = row
        if row.get("score") is not None and user_id not in latest_scored:
            latest_scored[user_id] = row

    selected_rows: List[Dict[str, Any]] = []
    for user_id, any_row in latest_any.items():
        selected_rows.append(latest_scored.get(user_id, any_row))

    min_datetime_utc = datetime.min.replace(tzinfo=timezone.utc)
    selected_rows.sort(
        key=lambda row: (
            row.get("end_time") is not None,
            row.get("end_time") or min_datetime_utc,
            int(row.get("session_id") or 0),
        ),
        reverse=True,
    )
    return selected_rows


EXAM_START_VALIDATION_CACHE_PREFIX = "cache:exam-start-validation:v1"
EXAM_START_VALIDATION_CACHE_TTL_SECONDS = 120
EXAM_START_VALIDATION_LOCAL_CACHE_TTL_SECONDS = 300
SESSION_POLL_TOKEN_EXPIRES_MINUTES = 15
SESSION_WRITE_LOCK_NAMESPACE = 48102
ANSWER_JOURNAL_EVENT_TTL_SECONDS = 48 * 60 * 60
ANSWER_JOURNAL_MAX_SYNC_EVENTS = 250
OFFLINE_PACKAGE_TTL_SECONDS = 30 * 60
ANSWER_JOURNAL_EVENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9:_-]{8,118}$")

_exam_start_validation_local_cache: Dict[int, float] = {}


def _answer_write_mode() -> str:
    mode = str(getattr(settings, "answer_write_mode", "direct") or "direct").strip().lower()
    if mode == "queue":
        return "queue"
    return "direct"


async def _publish_exam_monitor_event(exam_id: int, payload: Dict[str, Any]) -> None:
    await publish_message(f"exam_monitor_{exam_id}", payload)
    try:
        await publish_monitoring_delta(
            exam_id=exam_id,
            event_type=str(payload.get("type") or "event"),
            payload=payload,
        )
    except Exception as delta_exc:
        logger.debug("Failed to mirror monitor event to delta stream: %s", str(delta_exc))


def _answer_journal_event_set_key(session_id: int) -> str:
    return f"exam:answer-journal:v1:session:{session_id}:event-ids"


def _normalize_answer_journal_event_id(raw_event_id: str) -> str:
    return str(raw_event_id or "").strip().lower()


def _is_valid_answer_journal_event_id(event_id: str) -> bool:
    return bool(ANSWER_JOURNAL_EVENT_ID_RE.match(event_id))


def _sign_offline_package_payload(session_id: int, payload: Dict[str, Any]) -> str:
    secret_value = (
        (settings.secret_key or "").strip()
        or (settings.jwt_secret_key or "").strip()
        or "exam-offline-package-fallback-secret"
    )
    secret = secret_value.encode("utf-8")
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    payload_digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    signature_input = f"{session_id}:{payload_digest}".encode("utf-8")
    return hmac.new(secret, signature_input, hashlib.sha256).hexdigest()


def _build_exam_start_validation_cache_key(exam_id: int) -> str:
    return f"{EXAM_START_VALIDATION_CACHE_PREFIX}:{exam_id}:options-ok"


async def _acquire_session_write_lock(db: AsyncSession, session_id: int) -> None:
    """
    Serialize all mutating writes for the same exam session.

    This prevents answer writes from racing against final submission and avoids
    post-submit mutations under concurrent retry bursts.
    """
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :session_id)"),
        {
            "namespace": SESSION_WRITE_LOCK_NAMESPACE,
            "session_id": session_id,
        },
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



async def _ensure_exam_start_option_integrity(db: AsyncSession, exam_id: int) -> None:
    """
    Ensure option-based questions are renderable before exam start.
    Uses short Redis cache to avoid repeating heavy validation on burst starts.
    """
    now_monotonic = time.monotonic()
    local_cached_until = _exam_start_validation_local_cache.get(exam_id, 0.0)
    if now_monotonic < local_cached_until:
        return

    cache_key = _build_exam_start_validation_cache_key(exam_id)
    lock_key = f"{cache_key}:lock"
    redis = None
    validation_lock_token: Optional[str] = None
    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached == "1":
            _exam_start_validation_local_cache[exam_id] = (
                now_monotonic + EXAM_START_VALIDATION_LOCAL_CACHE_TTL_SECONDS
            )
            return

        validation_lock_token = uuid.uuid4().hex
        acquired = await redis.set(lock_key, validation_lock_token, ex=15, nx=True)
        if not acquired:
            wait_deadline = time.monotonic() + 12.0
            while time.monotonic() < wait_deadline:
                cached = await redis.get(cache_key)
                if cached == "1":
                    _exam_start_validation_local_cache[exam_id] = (
                        time.monotonic() + EXAM_START_VALIDATION_LOCAL_CACHE_TTL_SECONDS
                    )
                    return
                await asyncio.sleep(0.05)

            logger.warning(
                "Exam start validation lock wait expired for exam %s; skip duplicate validation on hot path",
                exam_id,
            )
            return
    except Exception as exc:
        logger.warning(
            "Failed reading exam start validation cache for exam %s: %s",
            exam_id,
            str(exc),
        )

    orphaned_check = await db.execute(
        select(Question.id, Question.question_text, Question.question_type)
        .outerjoin(QuestionOption, Question.id == QuestionOption.question_id)
        .where(
            Question.exam_id == exam_id,
            QuestionOption.id == None,
            or_(
                Question.question_type.in_(["multiple_choice", "true_false"]),
                and_(
                    Question.question_type == "multiple_choice_complex",
                    func.coalesce(Question.pgk_type, "checkbox") != "table_validation",
                ),
            ),
        )
        .group_by(Question.id, Question.question_text, Question.question_type)
    )
    orphaned_questions = orphaned_check.all()
    if orphaned_questions:
        orphaned_ids = [str(q[0]) for q in orphaned_questions]
        logger.error(
            "EXAM_START | INVALID EXAM %s | Questions with 0 options: %s",
            exam_id,
            orphaned_ids,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                f"Ujian memiliki {len(orphaned_questions)} soal pilihan ganda tanpa pilihan jawaban. "
                f"Tidak bisa dimulai. Silakan hubungi pengawas atau administrator."
            ),
        )

    _exam_start_validation_local_cache[exam_id] = (
        time.monotonic() + EXAM_START_VALIDATION_LOCAL_CACHE_TTL_SECONDS
    )

    if redis is not None:
        try:
            await redis.set(cache_key, "1", ex=EXAM_START_VALIDATION_CACHE_TTL_SECONDS)
        except Exception as exc:
            logger.warning(
                "Failed writing exam start validation cache for exam %s: %s",
                exam_id,
                str(exc),
            )
        finally:
            if validation_lock_token is not None:
                try:
                    current_lock = await redis.get(lock_key)
                    if current_lock == validation_lock_token:
                        await redis.delete(lock_key)
                except Exception as exc:
                    logger.warning(
                        "Failed releasing exam start validation lock for exam %s: %s",
                        exam_id,
                        str(exc),
                    )


def _is_placeholder_question(settings_payload: Optional[Dict[str, Any]]) -> bool:
    settings_dict = settings_payload or {}
    return bool(settings_dict.get("is_placeholder", False))


def _can_shuffle_placeholder_options(
    settings_payload: Optional[Dict[str, Any]],
    *,
    has_image: bool = False
) -> bool:
    """Allow placeholder shuffle only for non-image sources."""
    settings_dict = settings_payload or {}
    if not _is_placeholder_question(settings_dict):
        return False

    placeholder_source = str(settings_dict.get("placeholder_source") or "").strip().lower()
    allow_flag = bool(settings_dict.get("allow_placeholder_shuffle", False))
    if has_image or placeholder_source == "image":
        # Mode 2 is disabled globally; image-based placeholders stay fixed.
        return False

    return allow_flag


def _stable_shuffle_with_seed(items: List[Any], seed_str: str) -> List[Any]:
    """
    Deterministic shuffle with a guaranteed order change when possible.
    If RNG returns original order, rotate deterministically to enforce variation.
    """
    original_items = list(items)
    if len(original_items) < 2:
        return original_items

    seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    shuffled_items = list(original_items)
    rng.shuffle(shuffled_items)

    if shuffled_items == original_items:
        offset = (seed % (len(shuffled_items) - 1)) + 1
        shuffled_items = shuffled_items[offset:] + shuffled_items[:offset]

    return shuffled_items


async def _autofill_placeholder_options_for_publish(exam_id: int, db: AsyncSession) -> int:
    """
    Auto-fill A/B/C/... placeholders for option-based questions when teacher only sets answer keys.
    This keeps student rendering/scoring safe while allowing very fast question authoring.
    """
    result = await db.execute(
        select(Question)
        .options(selectinload(Question.options))
        .where(Question.exam_id == exam_id)
        .order_by(Question.order_index.asc(), Question.id.asc())
    )
    questions = result.scalars().all()

    def _has_embedded_choice_lines(raw_text: Optional[str]) -> bool:
        text = raw_text or ""
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</(p|div|li)>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        labels = {
            match.group(1).upper()
            for match in re.finditer(r"(?i)\b([A-Za-z])[.):]\s+\S+", text)
        }
        return len(labels) >= 2

    MC_MIN_OPTIONS = 3
    PGK_CHECKBOX_MIN_OPTIONS = 4
    updated_questions = 0

    for q in questions:
        settings = dict(q.question_settings or {})
        pgk_type = q.pgk_type or settings.get("pgk_type", "checkbox")
        minimum_required = (
            MC_MIN_OPTIONS
            if q.question_type == "multiple_choice"
            else PGK_CHECKBOX_MIN_OPTIONS
        )

        is_option_based = (
            q.question_type == "multiple_choice" or
            (q.question_type == "multiple_choice_complex" and pgk_type != "table_validation")
        )
        if not is_option_based or not q.options or len(q.options) < minimum_required:
            continue

        sorted_opts = sorted(q.options, key=lambda o: o.order_index)
        real_count = sum(1 for opt in sorted_opts if (opt.option_text or "").strip())
        if real_count >= minimum_required:
            continue

        has_selected_key = any(bool(opt.is_correct) for opt in sorted_opts)
        has_embedded = _has_embedded_choice_lines(q.question_text)
        has_media = bool(q.image_url)

        # Super-permissive mode: if key is selected, normalize blank options into A/B/C...
        if not has_selected_key and not has_embedded and not has_media:
            continue

        changed = False
        for idx, opt in enumerate(sorted_opts):
            if (opt.option_text or "").strip():
                continue
            letter = chr(65 + (idx % 26))
            suffix = str(idx // 26 + 1) if idx >= 26 else ""
            opt.option_text = f"{letter}{suffix}"
            changed = True

        if changed:
            settings["is_placeholder"] = True
            if has_media:
                settings["placeholder_source"] = "image"
            elif has_embedded:
                settings["placeholder_source"] = "question_text"
            else:
                settings["placeholder_source"] = "auto_no_option"
            q.question_settings = settings
            updated_questions += 1

    if updated_questions > 0:
        await db.flush()

    return updated_questions


async def _validate_questions_for_publish(exam_id: int, db: AsyncSession) -> None:
    """Validate question completeness before exam publish."""
    result = await db.execute(
        select(Question)
        .options(selectinload(Question.options))
        .where(Question.exam_id == exam_id)
        .order_by(Question.order_index.asc(), Question.id.asc())
    )
    questions = result.scalars().all()

    if not questions:
        raise HTTPException(status_code=400, detail="Ujian belum memiliki soal")

    errors: List[str] = []

    MC_MIN_OPTIONS = 3
    PGK_CHECKBOX_MIN_OPTIONS = 4

    def _is_generated_placeholder(option_text: Optional[str]) -> bool:
        normalized = (option_text or "").strip().upper()
        if not normalized:
            return False
        return bool(re.fullmatch(r"[A-Z](?:[2-9][0-9]*)?", normalized))

    def _count_real_options(options: List[QuestionOption]) -> int:
        count = 0
        for opt in options:
            text = (opt.option_text or "").strip()
            if not text:
                continue
            if _is_generated_placeholder(text):
                continue
            count += 1
        return count

    def _has_embedded_choice_lines(raw_text: Optional[str]) -> bool:
        """Detect copy-pasted options inside question text (e.g. A. ..., B. ...)."""
        text = raw_text or ""
        # Keep line boundaries when source text contains simple HTML tags.
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</(p|div|li)>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        labels = {
            match.group(1).upper()
            for match in re.finditer(r"(?i)\b([A-Za-z])[.):]\s+\S+", text)
        }
        return len(labels) >= 2

    for idx, q in enumerate(questions, 1):
        q_type = q.question_type
        settings = q.question_settings or {}
        pgk_type = q.pgk_type or settings.get("pgk_type", "checkbox")

        question_text = (q.question_text or "").strip()
        has_media = bool(q.image_url or q.video_url or q.audio_url)
        if not question_text and not has_media:
            errors.append(f"Soal No. {idx}: Pertanyaan masih kosong")

        if q_type == "multiple_choice":
            real_options_count = _count_real_options(q.options)
            has_embedded_options = _has_embedded_choice_lines(q.question_text)
            has_correct = any(opt.is_correct for opt in q.options)
            is_image_mode = bool(q.image_url)
            permissive_key_only_mode = has_correct and not is_image_mode and not has_embedded_options

            if real_options_count < MC_MIN_OPTIONS and not is_image_mode and not has_embedded_options and not permissive_key_only_mode:
                errors.append(
                    f"Soal No. {idx} (Pilihan Ganda): Minimal harus ada {MC_MIN_OPTIONS} opsi jawaban"
                )

            if not has_correct:
                errors.append(
                    f"Soal No. {idx} (Pilihan Ganda): Kunci jawaban belum dipilih"
                )

        elif q_type == "true_false":
            if len(q.options) < 2:
                errors.append(
                    f"Soal No. {idx} (Benar/Salah): Opsi Benar dan Salah belum lengkap"
                )
            if not any(opt.is_correct for opt in q.options):
                errors.append(
                    f"Soal No. {idx} (Benar/Salah): Kunci jawaban belum dipilih"
                )

        elif q_type == "short_answer":
            require_manual = bool(settings.get("require_manual_grading", False))
            acceptable_answers = settings.get("acceptable_answers", []) or []
            first_key = (acceptable_answers[0] if acceptable_answers else "").strip()
            if not require_manual and not first_key:
                errors.append(
                    f"Soal No. {idx} (Isian Singkat): Kunci jawaban belum diisi"
                )

        elif q_type == "multiple_choice_complex":
            if not q.image_url and not (q.stimulus or "").strip():
                errors.append(
                    f"Soal No. {idx} (PG Kompleks): Stimulus/bacaan wajib diisi"
                )

            if pgk_type == "table_validation":
                statements = settings.get("statements", []) or []
                statement_answers = settings.get("statement_answers", []) or []
                valid_statements = [s for s in statements if (s or "").strip()]
                has_image_mode = bool(q.image_url)

                if not has_image_mode and len(valid_statements) < 2:
                    errors.append(
                        f"Soal No. {idx} (PG Kompleks): Minimal harus ada 2 pernyataan"
                    )
                elif has_image_mode and len(valid_statements) < 2 and len(statement_answers) < 2:
                    errors.append(
                        f"Soal No. {idx} (PG Kompleks): Minimal harus ada 2 pernyataan"
                    )

                required_answers_count = len(valid_statements)
                if has_image_mode:
                    required_answers_count = max(required_answers_count, 2)

                if len(statement_answers) < required_answers_count:
                    errors.append(
                        f"Soal No. {idx} (PG Kompleks): Jawaban Benar/Salah pernyataan belum lengkap"
                    )
            else:
                real_options_count = _count_real_options(q.options)
                has_embedded_options = _has_embedded_choice_lines(q.question_text)
                is_image_mode = bool(q.image_url)
                correct_count = sum(1 for opt in q.options if opt.is_correct)
                permissive_key_only_mode = correct_count >= 2 and not is_image_mode and not has_embedded_options

                if real_options_count < PGK_CHECKBOX_MIN_OPTIONS and not is_image_mode and not has_embedded_options and not permissive_key_only_mode:
                    errors.append(
                        f"Soal No. {idx} (PG Kompleks): Minimal harus ada {PGK_CHECKBOX_MIN_OPTIONS} opsi jawaban"
                    )

                if correct_count < 2:
                    errors.append(
                        f"Soal No. {idx} (PG Kompleks): Minimal 2 kunci jawaban harus dicentang"
                    )

    if errors:
        bullet_list = "\n".join(f"- {item}" for item in errors)
        raise HTTPException(
            status_code=400,
            detail=(
                "Ujian belum siap dipublish:\n"
                f"{bullet_list}\n"
                "Silakan lengkapi soal-soal tersebut terlebih dahulu."
            )
        )


# ============== PUBLIC ENDPOINTS ==============

@router.get("", response_model=ExamListResponse)
async def list_exams(
    skip: int = 0,
    limit: int = 10000,
    published_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_read)
):
    """List available exams.

    Access rules:
    - Participant roles (student + GuruPlus): Only published exams that match access policy
    - Teachers: Only their own exams
    - Pengawas (teacher+job_title pengawas): All published exams (monitoring lane)
    - Admins: All exams (published and drafts)
    """
    # Keep list endpoint lightweight: no heavy relationship loading.
    query = select(Exam).options(
        noload("*"),
        joinedload(Exam.creator).noload("*"),
        noload(Exam.questions),
        noload(Exam.sessions),
        noload(Exam.schedules),
    )

    # Always exclude soft-deleted exams
    query = query.where(Exam.is_deleted == False)

    if _is_exam_participant_role(current_user.role):
        # Participant roles only see published exams
        query = query.where(Exam.is_published == True)
    elif current_user.role == "teacher":
        query = query.where(Exam.creator.has(User.role != ROLE_DEVELOPER))
        if is_pengawas_user(current_user):
            # Pengawas is monitor-only: never expose drafts, but must see all published exams.
            query = query.where(Exam.is_published == True)
        else:
            # Teachers see ONLY their own exams (published and drafts)
            query = query.where(Exam.creator_id == current_user.id)
            if published_only:
                query = query.where(Exam.is_published == True)
    elif current_user.role in {"admin", ROLE_DEVELOPER}:
        if current_user.role == "admin":
            query = query.where(Exam.creator.has(User.role != ROLE_DEVELOPER))
        # Admin/developer sees everything
        if published_only:
            query = query.where(Exam.is_published == True)
        # If published_only=False, show all

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    raw_exams = result.scalars().all()

    # Batch question counts to avoid per-exam lazy loads.
    question_count_map: Dict[int, int] = {}
    exam_ids = [exam.id for exam in raw_exams]
    if exam_ids:
        count_rows = await db.execute(
            select(Question.exam_id, func.count(Question.id))
            .where(Question.exam_id.in_(exam_ids))
            .group_by(Question.exam_id)
        )
        question_count_map = {exam_id: total for exam_id, total in count_rows.all()}

    for exam in raw_exams:
        setattr(exam, "_question_count", int(question_count_map.get(exam.id, 0)))

    # Post-query filtering for participant roles based on class/student restriction.
    exams = []
    if _is_exam_participant_role(current_user.role):
        for exam in raw_exams:
            creator_role = getattr(getattr(exam, "creator", None), "role", None)
            if _participant_has_exam_access(
                exam,
                current_user,
                exam_creator_role=creator_role,
            ):
                exams.append(exam)
    else:
        exams = raw_exams

    # Count total with same role filters (exclude soft-deleted exams).
    if _is_exam_participant_role(current_user.role):
        total = len(exams)
    else:
        count_query = select(func.count(Exam.id)).where(Exam.is_deleted == False)
        if current_user.role == "teacher":
            if is_pengawas_user(current_user):
                count_query = count_query.where(Exam.creator.has(User.role != ROLE_DEVELOPER))
                count_query = count_query.where(Exam.is_published == True)
            else:
                count_query = count_query.where(Exam.creator_id == current_user.id)
                if published_only:
                    count_query = count_query.where(Exam.is_published == True)
        elif current_user.role in {"admin", ROLE_DEVELOPER}:
            if current_user.role == "admin":
                count_query = count_query.where(Exam.creator.has(User.role != ROLE_DEVELOPER))
            if published_only:
                count_query = count_query.where(Exam.is_published == True)

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

    return ExamListResponse(
        exams=[ExamResponse.from_orm_with_wib(exam) for exam in exams],
        total=total
    )


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_read)
):
    """Get exam details."""
    question_count_expr = (
        select(func.count(Question.id))
        .where(Question.exam_id == Exam.id)
        .scalar_subquery()
    )

    result = await db.execute(
        select(
            Exam.id,
            Exam.title,
            Exam.description,
            Exam.creator_id,
            Exam.duration_minutes,
            Exam.start_time,
            Exam.end_time,
            Exam.passing_score,
            Exam.max_attempts,
            Exam.shuffle_questions,
            Exam.shuffle_options,
            Exam.show_results,
            Exam.allow_review,
            Exam.is_published,
            Exam.access_token,
            Exam.subject,
            Exam.exam_type,
            Exam.academic_year,
            Exam.show_teacher_name,
            Exam.builder_settings,
            Exam.allowed_classes,
            Exam.allowed_students,
            Exam.created_at,
            User.full_name.label("teacher_name"),
            User.role.label("creator_role"),
            func.coalesce(question_count_expr, 0).label("question_count"),
        )
        .join(User, User.id == Exam.creator_id)
        .where(Exam.id == exam_id, Exam.is_deleted == False)
    )
    exam = result.one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    if _is_exam_participant_role(current_user.role):
        if not exam.is_published:
            raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")
        _ensure_exam_participant_access(
            SimpleNamespace(
                allowed_students=exam.allowed_students,
                allowed_classes=exam.allowed_classes,
            ),
            current_user,
            exam_creator_role=exam.creator_role,
        )
    else:
        _enforce_developer_exam_visibility(current_user, exam.creator_role)

    # 🆕 FIX #4: Standardized permission check (admin bypass)
    if (
        exam.creator_id != current_user.id
        and not current_user.is_admin
        and not is_pengawas_user(current_user)
    ):
        raise HTTPException(status_code=403, detail="Tidak memiliki akses ke ujian ini")

    def format_wib(dt):
        if dt is None:
            return ""
        if dt.tzinfo is None:
            return dt.strftime('%d %B %Y %H:%M WIB')
        wib = pytz.timezone('Asia/Jakarta')
        return dt.astimezone(wib).strftime('%d %B %Y %H:%M WIB')

    return ExamResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        creator_id=exam.creator_id,
        duration_minutes=exam.duration_minutes,
        start_time=exam.start_time,
        end_time=exam.end_time,
        start_time_wib=format_wib(exam.start_time),
        end_time_wib=format_wib(exam.end_time),
        passing_score=exam.passing_score,
        max_attempts=exam.max_attempts,
        shuffle_questions=exam.shuffle_questions,
        shuffle_options=exam.shuffle_options,
        show_results=exam.show_results,
        allow_review=exam.allow_review,
        is_published=exam.is_published,
        access_token=exam.access_token,
        subject=exam.subject,
        exam_type=exam.exam_type,
        academic_year=exam.academic_year,
        show_teacher_name=exam.show_teacher_name if exam.show_teacher_name is not None else True,
        builder_settings=exam.builder_settings or {},
        teacher_name=exam.teacher_name,
        allowed_classes=exam.allowed_classes,
        allowed_students=exam.allowed_students,
        question_count=int(exam.question_count or 0),
        created_at=exam.created_at,
    )


# ============== TEACHER EXAM MANAGEMENT ==============

@router.post("", response_model=ExamResponse, status_code=201)
async def create_exam(
    exam_data: ExamCreate,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Create a new exam (Teacher/Admin only)."""
    # 1. Validate times
    if exam_data.end_time <= exam_data.start_time:
        raise HTTPException(status_code=400, detail="Waktu selesai harus setelah waktu mulai")

    # 2. Create Exam with Unique Token Retry
    for _ in range(5): # Retry up to 5 times
        try:
            token = secrets.token_hex(3).upper()

            new_exam = Exam(
                title=exam_data.title,
                description=exam_data.description,
                creator_id=current_user.id,
                duration_minutes=exam_data.duration_minutes,
                start_time=exam_data.start_time,
                end_time=exam_data.end_time,
                passing_score=exam_data.passing_score,
                max_attempts=exam_data.max_attempts,
                shuffle_questions=exam_data.shuffle_questions,
                shuffle_options=exam_data.shuffle_options,
                show_results=exam_data.show_results,
                allow_review=exam_data.allow_review,
                is_published=exam_data.is_published,
                subject=exam_data.subject,
                exam_type=exam_data.exam_type,
                academic_year=exam_data.academic_year,
                show_teacher_name=exam_data.show_teacher_name,
                builder_settings=exam_data.builder_settings or {},
                allowed_classes=exam_data.allowed_classes,
                allowed_students=exam_data.allowed_students,
                # Secure Token Generation
                access_token=token,
                seb_config_key=secrets.token_urlsafe(32),
                seb_browser_exam_key=secrets.token_urlsafe(32)
            )

            db.add(new_exam)
            await db.commit()
            await db.refresh(new_exam)

            return ExamResponse.from_orm_with_wib(new_exam)

        except sqlalchemy.exc.IntegrityError:
            await db.rollback()
            continue # Try next token

    raise HTTPException(status_code=500, detail="Gagal generate token ujian yang unik. Silakan coba lagi.")


@router.put("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: int,
    exam_data: ExamCreate,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Update exam details."""
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    # Check permissions
    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
    )

    # Update fields
    if exam_data.end_time <= exam_data.start_time:
        raise HTTPException(status_code=400, detail="Waktu selesai harus setelah waktu mulai")

    original_values = {field: getattr(exam, field) for field in EXAM_AUDIT_FIELDS}
    critical_changes = _exam_critical_metadata_changes(exam, exam_data)
    if critical_changes:
        session_count_result = await db.execute(
            select(func.count(ExamSession.id)).where(ExamSession.exam_id == exam_id)
        )
        session_count = int(session_count_result.scalar() or 0)
        if session_count > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ujian sudah memiliki sesi peserta. Perubahan jadwal atau target peserta "
                    "dikunci agar hasil historis tidak berubah konteks. Buat ujian/susulan baru "
                    "atau hubungi developer untuk recovery terkontrol."
                ),
            )

    exam.title = exam_data.title
    exam.description = exam_data.description
    exam.duration_minutes = exam_data.duration_minutes
    exam.start_time = exam_data.start_time
    exam.end_time = exam_data.end_time
    exam.passing_score = exam_data.passing_score
    exam.max_attempts = exam_data.max_attempts
    exam.shuffle_questions = exam_data.shuffle_questions
    exam.shuffle_options = exam_data.shuffle_options
    exam.show_results = exam_data.show_results
    exam.allow_review = exam_data.allow_review
    exam.is_published = exam_data.is_published
    exam.subject = exam_data.subject
    exam.exam_type = exam_data.exam_type
    exam.academic_year = exam_data.academic_year
    exam.show_teacher_name = exam_data.show_teacher_name
    exam.builder_settings = exam_data.builder_settings or {}
    exam.allowed_classes = exam_data.allowed_classes
    exam.allowed_students = exam_data.allowed_students

    update_changes = _collect_exam_update_changes(original_values, exam_data)

    await db.commit()
    # 🆕 FIX: Expire cache and force fresh read from DB
    db.expire(exam)
    await db.refresh(exam)

    if update_changes:
        db.add(
            UserActivityLog(
                user_id=current_user.id,
                event_type="exam_updated",
                event_data={
                    "actor_username": current_user.username,
                    "actor_role": current_user.role,
                    "target_exam_id": exam_id,
                    "target_exam_title": exam.title,
                    "critical_changes": critical_changes,
                    "changes": update_changes,
                },
            )
        )
        await db.commit()

    # Log admin action if admin editing other teacher's exam
    if current_user.is_admin and exam.creator_id != current_user.id:
        # Convert exam_data to dict and handle JSON serialization
        def json_serializable(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            elif isinstance(obj, (list, tuple)):
                return [json_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: json_serializable(v) for k, v in obj.items()}
            else:
                return str(obj)

        changes_dict = exam_data.dict()
        changes_dict = json_serializable(changes_dict)

        await log_admin_action(
            db, current_user, "edit", "exam", exam_id, exam.title,
            {"original_creator_id": exam.creator_id, "changes": changes_dict}
        )

    return ExamResponse.from_orm_with_wib(exam)


@router.delete("/{exam_id}", status_code=204)
async def delete_exam(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete an exam."""
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
    )

    # Archive metadata for all sessions before soft delete
    # This preserves what exam the student took even if the exam definition is deleted
    sessions_result = await db.execute(
        select(ExamSession).where(ExamSession.exam_id == exam_id)
    )
    sessions = sessions_result.scalars().all()

    for session in sessions:
        # Check if columns exist (assuming they were added in models)
        # If not, this is a safety check. Based on audit, we assume implementation needed.
        # Ideally, ExamSession model should have these columns.
        if hasattr(session, 'archived_exam_title'):
            session.archived_exam_title = exam.title
            session.archived_exam_subject = exam.subject
            session.archived_exam_type = exam.exam_type

    # Soft delete
    exam.is_deleted = True
    # exam.deleted_at = datetime.now(timezone.utc) # Uncomment if column exists
    await db.commit()

    # Log admin action if admin deleting other teacher's exam
    if current_user.is_admin and exam.creator_id != current_user.id:
        await log_admin_action(
            db, current_user, "delete", "exam", exam_id, exam.title,
            {"original_creator_id": exam.creator_id, "soft_delete": True}
        )

    return Response(status_code=204)


@router.post("/{exam_id}/publish")
async def publish_exam(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Publish an exam to make it visible to students."""
    if is_pengawas_user(current_user):
        raise HTTPException(
            status_code=403,
            detail="Pengawas tidak diizinkan publish ujian. Hanya guru pembuat atau admin.",
        )

    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
    )

    # Auto-fill placeholder options when teacher only sets keys (super-permissive authoring mode)
    await _autofill_placeholder_options_for_publish(exam_id, db)

    # Validate after normalization
    await _validate_questions_for_publish(exam_id, db)

    exam.is_published = True
    await db.commit()

    return {"message": "Ujian berhasil dipublikasikan", "is_published": True}


@router.patch("/{exam_id}/publish")
async def toggle_publish_exam(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Toggle exam publish status (publish/unpublish)."""
    from app.core.redis_pubsub import publish_message
    from app.models.session import ExamSession

    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    is_pengawas = is_pengawas_user(current_user)

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
        allow_pengawas=is_pengawas and bool(exam.is_published),
    )

    if is_pengawas and not bool(exam.is_published):
        raise HTTPException(
            status_code=403,
            detail="Pengawas hanya dapat menarik ujian (unpublish), tidak dapat publish.",
        )

    was_published = exam.is_published

    # Validate before transitioning draft -> published
    if not was_published:
        await _autofill_placeholder_options_for_publish(exam_id, db)
        await _validate_questions_for_publish(exam_id, db)

    # Toggle publish status
    exam.is_published = not exam.is_published
    await db.commit()

    # If exam was just UNPUBLISHED (cancelled), notify all active students
    if was_published and not exam.is_published:
        # Get all active sessions for this exam
        active_sessions = await db.execute(
            select(ExamSession)
            .where(
                ExamSession.exam_id == exam_id,
                ExamSession.status.in_(['in_progress', 'started', 'active'])
            )
        )
        sessions = active_sessions.scalars().all()
        target_user_ids = [int(s.user_id) for s in sessions]
        # Close read transaction before Redis/network operations.
        await db.commit()

        # Get teacher/admin name for notification
        cancelled_by = current_user.full_name or current_user.username

        # Send cancellation notification to each active student
        for target_user_id in target_user_ids:
            try:
                await publish_message(f"exam_student_{exam_id}_{target_user_id}", {
                    "type": "exam_cancelled",
                    "reason": "Ujian telah dibatalkan atau ditunda oleh pengawas",
                    "cancelled_by": cancelled_by,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"Failed to notify student {target_user_id}: {e}"
                )

        # Also broadcast to exam monitor channel
        try:
            await _publish_exam_monitor_event(exam_id, {
                "type": "exam_unpublished",
                "exam_id": exam_id,
                "cancelled_by": cancelled_by,
                "active_students_notified": len(sessions),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as exc:
            logger.warning(
                "Failed to broadcast exam_unpublished monitor event for exam_id=%s: %s",
                exam_id,
                str(exc),
                exc_info=True,
            )

        # CRITICAL: Delete non-submitted sessions so students can rejoin when republished
        # Only keep submitted/completed sessions (actual exam attempts that count)
        from sqlalchemy import delete
        delete_result = await db.execute(
            delete(ExamSession)
            .where(
                ExamSession.exam_id == exam_id,
                ~ExamSession.status.in_(['submitted', 'completed'])
            )
        )
        await db.commit()

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Exam {exam_id} unpublished: deleted {delete_result.rowcount} non-submitted sessions")

    action = "dipublikasikan" if exam.is_published else "dibatalkan publikasinya"
    return {
        "message": f"Ujian berhasil {action}",
        "is_published": exam.is_published
    }


@router.get("/results/all", response_model=List[ExamResponse])
async def get_exams_with_results(
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db_read)
):
    """
    Get all COMPLETED exams for results page (excluding deleted exams).

    Shows exams where:
    1. Completed + never had results (fresh exams for monitoring)
    2. OR has submitted/completed sessions (exams with actual results)

    IMPORTANT: Excludes soft-deleted exams AND exams that had results deleted

    Logic:
    - Fresh exam (has_ever_had_results=False) → SHOW (monitoring)
    - Exam with results (has sessions) → SHOW (view results)
    - Exam with deleted results (has_ever_had_results=True, no sessions) → HIDE
    - Deleted exam (is_deleted=True) → HIDE

    Authorization: Teacher/Admin only
    """
    now = datetime.now(timezone.utc)

    # Get exam IDs that currently have results
    exams_with_results_subquery = (
        select(ExamSession.exam_id)
        .where(ExamSession.status.in_(["submitted", "completed"]))
        .distinct()
    )

    # Main query: Get exams that are either:
    # 1. Completed + never had results (fresh exams)
    # 2. Currently have results
    # Exclude: soft-deleted exams + exams with deleted results
    query = (
        select(Exam)
        .options(
            noload("*"),
            joinedload(Exam.creator).noload("*"),
            noload(Exam.questions),
            noload(Exam.sessions),
            noload(Exam.schedules),
        )
        .where(
            or_(
                # Fresh completed exams (never had results) - for monitoring
                and_(
                    Exam.end_time < now,
                    Exam.has_ever_had_results == False
                ),
                # Exams with current results
                Exam.id.in_(exams_with_results_subquery)
            )
        )
        .where(Exam.is_deleted == False)  # Exclude soft-deleted exams
        .order_by(Exam.created_at.desc())
    )

    # For teachers, only show their own exams
    if current_user.role == "teacher":
        query = query.where(Exam.creator_id == current_user.id)
    # Admins can see all exams

    # FIX: Only show published exams
    query = query.where(Exam.is_published == True)

    result = await db.execute(query)
    exams = result.scalars().all()

    question_count_map: Dict[int, int] = {}
    exam_ids = [exam.id for exam in exams]
    if exam_ids:
        count_rows = await db.execute(
            select(Question.exam_id, func.count(Question.id))
            .where(Question.exam_id.in_(exam_ids))
            .group_by(Question.exam_id)
        )
        question_count_map = {exam_id: total for exam_id, total in count_rows.all()}

    for exam in exams:
        setattr(exam, "_question_count", int(question_count_map.get(exam.id, 0)))

    return [ExamResponse.from_orm_with_wib(exam) for exam in exams]


@router.get("/my-results", response_model=List[ExamResponse])
async def get_my_exam_results(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_read)
):
    """Get current user's exam history and results."""
    # Only participant roles can access this endpoint.
    if not _is_exam_participant_role(current_user.role):
        raise HTTPException(
            status_code=403,
            detail="Hanya peserta ujian yang dapat melihat riwayat ujian sendiri",
        )

    result = await db.execute(
        select(ExamSession)
        .options(selectinload(ExamSession.exam))
        .where(
            ExamSession.user_id == current_user.id,
            ExamSession.status.in_(['completed', 'submitted'])
        )
        .order_by(ExamSession.end_time.desc())
    )
    sessions = result.scalars().all()

    # Map sessions to ExamResponse format (simplified for list view)
    # We return the exam data but enriched with session score
    history = []
    for session in sessions:
        if not session.exam:
            continue

        # Use archived metadata if exam was deleted
        exam_data = session.exam

        # Note: We are returning ExamResponse, so we map session data to it where possible
        # or rely on the frontend to call separate details endpoint if needed.
        # But for "My Results", ideally we'd have a specific schema.
        # Re-using ExamResponse for now as requested by Audit Report structure implies list logic.

        # BUT, standard ExamResponse doesn't have "my_score".
        # However, the audit recommendation just said "return results".
        # Let's map it to the Exam schema structure.

        history.append(ExamResponse.from_orm_with_wib(exam_data))

    return history


@router.get("/{exam_id}/participation-summary")
async def get_exam_participation_summary(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db_read),
):
    """
    Summarize target participants vs actual sessions.

    This separates:
    - target students who never started
    - target students who started but have not submitted
    - submitted sessions outside current target metadata
    """
    exam_result = await db.execute(
        select(
            Exam.id,
            Exam.title,
            Exam.creator_id,
            Exam.allowed_classes,
            Exam.allowed_students,
            User.role.label("creator_role"),
        )
        .join(User, User.id == Exam.creator_id)
        .where(Exam.id == exam_id, Exam.is_deleted == False)
    )
    exam = exam_result.mappings().one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    _enforce_developer_exam_visibility(current_user, exam["creator_role"])
    if int(exam["creator_id"]) != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view this exam's participation summary")

    allowed_class_values = [
        value.strip()
        for value in (exam["allowed_classes"] or "").split(",")
        if value.strip()
    ]
    allowed_student_values = [
        value.strip()
        for value in (exam["allowed_students"] or "").split(",")
        if value.strip()
    ]

    target_conditions = [User.role == "student", User.is_active == True]
    restriction_clauses = []
    if allowed_class_values:
        restriction_clauses.append(User.student_class.in_(allowed_class_values))
    if allowed_student_values:
        restriction_clauses.append(User.id.cast(sqlalchemy.String).in_(allowed_student_values))
    if restriction_clauses:
        target_conditions.append(or_(*restriction_clauses))

    target_result = await db.execute(
        select(User.id, User.username, User.full_name, User.student_class)
        .where(*target_conditions)
        .order_by(User.student_class.asc(), User.full_name.asc(), User.username.asc())
    )
    target_rows = [dict(row) for row in target_result.mappings().all()]
    target_ids = {int(row["id"]) for row in target_rows}
    target_by_id = {int(row["id"]): row for row in target_rows}

    sessions_result = await db.execute(
        select(
            ExamSession.id.label("session_id"),
            ExamSession.user_id,
            ExamSession.status,
            ExamSession.start_time,
            ExamSession.end_time,
            User.username,
            User.full_name,
            User.student_class,
        )
        .join(User, User.id == ExamSession.user_id)
        .where(ExamSession.exam_id == exam_id)
        .order_by(ExamSession.start_time.desc(), ExamSession.id.desc())
    )
    session_rows = [dict(row) for row in sessions_result.mappings().all()]

    sessions_by_user: Dict[int, List[Dict[str, Any]]] = {}
    for row in session_rows:
        sessions_by_user.setdefault(int(row["user_id"]), []).append(row)

    submitted_statuses = {"submitted", "completed"}
    submitted_user_ids = {
        int(row["user_id"])
        for row in session_rows
        if str(row.get("status") or "").lower() in submitted_statuses
    }
    users_with_any_session = set(sessions_by_user.keys())

    target_submitted_ids = target_ids & submitted_user_ids
    not_started_ids = target_ids - users_with_any_session
    started_not_submitted_ids = {
        user_id
        for user_id in (target_ids & users_with_any_session)
        if user_id not in submitted_user_ids
    }
    submitted_outside_target_ids = submitted_user_ids - target_ids

    non_submitted_status_counts: Dict[str, int] = {}
    for user_id in started_not_submitted_ids:
        latest_status = str((sessions_by_user.get(user_id) or [{}])[0].get("status") or "unknown")
        non_submitted_status_counts[latest_status] = non_submitted_status_counts.get(latest_status, 0) + 1

    outside_students = []
    for user_id in sorted(submitted_outside_target_ids):
        latest = (sessions_by_user.get(user_id) or [{}])[0]
        outside_students.append(
            _student_summary_entry(
                {
                    "id": user_id,
                    "username": latest.get("username") or "",
                    "full_name": latest.get("full_name") or latest.get("username") or "",
                    "student_class": latest.get("student_class") or "",
                }
            )
        )

    return {
        "exam_id": exam_id,
        "exam_title": exam["title"],
        "restrictions": {
            "allowed_classes": allowed_class_values,
            "allowed_students_count": len(allowed_student_values),
        },
        "target_count": len(target_ids),
        "submitted_in_target_count": len(target_submitted_ids),
        "submitted_total_count": len(submitted_user_ids),
        "submitted_outside_target_count": len(submitted_outside_target_ids),
        "not_started_count": len(not_started_ids),
        "started_not_submitted_count": len(started_not_submitted_ids),
        "session_total_count": len(session_rows),
        "non_submitted_status_counts": non_submitted_status_counts,
        "not_started_students": [
            _student_summary_entry(target_by_id[user_id])
            for user_id in sorted(not_started_ids)
        ][:200],
        "started_not_submitted_students": [
            _student_summary_entry(target_by_id[user_id])
            for user_id in sorted(started_not_submitted_ids)
        ][:200],
        "submitted_outside_target_students": outside_students[:200],
    }


@router.get("/{exam_id}/participation-summary/export")
async def export_exam_participation_summary(
    exam_id: int,
    format: str = Query(
        "csv",
        pattern="^(csv|excel|xls|pdf|docx|word)$",
        description="Export format: csv, excel/xls, pdf, docx/word",
    ),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db_read),
):
    """Export target-vs-submission participation rows as CSV, Excel, PDF, or Word."""
    require_feature_enabled(
        settings.heavy_exports_active,
        "heavy_export",
        status_code=503,
        message="Ekspor partisipasi sedang dinonaktifkan selama mode ujian/puncak.",
    )
    exam_result = await db.execute(
        select(
            Exam.id,
            Exam.title,
            Exam.subject,
            Exam.exam_type,
            Exam.creator_id,
            Exam.allowed_classes,
            Exam.allowed_students,
            User.role.label("creator_role"),
            User.full_name.label("creator_name"),
            User.username.label("creator_username"),
        )
        .join(User, User.id == Exam.creator_id)
        .where(Exam.id == exam_id, Exam.is_deleted == False)
    )
    exam = exam_result.mappings().one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    _enforce_developer_exam_visibility(current_user, exam["creator_role"])
    if int(exam["creator_id"]) != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to export this exam's participation summary")

    allowed_class_values = [
        value.strip()
        for value in (exam["allowed_classes"] or "").split(",")
        if value.strip()
    ]
    allowed_student_values = [
        value.strip()
        for value in (exam["allowed_students"] or "").split(",")
        if value.strip()
    ]

    target_conditions = [User.role == "student", User.is_active == True]
    restriction_clauses = []
    if allowed_class_values:
        restriction_clauses.append(User.student_class.in_(allowed_class_values))
    if allowed_student_values:
        restriction_clauses.append(User.id.cast(sqlalchemy.String).in_(allowed_student_values))
    if restriction_clauses:
        target_conditions.append(or_(*restriction_clauses))

    target_result = await db.execute(
        select(User.id, User.username, User.full_name, User.student_class)
        .where(*target_conditions)
        .order_by(User.student_class.asc(), User.full_name.asc(), User.username.asc())
    )
    target_rows = [dict(row) for row in target_result.mappings().all()]
    target_by_id = {int(row["id"]): row for row in target_rows}
    target_ids = set(target_by_id.keys())

    sessions_result = await db.execute(
        select(
            ExamSession.id.label("session_id"),
            ExamSession.user_id,
            ExamSession.status,
            ExamSession.start_time,
            ExamSession.end_time,
            ExamSession.score,
            User.username,
            User.full_name,
            User.student_class,
        )
        .join(User, User.id == ExamSession.user_id)
        .where(ExamSession.exam_id == exam_id)
        .order_by(ExamSession.start_time.desc(), ExamSession.id.desc())
    )
    session_rows = [dict(row) for row in sessions_result.mappings().all()]

    sessions_by_user: Dict[int, List[Dict[str, Any]]] = {}
    for row in session_rows:
        sessions_by_user.setdefault(int(row["user_id"]), []).append(row)

    submitted_statuses = {"submitted", "completed"}
    submitted_user_ids = {
        int(row["user_id"])
        for row in session_rows
        if str(row.get("status") or "").lower() in submitted_statuses
    }

    def latest_session(user_id: int, *, submitted_only: bool = False) -> Optional[Dict[str, Any]]:
        for session_row in sessions_by_user.get(user_id, []):
            if not submitted_only or str(session_row.get("status") or "").lower() in submitted_statuses:
                return session_row
        return None

    target_with_session_ids = target_ids & set(sessions_by_user.keys())
    summary_rows = [
        ("Exam ID", exam_id),
        ("Nama Ujian", exam["title"]),
        ("Mata Pelajaran", exam["subject"] or "-"),
        ("Jenis Ujian", exam["exam_type"] or "-"),
        ("Guru/Admin", exam["creator_name"] or exam["creator_username"] or "-"),
        ("Kelas Target", ", ".join(allowed_class_values) or "Semua/khusus peserta"),
        ("Jumlah Peserta Khusus", len(allowed_student_values)),
        ("Target", len(target_ids)),
        ("Submitted Total", len(submitted_user_ids)),
        ("Submitted Dalam Target", len(target_ids & submitted_user_ids)),
        ("Belum Start", len(target_ids - set(sessions_by_user.keys()))),
        ("Sudah Start Belum Submit", len(target_with_session_ids - submitted_user_ids)),
        ("Submitted Di Luar Target", len(submitted_user_ids - target_ids)),
    ]
    table_headers = [
        "No",
        "Kategori",
        "User ID",
        "Username",
        "Nama",
        "Kelas",
        "Session ID",
        "Status Session",
        "Nilai",
        "Mulai",
        "Selesai/Submit",
        "Keterangan",
    ]
    table_rows: List[List[Any]] = []

    row_no = 1
    sorted_target_ids = sorted(
        target_ids,
        key=lambda user_id: (
            str(target_by_id[user_id].get("student_class") or ""),
            str(target_by_id[user_id].get("full_name") or target_by_id[user_id].get("username") or ""),
        ),
    )
    for user_id in sorted_target_ids:
        target = target_by_id[user_id]
        session = latest_session(user_id, submitted_only=user_id in submitted_user_ids)
        if user_id in submitted_user_ids:
            category = "submitted"
            note = "Sudah submit"
        elif session:
            category = "started_not_submitted"
            note = "Sudah ada sesi tetapi belum submitted"
        else:
            category = "not_started"
            note = "Belum pernah membuat sesi ujian"
        table_rows.append([
            row_no,
            category,
            user_id,
            target.get("username") or "",
            target.get("full_name") or target.get("username") or "",
            target.get("student_class") or "",
            session.get("session_id") if session else "",
            session.get("status") if session else "",
            str(session.get("score")) if session and session.get("score") is not None else "",
            _format_wib_datetime(session.get("start_time")) if session else "",
            _format_wib_datetime(session.get("end_time")) if session else "",
            note,
        ])
        row_no += 1

    for user_id in sorted(submitted_user_ids - target_ids):
        session = latest_session(user_id, submitted_only=True) or {}
        table_rows.append([
            row_no,
            "submitted_outside_target",
            user_id,
            session.get("username") or "",
            session.get("full_name") or session.get("username") or "",
            session.get("student_class") or "",
            session.get("session_id") or "",
            session.get("status") or "",
            str(session.get("score")) if session.get("score") is not None else "",
            _format_wib_datetime(session.get("start_time")),
            _format_wib_datetime(session.get("end_time")),
            "Submitted, tetapi di luar target metadata saat ini",
        ])
        row_no += 1

    export_format = format.lower().strip()
    if export_format == "word":
        export_format = "docx"
    if export_format == "excel":
        export_format = "xls"

    safe_title = re.sub(r"[^\w\s-]", "", exam["title"] or "ujian").strip()
    safe_title = re.sub(r"\s+", "_", safe_title) or "ujian"
    filename_base = f"kehadiran_ujian_{safe_title}_{datetime.now().strftime('%Y%m%d')}"

    if export_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Laporan Kehadiran Ujian"])
        for label, value in summary_rows:
            writer.writerow([label, value])
        writer.writerow([])
        writer.writerow(table_headers)
        writer.writerows(table_rows)
        return Response(
            content="\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.csv"'},
        )

    if export_format == "xls":
        def td(value: Any, *, header: bool = False) -> str:
            tag = "th" if header else "td"
            return f"<{tag}>{html.escape(str(value if value is not None else ''))}</{tag}>"

        summary_html = "".join(
            f"<tr>{td(label, header=True)}{td(value)}</tr>" for label, value in summary_rows
        )
        header_html = "".join(td(header, header=True) for header in table_headers)
        body_html = "".join(
            "<tr>" + "".join(td(value) for value in row) + "</tr>" for row in table_rows
        )
        html_content = f"""
        <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
        <head><meta charset="utf-8"><style>
            body {{ font-family: Arial, sans-serif; }}
            h2 {{ color: #0f172a; }}
            table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
            th {{ background: #0f172a; color: white; font-weight: bold; }}
            th, td {{ border: 1px solid #000; padding: 6px; vertical-align: top; }}
        </style></head>
        <body>
            <h2>Laporan Kehadiran Ujian</h2>
            <table>{summary_html}</table>
            <table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>
        </body></html>
        """
        return Response(
            content="\ufeff" + html_content,
            media_type="application/vnd.ms-excel; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.xls"'},
        )

    if export_format == "pdf":
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        except Exception as exc:
            raise HTTPException(status_code=501, detail="PDF export tidak tersedia. Install ReportLab.") from exc

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=18, leftMargin=18, topMargin=18, bottomMargin=18)
        styles = getSampleStyleSheet()
        story = [Paragraph("Laporan Kehadiran Ujian", styles["Title"]), Spacer(1, 8)]
        summary_table = Table([[str(label), str(value)] for label, value in summary_rows], colWidths=[150, 420])
        summary_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.extend([summary_table, Spacer(1, 10)])
        pdf_headers = ["No", "Kategori", "Username", "Nama", "Kelas", "Status", "Nilai", "Keterangan"]
        pdf_rows = [pdf_headers]
        for row in table_rows:
            pdf_rows.append([row[0], row[1], row[3], row[4], row[5], row[7], row[8], row[11]])
        pdf_table = Table(pdf_rows, repeatRows=1, colWidths=[28, 82, 82, 150, 48, 62, 38, 210])
        pdf_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(pdf_table)
        doc.build(story)
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'},
        )

    if export_format == "docx":
        try:
            from docx import Document
            from docx.enum.section import WD_ORIENT
            from docx.shared import Inches
        except Exception as exc:
            raise HTTPException(status_code=501, detail="Word export tidak tersedia. Install python-docx.") from exc

        document = Document()
        section = document.sections[0]
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width
        section.left_margin = Inches(0.45)
        section.right_margin = Inches(0.45)
        document.add_heading("Laporan Kehadiran Ujian", level=1)
        for label, value in summary_rows:
            paragraph = document.add_paragraph()
            paragraph.add_run(f"{label}: ").bold = True
            paragraph.add_run(str(value))
        document.add_paragraph("")
        table = document.add_table(rows=1, cols=len(table_headers))
        table.style = "Table Grid"
        for idx, header in enumerate(table_headers):
            table.rows[0].cells[idx].text = header
        for row in table_rows:
            cells = table.add_row().cells
            for idx, value in enumerate(row):
                cells[idx].text = str(value if value is not None else "")
        buffer = io.BytesIO()
        document.save(buffer)
        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.docx"'},
        )

    raise HTTPException(status_code=400, detail="Format export tidak didukung")


@router.get("/{exam_id}/results")
async def get_exam_results(
    exam_id: int,
    include_breakdown: bool = Query(
        False,
        description="Include per-question score breakdown in response payload",
    ),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db_read)
):
    """
    Get all results/sessions for a specific exam.

    Returns list of completed/submitted sessions with student info and scores.
    """
    # Verify exam exists and user has access
    exam_result = await db.execute(
        select(
            Exam.id,
            Exam.title,
            Exam.subject,
            Exam.exam_type,
            Exam.passing_score,
            Exam.creator_id,
            User.role.label("creator_role"),
        )
        .join(User, User.id == Exam.creator_id)
        .where(Exam.id == exam_id, Exam.is_deleted == False)
    )
    exam = exam_result.mappings().one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    _enforce_developer_exam_visibility(current_user, exam["creator_role"])

    # 🆕 FIX #4: Standardized permission check (admin bypass)
    if exam["creator_id"] != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view this exam's results")

    viewer_scope = _build_exam_results_viewer_scope(current_user, int(exam["creator_id"]))
    cache_key = _build_exam_results_cache_key(exam_id, include_breakdown, viewer_scope)
    cached_results = await _get_cached_exam_results(cache_key)
    if cached_results is not None:
        return cached_results

    # Get all completed/submitted sessions with student info
    try:
        sessions_result = await db.execute(
            select(
                ExamSession.id.label("session_id"),
                ExamSession.user_id,
                ExamSession.start_time,
                ExamSession.end_time,
                ExamSession.score,
                ExamSession.violation_count,
                ExamSession.status,
                User.id.label("student_id"),
                User.full_name,
                User.username,
                User.student_class,
            )
            .join(User, ExamSession.user_id == User.id)
            .where(
                ExamSession.exam_id == exam_id,
                ExamSession.status.in_(["submitted", "completed"])
            )
            .order_by(ExamSession.end_time.desc(), ExamSession.id.desc())
        )
        session_rows = [dict(row) for row in sessions_result.mappings().all()]
        if not session_rows:
            await _set_cached_exam_results(cache_key, [], include_breakdown=include_breakdown)
            return []
        selected_session_rows = _pick_latest_scored_exam_session_per_user(session_rows)

        ordered_questions: List[Dict[str, Any]] = []
        answers_by_session: Dict[int, Dict[int, Dict[str, Any]]] = {}

        if include_breakdown:
            questions_result = await db.execute(
                select(
                    Question.id.label("question_id"),
                    Question.question_type,
                    Question.points,
                    Question.order_index,
                )
                .where(Question.exam_id == exam_id)
                .order_by(Question.order_index.asc(), Question.id.asc())
            )
            ordered_questions = [dict(row) for row in questions_result.mappings().all()]

            if ordered_questions:
                session_ids = [int(row["session_id"]) for row in selected_session_rows]
                answers_result = await db.execute(
                    select(
                        Answer.session_id,
                        Answer.question_id,
                        Answer.is_correct,
                        Answer.points_earned,
                    )
                    .where(Answer.session_id.in_(session_ids))
                )
                for answer_row in answers_result.mappings().all():
                    session_answer_map = answers_by_session.setdefault(
                        int(answer_row["session_id"]),
                        {},
                    )
                    session_answer_map[int(answer_row["question_id"])] = {
                        "is_correct": answer_row["is_correct"],
                        "points_earned": answer_row["points_earned"],
                    }

        passing_score = float(exam["passing_score"]) if exam["passing_score"] is not None else 70.0
        results: List[Dict[str, Any]] = []

        for row in selected_session_rows:
            start_time = row["start_time"]
            end_time = row["end_time"]
            duration_seconds = 0
            if start_time and end_time:
                duration_seconds = int((end_time - start_time).total_seconds())

            score_value = float(row["score"]) if row["score"] is not None else 0.0
            passed = score_value >= passing_score if row["score"] is not None else False

            session_metadata: Dict[str, Any] = {}
            if include_breakdown and ordered_questions:
                score_breakdown = []
                answers_by_question_id = answers_by_session.get(int(row["session_id"]), {})

                for question in ordered_questions:
                    answer = answers_by_question_id.get(int(question["question_id"]))
                    max_points = float(question["points"]) if question["points"] is not None else 0.0
                    points_earned = None
                    if answer and answer["points_earned"] is not None:
                        points_earned = float(answer["points_earned"])

                    if answer is None:
                        item_status = "not_answered"
                        item_is_correct = False
                        points_earned = 0.0
                    elif points_earned is None:
                        item_status = "pending"
                        item_is_correct = None
                    elif question["question_type"] in ("essay", "short_answer"):
                        if points_earned >= max_points:
                            item_status = "correct"
                            item_is_correct = True
                        elif points_earned <= 0:
                            item_status = "incorrect"
                            item_is_correct = False
                        else:
                            item_status = "partial"
                            item_is_correct = None
                    else:
                        if answer["is_correct"] is True:
                            item_status = "correct"
                            item_is_correct = True
                        elif answer["is_correct"] is False and points_earned > 0:
                            item_status = "partial"
                            item_is_correct = False
                        elif answer["is_correct"] is False:
                            item_status = "incorrect"
                            item_is_correct = False
                        elif points_earned > 0:
                            item_status = "partial"
                            item_is_correct = None
                        else:
                            item_status = "incorrect"
                            item_is_correct = False

                    score_breakdown.append(
                        {
                            "question_id": str(question["question_id"]),
                            "question_type": question["question_type"],
                            "points_earned": points_earned,
                            "max_points": max_points,
                            "is_correct": item_is_correct,
                            "status": item_status,
                        }
                    )

                session_metadata["score_breakdown"] = score_breakdown

            results.append(
                {
                    "id": int(row["session_id"]),
                    "user_id": int(row["user_id"]),
                    "user": {
                        "id": int(row["student_id"]),
                        "full_name": row["full_name"] or row["username"] or "Unknown",
                        "username": row["username"] or "unknown",
                        "student_class": row["student_class"] or "",
                    },
                    "exam": {
                        "id": int(exam["id"]),
                        "title": exam["title"],
                        "subject": exam["subject"] or "",
                        "exam_type": exam["exam_type"] or "",
                        "passing_score": passing_score,
                    },
                    "score": score_value,
                    "start_time": start_time,
                    "end_time": end_time,
                    "submitted_at": end_time,
                    "duration_seconds": duration_seconds,
                    "violation_count": row["violation_count"] or 0,
                    "passed": passed,
                    "status": row["status"] or "unknown",
                    "session_metadata": session_metadata,
                }
            )

        await _set_cached_exam_results(cache_key, results, include_breakdown=include_breakdown)
        return results
    except Exception:
        logger.exception("Error in get_exam_results")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server saat memuat hasil ujian.")


@router.get("/{exam_id}/sessions/{session_id}/review")
async def get_session_answer_review(
    exam_id: int,
    session_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db_read),
):
    """
    Fetch detailed answer review payload for admin/teacher result inspection.
    Lightweight by using 3 bounded queries:
    - session + participant + exam metadata
    - ordered questions + options
    - submitted answers for this session
    """
    session_row_result = await db.execute(
        select(
            ExamSession.id.label("session_id"),
            ExamSession.user_id,
            ExamSession.score,
            ExamSession.status,
            ExamSession.start_time,
            ExamSession.end_time,
            User.id.label("student_id"),
            User.full_name,
            User.username,
            User.student_class,
            Exam.id.label("exam_id"),
            Exam.title,
            Exam.subject,
            Exam.exam_type,
            Exam.passing_score,
            Exam.creator_id,
        )
        .join(User, ExamSession.user_id == User.id)
        .join(Exam, ExamSession.exam_id == Exam.id)
        .where(
            ExamSession.id == session_id,
            ExamSession.exam_id == exam_id,
            Exam.is_deleted == False,
        )
    )
    session_row = session_row_result.mappings().one_or_none()
    if not session_row:
        raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan")

    creator_role = await _get_exam_creator_role(db, int(session_row["creator_id"]))
    _enforce_developer_exam_visibility(current_user, creator_role)

    if (
        int(session_row["creator_id"]) != current_user.id
        and not bool(current_user.is_admin)
    ):
        raise HTTPException(status_code=403, detail="Tidak memiliki akses")

    questions_result = await db.execute(
        select(Question)
        .options(selectinload(Question.options))
        .where(Question.exam_id == exam_id)
        .order_by(Question.order_index.asc(), Question.id.asc())
    )
    questions = questions_result.scalars().all()

    answers_result = await db.execute(
        select(Answer)
        .where(Answer.session_id == session_id)
    )
    answers = answers_result.scalars().all()
    answers_by_question = {int(a.question_id): a for a in answers}

    total_questions = len(questions)
    correct_count = 0
    partial_count = 0
    incorrect_count = 0
    pending_count = 0
    unanswered_count = 0
    review_items: List[Dict[str, Any]] = []

    for order_idx, question in enumerate(questions, start=1):
        max_points = float(question.points or 0.0)
        answer = answers_by_question.get(int(question.id))
        question_settings = dict(question.question_settings or {})
        option_map = _build_option_map(question.options or [])
        options_payload = list(option_map.values())
        correct_options = [opt for opt in options_payload if opt["is_correct"]]

        status = _status_from_answer(answer, max_points)
        if status == "correct":
            correct_count += 1
        elif status == "partial":
            partial_count += 1
        elif status == "pending":
            pending_count += 1
        elif status == "not_answered":
            unanswered_count += 1
        else:
            incorrect_count += 1

        points_earned = float(answer.points_earned) if answer and answer.points_earned is not None else 0.0
        answer_meta = dict(answer.answer_metadata or {}) if answer else {}
        statement_answers = (
            answer_meta.get("statement_answers")
            if isinstance(answer_meta.get("statement_answers"), dict)
            else {}
        )

        student_answer_display = "-"
        answer_key_display = "-"
        student_answer_payload: Dict[str, Any] = {"type": question.question_type, "display": "-"}
        answer_key_payload: Dict[str, Any] = {"type": question.question_type, "display": "-"}

        if question.question_type in {"multiple_choice", "true_false"}:
            selected = option_map.get(int(answer.selected_option_id)) if answer and answer.selected_option_id else None
            key_opt = correct_options[0] if correct_options else None

            if selected:
                student_answer_display = f"{selected['label']}. {selected['text']}"
                student_answer_payload.update({
                    "selected_option_id": selected["id"],
                    "selected_option_label": selected["label"],
                    "selected_option_text": selected["text"],
                    "display": student_answer_display,
                })
            else:
                student_answer_payload["display"] = "-"

            if key_opt:
                answer_key_display = f"{key_opt['label']}. {key_opt['text']}"
                answer_key_payload.update({
                    "correct_option_id": key_opt["id"],
                    "correct_option_label": key_opt["label"],
                    "correct_option_text": key_opt["text"],
                    "display": answer_key_display,
                })
            else:
                answer_key_payload["display"] = "-"

        elif question.question_type == "multiple_choice_complex":
            pgk_type = question.pgk_type or str(question_settings.get("pgk_type") or "checkbox")
            if pgk_type == "table_validation":
                statements = _resolve_question_statements(question_settings)
                key_map = _resolve_statement_keys(question_settings, len(statements))
                table_rows: List[Dict[str, Any]] = []
                student_lines: List[str] = []
                key_lines: List[str] = []

                max_index = max(
                    len(statements),
                    len(key_map),
                    len(statement_answers) if isinstance(statement_answers, dict) else 0,
                )

                for idx in range(max_index):
                    key = str(idx)
                    statement_text = statements[idx] if idx < len(statements) else f"Pernyataan {idx + 1}"
                    correct_bool = key_map.get(key)
                    student_bool = _coerce_bool(statement_answers.get(key)) if isinstance(statement_answers, dict) else None
                    table_rows.append(
                        {
                            "index": idx + 1,
                            "statement": statement_text,
                            "student_answer": student_bool,
                            "correct_answer": correct_bool,
                        }
                    )
                    student_lines.append(
                        f"{idx + 1}. {statement_text}: "
                        f"{'Benar' if student_bool is True else ('Salah' if student_bool is False else '-')}"
                    )
                    key_lines.append(
                        f"{idx + 1}. {statement_text}: "
                        f"{'Benar' if correct_bool is True else ('Salah' if correct_bool is False else '-')}"
                    )

                student_answer_display = " | ".join(student_lines) if student_lines else "-"
                answer_key_display = " | ".join(key_lines) if key_lines else "-"
                student_answer_payload.update(
                    {
                        "pgk_type": "table_validation",
                        "rows": table_rows,
                        "display": student_answer_display,
                    }
                )
                answer_key_payload.update(
                    {
                        "pgk_type": "table_validation",
                        "rows": table_rows,
                        "display": answer_key_display,
                    }
                )
            else:
                selected_ids = [int(x) for x in (answer.selected_option_ids or [])] if answer else []
                selected_opts = [option_map[opt_id] for opt_id in selected_ids if opt_id in option_map]
                selected_opts.sort(key=lambda x: x["label"])

                student_answer_display = ", ".join(
                    f"{opt['label']}. {opt['text']}" for opt in selected_opts
                ) if selected_opts else "-"
                answer_key_display = ", ".join(
                    f"{opt['label']}. {opt['text']}" for opt in correct_options
                ) if correct_options else "-"

                student_answer_payload.update(
                    {
                        "pgk_type": "checkbox",
                        "selected_option_ids": [opt["id"] for opt in selected_opts],
                        "selected_options": selected_opts,
                        "display": student_answer_display,
                    }
                )
                answer_key_payload.update(
                    {
                        "pgk_type": "checkbox",
                        "correct_option_ids": [opt["id"] for opt in correct_options],
                        "correct_options": correct_options,
                        "display": answer_key_display,
                    }
                )

        elif question.question_type == "short_answer":
            acceptable_answers = question_settings.get("acceptable_answers") or []
            accepted_values = [
                str(item).strip()
                for item in acceptable_answers
                if str(item or "").strip()
            ]
            student_answer_display = str(answer.answer_text or "").strip() if answer else "-"
            answer_key_display = " / ".join(accepted_values) if accepted_values else "-"
            student_answer_payload.update(
                {
                    "answer_text": student_answer_display if student_answer_display != "-" else "",
                    "display": student_answer_display,
                }
            )
            answer_key_payload.update(
                {
                    "acceptable_answers": accepted_values,
                    "display": answer_key_display,
                }
            )

        else:  # essay + fallback text
            key_essay = (
                str(question_settings.get("answer_key") or "").strip()
                or str(question_settings.get("sample_answer") or "").strip()
            )
            student_answer_display = str(answer.answer_text or "").strip() if answer else "-"
            answer_key_display = key_essay or "-"
            student_answer_payload.update(
                {
                    "answer_text": student_answer_display if student_answer_display != "-" else "",
                    "display": student_answer_display,
                }
            )
            answer_key_payload.update(
                {
                    "sample_answer": key_essay,
                    "display": answer_key_display,
                }
            )

        review_items.append(
            {
                "question_id": int(question.id),
                "order_index": int(question.order_index if question.order_index is not None else order_idx),
                "question_number": order_idx,
                "question_type": question.question_type,
                "question_type_label": QUESTION_TYPE_LABELS.get(question.question_type, question.question_type),
                "question_text": question.question_text or "",
                "stimulus": question.stimulus or "",
                "max_points": max_points,
                "points_earned": points_earned,
                "status": status,
                "is_correct": answer.is_correct if answer else None,
                "answered_at": answer.answered_at.isoformat() if answer and answer.answered_at else None,
                "student_answer": student_answer_payload,
                "answer_key": answer_key_payload,
                "student_answer_display": student_answer_display,
                "answer_key_display": answer_key_display,
                "options": options_payload,
            }
        )

    review_items.sort(key=lambda item: (item["order_index"], item["question_id"]))
    score_value = float(session_row["score"] or 0.0)
    passing_score = float(session_row["passing_score"] or 70.0)

    return {
        "session_id": int(session_row["session_id"]),
        "exam": {
            "id": int(session_row["exam_id"]),
            "title": session_row["title"] or f"Ujian #{exam_id}",
            "subject": session_row["subject"] or "",
            "exam_type": session_row["exam_type"] or "",
            "passing_score": passing_score,
        },
        "student": {
            "id": int(session_row["student_id"]),
            "full_name": session_row["full_name"] or session_row["username"] or "Unknown",
            "username": session_row["username"] or "unknown",
            "student_class": session_row["student_class"] or "",
        },
        "session": {
            "status": session_row["status"] or "unknown",
            "start_time": session_row["start_time"].isoformat() if session_row["start_time"] else None,
            "end_time": session_row["end_time"].isoformat() if session_row["end_time"] else None,
            "score": score_value,
            "passed": score_value >= passing_score,
        },
        "summary": {
            "total_questions": total_questions,
            "answered_questions": total_questions - unanswered_count,
            "correct": correct_count,
            "partial": partial_count,
            "incorrect": incorrect_count,
            "pending": pending_count,
            "unanswered": unanswered_count,
        },
        "questions": review_items,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/{exam_id}/results")
async def delete_exam_results(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete all results/sessions for an exam.

    WARNING: This permanently deletes student session data!
    Use with caution. Only accessible by exam creator or admin.
    """
    # Verify exam exists and user has access
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
    )

    # Delete all sessions and their answers for this exam
    delete_stmt = delete(ExamSession).where(ExamSession.exam_id == exam_id)
    delete_result = await db.execute(delete_stmt)
    await db.commit()
    await _invalidate_exam_results_cache(exam_id)

    deleted_count = delete_result.rowcount

    return {
        "success": True,
        "message": f"Berhasil menghapus {deleted_count} hasil ujian",
        "deleted_count": deleted_count
    }


# ============== TOKEN-BASED ACCESS ==============

class JoinExamRequest(BaseModel):
    token: str

class JoinExamResponse(BaseModel):
    exam_id: int
    title: str
    description: Optional[str]
    duration_minutes: int
    question_count: int
    allowed: bool
    message: str


@router.post("/join", response_model=JoinExamResponse)
async def join_exam_by_token(
    request: JoinExamRequest,
    raw_request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_read)
):
    """
    Join an exam using access token.

    Validates:
    1. Rate limit (5 attempts/min) - Anti Brute-force
    2. Token exists and is valid
    3. Exam is published
    4. Exam is within active time window
    5. Participant belongs to allowed class/list policy
    6. Student hasn't exceeded max attempts
    """
    # Rate limit check (5 per minute) with proxy-aware IP resolver.
    client_ip = get_client_ip(raw_request)
    is_allowed, remaining = await check_rate_limit(RateLimiters.JOIN_EXAM, f"{current_user.id}:{client_ip}")

    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak percobaan token salah. Tunggu 1 menit.",
            headers={"Retry-After": "60"}
        )

    # Only exam participants can join exams.
    if not _is_exam_participant_role(current_user.role):
        raise HTTPException(
            status_code=403,
            detail="Hanya peserta ujian yang dapat mengikuti ujian",
        )

    # Normalize token (uppercase, trim)
    token = request.token.strip().upper()

    if len(token) != 6:
        raise HTTPException(status_code=400, detail="Token harus 6 karakter")

    # Find exam by token (keep query lightweight under burst join traffic).
    result = await db.execute(
        select(Exam, User.role.label("creator_role"))
        .join(User, User.id == Exam.creator_id)
        .where(Exam.access_token == token)
    )
    exam_row = result.first()
    exam = exam_row[0] if exam_row else None
    exam_creator_role = exam_row[1] if exam_row else None

    if not exam:
        raise HTTPException(status_code=404, detail="Token ujian tidak valid")

    # Check if published
    if not exam.is_published:
        raise HTTPException(status_code=403, detail="Ujian belum dipublikasikan")

    # Check time window
    now = datetime.now(timezone.utc)
    if now < exam.start_time:
        raise HTTPException(status_code=403, detail="Ujian belum dimulai")
    if now > exam.end_time:
        raise HTTPException(status_code=403, detail="Ujian sudah berakhir")

    # Check participant restriction.
    _ensure_exam_participant_access(
        exam,
        current_user,
        exam_creator_role=exam_creator_role,
    )

    # Check max attempts (COUNT query avoids loading session rows)
    completed_attempts_result = await db.execute(
        select(func.count(ExamSession.id))
        .where(ExamSession.user_id == current_user.id)
        .where(ExamSession.exam_id == exam.id)
        .where(ExamSession.status.in_(("completed", "submitted")))
    )
    completed_attempts = int(completed_attempts_result.scalar() or 0)

    if completed_attempts >= exam.max_attempts:
        raise HTTPException(status_code=403, detail=f"Anda sudah menggunakan semua kesempatan ({exam.max_attempts}x)")

    question_count_result = await db.execute(
        select(func.count(Question.id)).where(Question.exam_id == exam.id)
    )
    question_count = int(question_count_result.scalar() or 0)

    return JoinExamResponse(
        exam_id=exam.id,
        title=exam.title,
        description=exam.description,
        duration_minutes=exam.duration_minutes,
        question_count=question_count,
        allowed=True,
        message="Token valid. Anda dapat memulai ujian."
    )


@router.post("/{exam_id}/regenerate-token", response_model=ExamResponse)
async def regenerate_exam_token(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate exam access token (teacher/admin only)."""
    result = await db.execute(
        select(Exam)
        .options(selectinload(Exam.questions))
        .where(Exam.id == exam_id)
    )
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
        allow_pengawas=is_pengawas_user(current_user) and bool(exam.is_published),
    )

    if is_pengawas_user(current_user) and not bool(exam.is_published):
        raise HTTPException(
            status_code=403,
            detail="Pengawas hanya dapat refresh token untuk ujian yang sedang/published.",
        )

    # Generate new token
    allowed_chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'

    for _ in range(10):
        new_token = ''.join(secrets.choice(allowed_chars) for _ in range(6))
        existing = await db.execute(select(Exam).where(Exam.access_token == new_token))
        if not existing.scalar_one_or_none():
            break
    else:
        raise HTTPException(status_code=500, detail="Gagal generate token baru")

    exam.access_token = new_token
    exam.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(exam)

    return ExamResponse.from_orm_with_wib(exam)


@router.post("/{exam_id}/start", response_model=ExamStartResponse)
async def start_exam_session(
    exam_id: int,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user_hot_path),
    db: AsyncSession = Depends(get_db)
):
    """Start an exam session (participant roles only)."""
    # Only participant roles can take exams.
    if not _is_exam_participant_role(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya peserta ujian yang dapat mengikuti ujian"
        )

    # Validate SEB
    await validate_seb_headers(request, exam_id, db, require_seb=True)
    exam_service = ExamService(db)
    exam = await exam_service.get_exam_with_settings(exam_id)

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    await _ensure_exam_start_option_integrity(db, exam_id)

    if not exam.is_published:
        raise HTTPException(status_code=400, detail="Ujian belum dipublikasikan")

    now = datetime.now(timezone.utc)
    if now < exam.start_time:
        raise HTTPException(status_code=400, detail="Ujian belum dimulai")
    if now > exam.end_time:
        raise HTTPException(status_code=400, detail="Ujian sudah berakhir")

    # Enforce the same participant access policy used by token join.
    exam_creator_role = await _get_exam_creator_role(db, exam.creator_id)
    _ensure_exam_participant_access(
        exam,
        current_user,
        exam_creator_role=exam_creator_role,
    )

    # Check max attempts with COUNT query (avoid loading full session history).
    completed_attempts_result = await db.execute(
        select(func.count(ExamSession.id)).where(
            ExamSession.user_id == current_user.id,
            ExamSession.exam_id == exam_id,
            ExamSession.status.in_(("completed", "submitted")),
        )
    )
    completed_attempts = int(completed_attempts_result.scalar() or 0)
    if completed_attempts >= exam.max_attempts:
        raise HTTPException(status_code=400, detail="Batas percobaan sudah tercapai")

    # Query only sessions relevant for resume/recovery decisions.
    existing_result = await db.execute(
        select(ExamSession)
        .where(
            ExamSession.user_id == current_user.id,
            ExamSession.exam_id == exam_id,
            ExamSession.status.in_(("in_progress", "active", "terminated", "kicked")),
        )
        .order_by(ExamSession.start_time.desc(), ExamSession.id.desc())
        .limit(16)
    )
    existing_sessions = existing_result.scalars().all()

    # Preload answer counts only for candidate resume sessions.
    answer_counts: Dict[int, int] = {}
    if len(existing_sessions) > 1:
        existing_session_ids = [s.id for s in existing_sessions]
        answer_count_result = await db.execute(
            select(Answer.session_id, func.count(Answer.id))
            .where(Answer.session_id.in_(existing_session_ids))
            .group_by(Answer.session_id)
        )
        answer_counts = {int(sid): int(cnt or 0) for sid, cnt in answer_count_result.all()}

    # Check for resumable session.
    # If duplicate active sessions exist due reconnect/race, prefer the one with most saved answers.
    resumable_sessions = [s for s in existing_sessions if s.status in ("in_progress", "active")]
    is_resumed_session = False
    session = None
    if resumable_sessions:
        is_resumed_session = True
        resumable_sessions.sort(
            key=lambda s: (
                answer_counts.get(s.id, 0),
                s.start_time or datetime.min.replace(tzinfo=timezone.utc),
                s.id
            ),
            reverse=True
        )
        session = resumable_sessions[0]
        logger.info(
            "EXAM_START | RESUME_SESSION | user=%s exam=%s session=%s answers=%s status=%s",
            current_user.id,
            exam_id,
            session.id,
            answer_counts.get(session.id, 0),
            session.status
        )
    else:
        # Auto-reset terminated sessions only when cause is network/disconnection.
        recoverable_sessions = [
            s for s in existing_sessions if s.status in ("terminated", "kicked")
        ]
        recoverable_sessions.sort(
            key=lambda s: (
                answer_counts.get(s.id, 0),
                s.start_time or datetime.min.replace(tzinfo=timezone.utc),
                s.id,
            ),
            reverse=True,
        )

        for candidate in recoverable_sessions:
            logs_result = await db.execute(
                select(ExamLog)
                .where(ExamLog.session_id == candidate.id)
                .order_by(ExamLog.created_at.desc(), ExamLog.id.desc())
                .limit(30)
            )
            recovery = evaluate_session_recovery(candidate, logs_result.scalars().all())
            if not recovery.get("allow_continue"):
                continue

            candidate.status = "in_progress"
            candidate.end_time = None
            candidate.terminated_by_admin = False
            candidate.emergency_exit_allowed = False
            db.add(
                ExamLog(
                    session_id=candidate.id,
                    event_type="SESSION_AUTO_RESET_NETWORK",
                    event_data={
                        "category": recovery.get("category"),
                        "message": recovery.get("message"),
                        "trigger": "start_exam_session",
                    },
                )
            )
            await db.commit()
            session = candidate
            is_resumed_session = True
            logger.warning(
                "EXAM_START | AUTO_RESET_SESSION | user=%s exam=%s session=%s category=%s",
                current_user.id,
                exam_id,
                candidate.id,
                recovery.get("category"),
            )
            break

    if session is None:
        # Create new session
        client_info = get_client_info(request)
        session = ExamSession(
            user_id=current_user.id,
            exam_id=exam_id,
            start_time=now,
            status="in_progress",
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            seb_detected=client_info["seb_detected"]
        )
        db.add(session)
        try:
            await db.flush()
            db.add(
                ExamLog(
                    session_id=session.id,
                    event_type="SESSION_START",
                    event_data={
                        "ip": client_info["ip_address"],
                        "seb_detected": client_info["seb_detected"],
                        "exam_snapshot": {
                            "title": exam.title,
                            "subject": exam.subject,
                            "exam_type": exam.exam_type,
                            "allowed_classes": exam.allowed_classes,
                            "allowed_students": exam.allowed_students,
                            "start_time": exam.start_time.isoformat() if exam.start_time else None,
                            "end_time": exam.end_time.isoformat() if exam.end_time else None,
                            "duration_minutes": exam.duration_minutes,
                        },
                    }
                )
            )
            await db.commit()
        except sqlalchemy.exc.IntegrityError as integrity_error:
            await db.rollback()

            race_result = await db.execute(
                select(ExamSession)
                .where(
                    ExamSession.user_id == current_user.id,
                    ExamSession.exam_id == exam_id,
                    ExamSession.status.in_(("in_progress", "active")),
                )
                .order_by(ExamSession.start_time.desc(), ExamSession.id.desc())
            )
            raced_session = race_result.scalar_one_or_none()
            if raced_session is None:
                logger.error(
                    "EXAM_START | ACTIVE_SESSION_RACE_MISS | user=%s exam=%s error=%s",
                    current_user.id,
                    exam_id,
                    str(integrity_error),
                )
                raise HTTPException(
                    status_code=409,
                    detail="Konflik saat memulai sesi ujian, silakan coba lagi.",
                )

            is_resumed_session = True
            session = raced_session
            logger.warning(
                "EXAM_START | ACTIVE_SESSION_RACE_RESUME | user=%s exam=%s session=%s",
                current_user.id,
                exam_id,
                session.id,
            )

    # Release any open read transaction before Redis calls.
    await db.commit()

    # Store session in Redis with idempotent timer data.
    # Do NOT overwrite started_at for an existing/resumed session.
    existing_redis_data = await get_session_data(session.id) if is_resumed_session else None
    started_at_iso = (
        (existing_redis_data or {}).get("started_at")
        or session.start_time.isoformat()
    )
    session_cache_data = {
        "user_id": current_user.id,
        "exam_id": exam_id,
        "start_time": session.start_time.isoformat(),
        "started_at": started_at_iso,
        "duration_seconds": exam.duration_minutes * 60,
        "elapsed_seconds": int((existing_redis_data or {}).get("elapsed_seconds") or 0),
        "paused": False,
        "duration_minutes": exam.duration_minutes,
        "status": "in_progress",
        "answered_count": int((existing_redis_data or {}).get("answered_count") or 0),
        "answered_count_stale": False,
        "total_questions": int((existing_redis_data or {}).get("total_questions") or 0),
        "violation_count": int(session.violation_count or 0),
    }
    total_paused_seconds = max(
        int((existing_redis_data or {}).get("total_paused_seconds") or 0),
        int(session.total_paused_seconds or 0),
    )
    if total_paused_seconds > 0:
        session_cache_data["total_paused_seconds"] = total_paused_seconds
    await store_session_data(session.id, session_cache_data)

    # Broadcast session start
    await _publish_exam_monitor_event(exam_id, {
        "type": "student_started",
        "user_id": current_user.id,
        "username": current_user.username,
        "session_id": session.id,
        "timestamp": now.isoformat()
    })

    # Build questions response from cached payload (without is_correct).
    questions_payload = await exam_service.get_questions_payload(exam_id)
    if not questions_payload:
        raise HTTPException(status_code=404, detail="Soal ujian tidak ditemukan")

    questions_list: List[SimpleNamespace] = []
    for raw_question in questions_payload:
        raw_options = raw_question.get("options") or []
        normalized_options = [
            SimpleNamespace(
                id=safe_int(raw_option.get("id")) or 0,
                option_text=raw_option.get("option_text"),
                order_index=safe_int(raw_option.get("order_index")) or 0,
                option_group=raw_option.get("option_group") or "standard",
                pair_id=raw_option.get("pair_id"),
            )
            for raw_option in raw_options
        ]

        questions_list.append(
            SimpleNamespace(
                id=safe_int(raw_question.get("id")) or 0,
                question_text=raw_question.get("question_text"),
                stimulus=raw_question.get("stimulus"),
                question_type=raw_question.get("question_type"),
                pgk_type=raw_question.get("pgk_type"),
                difficulty_level=raw_question.get("difficulty_level"),
                question_settings=raw_question.get("question_settings") or {},
                points=float(raw_question.get("points") or 0),
                order_index=safe_int(raw_question.get("order_index")) or 0,
                image_url=raw_question.get("image_url"),
                video_url=raw_question.get("video_url"),
                audio_url=raw_question.get("audio_url"),
                cached_options=normalized_options,
            )
        )

    questions_list.sort(key=lambda q: q.order_index)

    total_questions_from_payload = len(questions_list)
    if int(session_cache_data.get("total_questions") or 0) != total_questions_from_payload:
        session_cache_data["total_questions"] = total_questions_from_payload
        await store_session_data(session.id, session_cache_data)

    # Randomize questions if enabled (deterministic per student).
    if exam.shuffle_questions:
        def get_question_hash(q_id: int) -> int:
            seed_str = f"{settings.secret_key}_{current_user.id}_{exam.id}_question_{q_id}"
            return int(hashlib.md5(seed_str.encode()).hexdigest(), 16)

        questions_list.sort(key=lambda q: get_question_hash(q.id))

    questions: List[QuestionResponse] = []
    skipped_questions: List[Dict[str, Any]] = []

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "EXAM_START | exam=%s user=%s | loading %s questions from cached payload",
            exam_id,
            current_user.id,
            len(questions_list),
        )

    for q in questions_list:
        try:
            question_settings = dict(q.question_settings or {})
            question_text = (q.question_text or "").strip()
            placeholder_source = str(question_settings.get("placeholder_source") or "").strip().lower()
            is_placeholder_question = _is_placeholder_question(question_settings)
            is_image_placeholder = (
                is_placeholder_question
                and bool(q.image_url)
                and placeholder_source == "image"
            )

            # VALIDATION: Check required fields first
            if not question_text:
                if is_image_placeholder:
                    question_text = "Perhatikan gambar soal berikut, lalu pilih jawaban yang benar."
                    logger.warning(
                        "EXAM_START | Question %s uses image-placeholder fallback text",
                        q.id,
                    )
                else:
                    error_msg = f"Question {q.id} has NO QUESTION_TEXT"
                    logger.error(f"EXAM_START | {error_msg}")
                    skipped_questions.append({"id": q.id, "reason": "no_text"})
                    continue

            # VALIDATION: Check question has options (ONLY for types that require options)
            # Essay, short_answer, and PGK table_validation don't need options

            # Determine effective PGK type safely
            q_settings = q.question_settings or {}
            pgk_type = q.pgk_type or q_settings.get("pgk_type", "checkbox")
            is_table_validation = (q.question_type == "multiple_choice_complex" and pgk_type == "table_validation")

            requires_options = (
                q.question_type in ['multiple_choice', 'multiple_choice_complex', 'true_false']
                and not is_table_validation
            )
            question_options = list(getattr(q, "cached_options", []) or [])

            if requires_options and not question_options:
                error_msg = f"Question {q.id} (type: {q.question_type}) has NO OPTIONS"
                logger.error(f"EXAM_START | {error_msg}")
                skipped_questions.append({"id": q.id, "text": q.question_text[:50], "reason": "no_options", "type": q.question_type})
                continue

            # Build options (only for question types that have options)
            options = []
            should_shuffle = bool(exam.shuffle_options)  # Define outside the if block for use later

            if requires_options:
                options_list = sorted(question_options, key=lambda x: x.order_index)

                # Placeholder options are shuffled only when explicitly allowed by builder
                # and never for image-driven placeholders.
                is_placeholder = is_placeholder_question
                can_shuffle_placeholder = _can_shuffle_placeholder_options(
                    question_settings,
                    has_image=bool(q.image_url)
                )

                if should_shuffle and (not is_placeholder or can_shuffle_placeholder):
                    seed_str = f"{settings.secret_key}_{current_user.id}_{exam.id}_question_{q.id}_options"
                    options_list = _stable_shuffle_with_seed(options_list, seed_str)

                options = [
                    QuestionOptionResponse(
                        id=opt.id,
                        option_text=opt.option_text,
                        order_index=opt.order_index,
                        option_group=opt.option_group or "standard",
                        pair_id=opt.pair_id
                    )
                    for opt in options_list
                ]

            # Prepare question settings (handle Table Validation shuffling)
            # Determine PGK type (fallback to settings if not in column)
            pgk_type = q.pgk_type or question_settings.get("pgk_type", "checkbox")
            is_table_validation = (
                q.question_type == "multiple_choice_complex" and pgk_type == "table_validation"
            )
            table_statement_shuffle_allowed = bool(
                question_settings.get("allow_table_statement_shuffle", True)
            ) if is_table_validation else False
            if is_table_validation:
                question_settings["allow_table_statement_shuffle"] = table_statement_shuffle_allowed

            # Shuffle statements for Table Validation if enabled
            if should_shuffle and is_table_validation and table_statement_shuffle_allowed:
                statements = question_settings.get("statements", [])
                if statements:
                    # Do NOT shuffle when statements are image-driven/placeholder,
                    # because row text does not uniquely identify statement order.
                    normalized_texts = []
                    for s in statements:
                        if isinstance(s, dict):
                            text = str(s.get("text", "")).strip()
                        else:
                            text = str(s).strip()
                        normalized_texts.append(text)

                    informative_texts = [
                        t for t in normalized_texts
                        if t and t not in {"-", "--", "—", "–"}
                    ]
                    has_meaningful_statement_text = len(set(informative_texts)) >= 2
                    is_image_mode = bool(q.image_url)

                    if has_meaningful_statement_text and not is_image_mode:
                        # Create indexed objects to preserve original mapping
                        indexed_stmts = [{"text": s, "original_index": i} for i, s in enumerate(statements)]

                        # Use stable hash for consistent order
                        seed_str = f"{settings.secret_key}_{current_user.id}_{exam.id}_question_{q.id}_statements"
                        indexed_stmts = _stable_shuffle_with_seed(indexed_stmts, seed_str)

                        # Update settings with shuffled objects
                        question_settings["statements"] = indexed_stmts

            questions.append(QuestionResponse(
                id=q.id,
                question_text=question_text,
                stimulus=q.stimulus,
                question_type=q.question_type,
                pgk_type=q.pgk_type,
                difficulty_level=q.difficulty_level or "medium",
                category=None,
                tags=[],
                question_settings=question_settings,
                points=q.points,
                order_index=q.order_index,
                image_url=q.image_url,
                video_url=q.video_url,
                audio_url=q.audio_url,
                options=options
            ))

        except Exception as e:
            logger.error(f"EXAM_START | Question {q.id} FAILED to build: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            skipped_questions.append({"id": q.id, "text": getattr(q, 'question_text', 'N/A')[:50], "reason": "exception", "error": str(e)})
            continue

    # VALIDATION: Check final question count
    expected_count = len(questions_list)
    actual_count = len(questions)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "EXAM_START | exam=%s user=%s | built %s/%s questions",
            exam_id,
            current_user.id,
            actual_count,
            expected_count,
        )

    if skipped_questions:
        logger.error(f"EXAM_START | SKIPPED {len(skipped_questions)} questions: {skipped_questions}")

    if actual_count < expected_count:
        logger.error(f"EXAM_START | QUESTION COUNT MISMATCH! Expected {expected_count}, got {actual_count}")
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memuat {expected_count - actual_count} soal dari ujian. Data ujian tidak lengkap. Silakan hubungi pengawas atau administrator."
        )

    return ExamStartResponse(
        session_id=session.id,
        exam_id=exam.id,
        exam_title=exam.title,
        duration_minutes=exam.duration_minutes,
        question_count=len(questions),
        start_time=session.start_time,
        end_time=session.start_time + timedelta(minutes=exam.duration_minutes),
        server_time=datetime.now(timezone.utc),
        show_results=exam.show_results,
        show_teacher_name=exam.show_teacher_name if exam.show_teacher_name is not None else True,
        teacher_name=exam.creator.full_name if (exam.show_teacher_name and exam.creator) else None,
        subject=exam.subject,
        exam_type=exam.exam_type,
        shuffle_questions=bool(exam.shuffle_questions),
        shuffle_options=bool(exam.shuffle_options),
        session_poll_token=create_session_poll_token(
            session_id=session.id,
            user_id=current_user.id,
            expires_minutes=SESSION_POLL_TOKEN_EXPIRES_MINUTES,
        ),
        session_poll_token_expires_minutes=SESSION_POLL_TOKEN_EXPIRES_MINUTES,
        questions=questions
    )


# ============== SPRINT 1.3: NEW ENDPOINTS ==============


@router.post("/from-template", response_model=ExamResponse)
async def create_exam_from_template(
    template_id: int,
    start_time: datetime,
    end_time: datetime,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Create a new exam from a template."""
    # Fetch template
    result = await db.execute(select(ExamTemplate).where(ExamTemplate.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(404, "Template not found")

    data = template.template_data

    # Create Exam
    new_exam = Exam(
        title=data.get('title', 'Untitled Exam'),
        description=data.get('description'),
        creator_id=current_user.id,
        duration_minutes=data.get('duration_minutes', 60),
        start_time=start_time,
        end_time=end_time,
        passing_score=data.get('passing_score', 0),
        max_attempts=data.get('max_attempts', 1),
        shuffle_questions=data.get('shuffle_questions', False),
        shuffle_options=data.get('shuffle_options', False),
        show_results=data.get('show_results', False),  # FIX: Default to False to match checkbox default
        allow_review=data.get('allow_review', False),
        builder_settings=data.get('builder_settings', {}),
        seb_config_key=secrets.token_urlsafe(32),
        seb_browser_exam_key=secrets.token_urlsafe(32),
        is_published=False,
        access_token=secrets.token_hex(3).upper(),  # Temporary basic token
        allowed_classes=None
    )

    db.add(new_exam)
    await db.commit()
    await db.refresh(new_exam)

    # Copy questions (simplified logic, assumes template_data has questions structure)
    # Ideally templates should store question prototypes.
    # For now, if template_data has 'questions', we implement basic copying.
    # Implementation deferred/simplified for brevity as templates usually need robust structure.

    return ExamResponse.from_orm_with_wib(new_exam)


@router.post("/{exam_id}/duplicate", response_model=ExamResponse)
async def duplicate_exam(
    exam_id: int,
    include_questions: bool = True,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Duplicate an existing exam."""
    # Fetch original
    result = await db.execute(
        select(Exam)
        .options(selectinload(Exam.questions).selectinload(Question.options))
        .where(Exam.id == exam_id)
    )
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(404, "Original exam not found")
    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        original.creator_id,
    )

    # Create Copy
    new_exam = Exam(
        title=f"{original.title} (Copy)",
        description=original.description,
        creator_id=current_user.id,
        duration_minutes=original.duration_minutes,
        start_time=original.start_time,
        end_time=original.end_time,
        passing_score=original.passing_score,
        max_attempts=original.max_attempts,
        shuffle_questions=original.shuffle_questions,
        shuffle_options=original.shuffle_options,
        show_results=original.show_results,
        allow_review=original.allow_review,
        builder_settings=original.builder_settings or {},
        seb_config_key=secrets.token_urlsafe(32),
        seb_browser_exam_key=secrets.token_urlsafe(32),
        is_published=False,
        access_token=secrets.token_hex(3).upper(),
        allowed_classes=original.allowed_classes
    )

    db.add(new_exam)
    await db.commit()
    await db.refresh(new_exam)

    # Duplicate Questions
    if include_questions and original.questions:
        for q in original.questions:
            new_q = Question(
                exam_id=new_exam.id,
                question_text=q.question_text,
                question_type=q.question_type,
                question_subtype=q.question_subtype,
                pgk_type=q.pgk_type,
                stimulus=q.stimulus,
                question_settings=q.question_settings,
                points=q.points,
                order_index=q.order_index,
                image_url=q.image_url,
                video_url=q.video_url,
                audio_url=q.audio_url
            )
            db.add(new_q)
            await db.flush() # Get ID

            # Duplicate Options
            for opt in q.options:
                new_opt = QuestionOption(
                    question_id=new_q.id,
                    option_text=opt.option_text,
                    is_correct=opt.is_correct,
                    order_index=opt.order_index,
                    option_group=opt.option_group,
                    pair_id=opt.pair_id,
                    option_metadata=opt.option_metadata
                )
                db.add(new_opt)

        await db.commit()

    return ExamResponse.from_orm_with_wib(new_exam)


@router.get("/{exam_id}/analytics", response_model=ExamAnalytics)
async def get_exam_analytics(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive analytics for an exam."""
    # First, check if exam exists and user has access
    exam_check = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam_data = exam_check.scalar_one_or_none()

    if not exam_data:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam_data.creator_id,
    )

    # Gather Stats
    # 1. Sessions
    sessions_result = await db.execute(select(ExamSession).where(ExamSession.exam_id == exam_id))
    sessions = sessions_result.scalars().all()

    if not sessions:
        return ExamAnalytics(
            exam_id=exam_id,
            total_participants=0,
            active_sessions=0,
            completed_sessions=0,
            average_score=0,
            highest_score=0,
            lowest_score=0,
            pass_rate=0,
            score_distribution={},
            difficult_questions=[],
            violation_stats={}
        )

    total = len(sessions)
    completed = [s for s in sessions if s.status in ('completed', 'submitted')]
    active = [s for s in sessions if s.status == 'in_progress']

    # Scores
    scores = [float(s.score) for s in completed if s.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0
    max_score = max(scores) if scores else 0
    min_score = min(scores) if scores else 0

    # Pass Rate
    exam_res = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_res.scalar_one()
    passing_score = float(exam.passing_score or 0)
    passed_count = len([s for s in scores if s >= passing_score]) if exam.passing_score else len(scores)
    pass_rate = (passed_count / len(completed) * 100) if completed else 0

    # Distribution
    dist = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for s in scores:
        if s <= 20: dist["0-20"] += 1
        elif s <= 40: dist["21-40"] += 1
        elif s <= 60: dist["41-60"] += 1
        elif s <= 80: dist["61-80"] += 1
        else: dist["81-100"] += 1

    # Violations (Basic aggregation)
    violations = sum([s.violation_count for s in sessions if s.violation_count])

    return ExamAnalytics(
        exam_id=exam_id,
        total_participants=total,
        active_sessions=len(active),
        completed_sessions=len(completed),
        average_score=round(avg_score, 2),
        highest_score=max_score,
        lowest_score=min_score,
        pass_rate=round(pass_rate, 2),
        score_distribution=dist,
        difficult_questions=[], # Requires deeper query on Answer table
        violation_stats={"total_violations": violations}
    )


@router.get("/{exam_id}/preview", response_model=ExamStartResponse)
async def preview_exam(
    exam_id: int,
    simulate_student_shuffle: bool = Query(
        default=False,
        description="Simulasikan urutan acak seperti saat siswa memulai ujian"
    ),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Preview exam as a teacher (no SEB check, no session recording)."""
    # Fetch complete exam
    result = await db.execute(
        select(Exam)
        .options(selectinload(Exam.questions).selectinload(Question.options))
        .where(Exam.id == exam_id)
    )
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(404, "Exam not found")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
    )
    start_time = datetime.now(timezone.utc)

    questions_list = sorted(exam.questions, key=lambda x: x.order_index)
    if simulate_student_shuffle and exam.shuffle_questions:
        def get_question_hash(q_id: int) -> int:
            seed_str = f"{settings.secret_key}_{current_user.id}_{exam.id}_question_{q_id}"
            return int(hashlib.md5(seed_str.encode()).hexdigest(), 16)

        questions_list.sort(key=lambda q: get_question_hash(q.id))

    # Build questions
    questions = []
    for q in questions_list:
        question_settings = dict(q.question_settings or {})
        pgk_type = q.pgk_type or question_settings.get("pgk_type", "checkbox")
        is_table_validation = (
            q.question_type == "multiple_choice_complex" and pgk_type == "table_validation"
        )
        table_statement_shuffle_allowed = bool(
            question_settings.get("allow_table_statement_shuffle", True)
        ) if is_table_validation else False
        if is_table_validation:
            question_settings["allow_table_statement_shuffle"] = table_statement_shuffle_allowed
        requires_options = q.question_type in [
            "multiple_choice",
            "multiple_choice_complex",
            "true_false"
        ] and not is_table_validation

        should_shuffle_options = bool(simulate_student_shuffle and exam.shuffle_options)
        options = []
        if requires_options:
            options_list = sorted(q.options, key=lambda x: x.order_index)
            is_placeholder = _is_placeholder_question(q.question_settings)
            can_shuffle_placeholder = _can_shuffle_placeholder_options(
                q.question_settings,
                has_image=bool(q.image_url)
            )
            if should_shuffle_options and (not is_placeholder or can_shuffle_placeholder):
                seed_str = f"{settings.secret_key}_{current_user.id}_{exam.id}_question_{q.id}_options"
                options_list = _stable_shuffle_with_seed(options_list, seed_str)

            options = [
                QuestionOptionResponse(
                    id=opt.id,
                    option_text=opt.option_text,
                    order_index=opt.order_index,
                    option_group=opt.option_group or "standard",
                    pair_id=opt.pair_id
                )
                for opt in options_list
            ]

        if should_shuffle_options and is_table_validation and table_statement_shuffle_allowed:
            statements = question_settings.get("statements", [])
            if statements:
                normalized_texts = []
                for statement in statements:
                    if isinstance(statement, dict):
                        text = str(statement.get("text", "")).strip()
                    else:
                        text = str(statement).strip()
                    normalized_texts.append(text)

                informative_texts = [
                    text for text in normalized_texts
                    if text and text not in {"-", "--", "—", "–"}
                ]
                has_meaningful_statement_text = len(set(informative_texts)) >= 2
                is_image_mode = bool(q.image_url)

                if has_meaningful_statement_text and not is_image_mode:
                    indexed_stmts = [
                        {"text": statement, "original_index": i}
                        for i, statement in enumerate(statements)
                    ]
                    seed_str = f"{settings.secret_key}_{current_user.id}_{exam.id}_question_{q.id}_statements"
                    indexed_stmts = _stable_shuffle_with_seed(indexed_stmts, seed_str)
                    question_settings["statements"] = indexed_stmts

        questions.append(QuestionResponse(
            id=q.id,
            question_text=q.question_text,
            stimulus=q.stimulus,
            question_type=q.question_type,
            pgk_type=q.pgk_type,
            points=q.points,
            order_index=q.order_index,
            image_url=q.image_url,
            video_url=q.video_url,
            audio_url=q.audio_url,
            question_settings=question_settings,
            options=options
        ))

    return ExamStartResponse(
        session_id=0, # Dummy ID
        exam_id=exam.id,
        exam_title=(
            f"[SIMULASI SISWA] {exam.title}"
            if simulate_student_shuffle
            else f"[PREVIEW] {exam.title}"
        ),
        duration_minutes=exam.duration_minutes,
        question_count=len(questions),
        start_time=start_time,
        end_time=start_time + timedelta(minutes=exam.duration_minutes),
        server_time=datetime.now(timezone.utc),  # Server time for preview consistency
        show_results=exam.show_results if exam.show_results is not None else True,
        show_teacher_name=exam.show_teacher_name if exam.show_teacher_name is not None else True,
        teacher_name=exam.creator.full_name if exam.creator else None,
        subject=exam.subject,  # FIX: Include exam metadata for preview
        exam_type=exam.exam_type,  # FIX: Include exam type for preview
        shuffle_questions=bool(exam.shuffle_questions),
        shuffle_options=bool(exam.shuffle_options),
        questions=questions
    )



@router.post("/submit-answer", response_model=AnswerResponse)
async def submit_answer(
    answer_data: AnswerSubmit,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user_hot_path),
    db: AsyncSession = Depends(get_db)
):
    """Submit a single answer."""
    # Rate limit check (30 requests/minute per session)
    session_key = f"{current_user.id}:{answer_data.session_id}"
    is_allowed, remaining = await check_rate_limit(RateLimiters.ANSWER_SUBMIT, session_key)
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail="Terlalu banyak request. Tunggu beberapa saat.",
            headers={"Retry-After": "5", "X-RateLimit-Remaining": str(remaining)}
        )

    session_id = int(answer_data.session_id)
    try:
        session_row_result = await db.execute(
            select(
                ExamSession.id,
                ExamSession.exam_id,
                ExamSession.status,
            ).where(
                ExamSession.id == session_id,
                ExamSession.user_id == current_user.id,
            )
        )
    except (sqlalchemy.exc.TimeoutError, sqlalchemy.exc.DBAPIError) as exc:
        logger.warning(
            "SUBMIT-ANSWER | session=%s | transient DB read pressure: %s",
            session_id,
            str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail="Server sedang sibuk, silakan ulangi kirim jawaban.",
            headers={"Retry-After": "1"},
        )

    session_row = session_row_result.first()
    if session_row is None:
        raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan")

    exam_id = int(session_row[1])
    session_status = str(session_row[2] or "").strip().lower()

    if session_status != "in_progress":
        # Idempotent/no-op for retry races after successful submit.
        if session_status in {"submitted", "completed"}:
            return AnswerResponse(
                status="saved",
                question_id=answer_data.question_id,
                message="Sesi ujian sudah dikumpulkan. Jawaban tambahan diabaikan.",
            )
        raise HTTPException(status_code=400, detail="Sesi ujian sudah berakhir")

    # Validate SEB
    await validate_seb_headers(request, exam_id, db, require_seb=True)

    # Get question validation payload (local cache first) and validate.
    try:
        question_payload = await _get_question_validation_payload_cached(
            db,
            exam_id=exam_id,
            question_id=answer_data.question_id,
        )
    except (sqlalchemy.exc.TimeoutError, sqlalchemy.exc.DBAPIError) as exc:
        logger.warning(
            "SUBMIT-ANSWER | Q%s | transient DB question read pressure: %s",
            answer_data.question_id,
            str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail="Server sedang sibuk, silakan ulangi kirim jawaban.",
            headers={"Retry-After": "1"},
        )

    if not question_payload:
        raise HTTPException(status_code=404, detail="Soal tidak ditemukan")

    question_id = int(question_payload["id"])
    question_type = str(question_payload.get("question_type") or "")
    question_pgk_type = question_payload.get("pgk_type")
    question_max_points = float(question_payload.get("points") or 0.0)

    # Build final metadata from incoming payload only, then persist with UPSERT.
    incoming_metadata = dict(answer_data.answer_metadata or {})
    merged_statement_answers = answer_data.statement_answers
    final_metadata, _ = merge_statement_answer_metadata(
        existing_metadata={},
        incoming_metadata=incoming_metadata,
        incoming_statement_answers=merged_statement_answers,
    )

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "SUBMIT-ANSWER | Q%s (%s) | pgk_type=%s",
            question_id,
            question_type,
            question_pgk_type,
        )

    has_answer = (
        answer_data.selected_option_id is not None or
        (answer_data.selected_option_ids is not None and len(answer_data.selected_option_ids) > 0) or
        (answer_data.answer_text is not None and answer_data.answer_text.strip() != '') or
        (merged_statement_answers is not None and len(merged_statement_answers) > 0)
    )

    if not has_answer:
        logger.warning(f"SUBMIT-ANSWER | Q{question_id} | Tidak ada data jawaban yang valid!")

    try:
        is_correct, points_earned = _validate_answer_with_cached_payload(
            question_payload,
            selected_option_id=answer_data.selected_option_id,
            selected_option_ids=answer_data.selected_option_ids,
            answer_text=answer_data.answer_text,
            statement_answers=merged_statement_answers,
        )
    except Exception as e:
        logger.error(
            "SUBMIT-ANSWER | Q%s | Error saat validasi: %s",
            question_id,
            str(e),
            exc_info=True
        )
        is_correct = False
        points_earned = 0.0

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "SUBMIT-ANSWER | Q%s validation result | is_correct=%s points_earned=%s max_points=%s",
            question_id,
            is_correct,
            points_earned,
            question_max_points,
        )

    write_timestamp = datetime.now(timezone.utc)
    write_fields = {
        "selected_option_id": answer_data.selected_option_id,
        "selected_option_ids": answer_data.selected_option_ids,
        "answer_text": answer_data.answer_text,
        "answer_metadata": final_metadata,
        "is_correct": is_correct,
        "points_earned": points_earned,
        "answered_at": write_timestamp,
    }
    answered_count_runtime: Optional[int] = None
    persisted_via_queue = False

    try:
        if _answer_write_mode() == "queue":
            queue_payload = {
                "session_id": session_id,
                "exam_id": exam_id,
                "user_id": current_user.id,
                "question_id": question_id,
                "selected_option_id": answer_data.selected_option_id,
                "selected_option_ids": answer_data.selected_option_ids,
                "answer_text": answer_data.answer_text,
                "statement_answers": merged_statement_answers,
                "answer_metadata": final_metadata,
                "is_correct": is_correct,
                "points_earned": points_earned,
                "answered_at": write_timestamp.isoformat(),
            }
            try:
                await enqueue_answer_payload(queue_payload)
                persisted_via_queue = True
            except Exception as queue_exc:
                logger.warning(
                    "SUBMIT-ANSWER | session=%s Q%s | queue enqueue failed, fallback direct write: %s",
                    session_id,
                    question_id,
                    str(queue_exc),
                )

        if not persisted_via_queue:
            upsert_stmt = (
                pg_insert(Answer)
                .values(
                    session_id=session_id,
                    question_id=question_id,
                    **write_fields,
                )
                .on_conflict_do_update(
                    index_elements=[Answer.session_id, Answer.question_id],
                    set_=write_fields,
                )
            )
            try:
                await db.execute(upsert_stmt)
            except sqlalchemy.exc.DBAPIError as upsert_exc:
                # Fallback for legacy deployments that lack unique index
                # on (session_id, question_id).
                if "no unique or exclusion constraint" not in str(upsert_exc).lower():
                    raise
                await db.execute(
                    text("SELECT pg_advisory_xact_lock(:session_id, :question_id)"),
                    {"session_id": session_id, "question_id": question_id},
                )
                update_stmt = (
                    update(Answer)
                    .where(
                        Answer.session_id == session_id,
                        Answer.question_id == question_id,
                    )
                    .values(**write_fields)
                )
                update_result = await db.execute(update_stmt)
                if (update_result.rowcount or 0) == 0:
                    db.add(
                        Answer(
                            session_id=session_id,
                            question_id=question_id,
                            **write_fields,
                        )
                    )
            await db.commit()

        _invalidate_session_answer_count_cache(session_id)
        try:
            answered_count_runtime = await _add_answered_questions_and_count(
                session_id,
                [question_id],
            )
            if answered_count_runtime is not None:
                await _update_runtime_snapshot_answered_count(
                    session_id,
                    expected_user_id=current_user.id,
                    answered_count=answered_count_runtime,
                    mark_stale=False,
                    status="in_progress",
                )
            else:
                cached_session_data = await get_session_data(session_id)
                if cached_session_data and safe_int(cached_session_data.get("user_id")) == current_user.id:
                    cached_session_data["answered_count_stale"] = True
                    await store_session_data(session_id, cached_session_data)
        except Exception as cache_exc:
            logger.debug(
                "SUBMIT-ANSWER | session=%s | failed to refresh runtime answered_count: %s",
                session_id,
                str(cache_exc),
            )
    except HTTPException as exc:
        await db.rollback()
        if exc.status_code == 400:
            detail_text = str(exc.detail).lower()
            if "sudah berakhir" in detail_text or "sudah dikumpulkan" in detail_text:
                return AnswerResponse(
                    status="saved",
                    question_id=question_id,
                    message="Sesi ujian sudah dikumpulkan. Jawaban tambahan diabaikan.",
                )
        raise
    except Exception as exc:
        await db.rollback()
        if isinstance(exc, (sqlalchemy.exc.TimeoutError, sqlalchemy.exc.DBAPIError)):
            logger.warning(
                "SUBMIT-ANSWER | Q%s | transient DB write pressure: %s",
                question_id,
                str(exc),
            )
            raise HTTPException(
                status_code=503,
                detail="Server sedang sibuk, silakan ulangi kirim jawaban.",
                headers={"Retry-After": "1"},
            )
        logger.error(
            "SUBMIT-ANSWER | Q%s | upsert failed: %s",
            question_id,
            str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=409, detail="Konflik penyimpanan jawaban, silakan coba lagi")

    # Progress broadcast is throttled to reduce DB pressure on hot path.
    if _should_publish_progress_update(session_id):
        total_questions = await _get_exam_question_count_cached(db, exam_id)
        answered_count: Optional[int] = answered_count_runtime
        if answered_count is None:
            try:
                answered_count = await _get_answered_count_from_set(session_id)
            except Exception as runtime_exc:
                logger.debug(
                    "SUBMIT-ANSWER | session=%s | failed reading answered_count set: %s",
                    session_id,
                    str(runtime_exc),
                )
        if answered_count is None:
            answered_result = await db.execute(
                select(func.count(func.distinct(Answer.question_id))).where(
                    Answer.session_id == session_id,
                    _answer_has_meaningful_content_clause(),
                )
            )
            answered_count = int(answered_result.scalar() or 0)
        progress = (answered_count / total_questions * 100) if total_questions > 0 else 0.0

        # End DB transaction before Redis publish to avoid long idle-in-transaction windows.
        await db.commit()

        try:
            await _publish_exam_monitor_event(exam_id, {
                "type": "progress_update",
                "user_id": current_user.id,
                "exam_id": exam_id,
                "session_id": session_id,
                "progress": round(progress, 2),
                "answered_count": answered_count,
                "total_questions": total_questions,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.warning(f"Failed to broadcast progress update: {e}")

    # NOTE: Response does NOT include is_correct!
    return AnswerResponse(
        status="saved",
        question_id=question_id,
        message="Jawaban berhasil disimpan"
    )


@router.get("/session/{session_id}/offline-package")
async def get_offline_exam_package(
    session_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user_hot_path),
    db: AsyncSession = Depends(get_db_read),
    exam_service: ExamService = Depends(get_exam_service_read),
):
    """
    Build a signed offline package snapshot for resilient mobile exam runtime.

    Package includes current timer state, latest saved answers, and question
    payload (without answer keys/correctness). Signature allows client-side
    integrity checks before using cached data while offline.
    """
    result = await db.execute(
        select(ExamSession)
        .options(
            selectinload(ExamSession.exam).selectinload(Exam.creator),
            selectinload(ExamSession.answers),
        )
        .where(
            ExamSession.id == session_id,
            ExamSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan")

    if session.status not in ["in_progress", "active"]:
        raise HTTPException(
            status_code=409,
            detail="Paket offline hanya tersedia untuk sesi ujian aktif",
        )

    answered_count = await _get_session_answer_count_cached(db, session.id)
    total_questions = await _get_exam_question_count_cached(db, session.exam_id)

    await db.commit()
    redis_data = await get_session_data(session.id)
    started_at, total_seconds, total_paused = resolve_timer_context(session, redis_data)
    elapsed_seconds, remaining_seconds = calculate_effective_timer(
        started_at=started_at,
        total_seconds=total_seconds,
        total_paused_seconds=total_paused,
    )
    is_expired = remaining_seconds <= 0

    questions_payload = await exam_service.get_questions_payload(session.exam_id)
    if not questions_payload:
        raise HTTPException(status_code=404, detail="Soal ujian tidak ditemukan")

    saved_answers: Dict[str, Any] = {}
    for answer in session.answers:
        question_id = str(answer.question_id)
        metadata = dict(answer.answer_metadata or {})
        if metadata.get("statement_answers"):
            saved_answers[question_id] = metadata.get("statement_answers")
        elif answer.selected_option_ids:
            saved_answers[question_id] = answer.selected_option_ids
        elif answer.answer_text is not None and answer.answer_text.strip():
            saved_answers[question_id] = answer.answer_text
        elif answer.selected_option_id is not None:
            saved_answers[question_id] = answer.selected_option_id

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=OFFLINE_PACKAGE_TTL_SECONDS)

    package_payload: Dict[str, Any] = {
        "session": {
            "session_id": session.id,
            "exam_id": session.exam_id,
            "status": session.status,
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "time_remaining_seconds": remaining_seconds,
            "elapsed_seconds": elapsed_seconds,
            "total_seconds": total_seconds,
            "is_expired": is_expired,
            "violation_count": int(session.violation_count or 0),
            "emergency_exit_allowed": bool(session.emergency_exit_allowed),
        },
        "exam": {
            "title": session.exam.title,
            "duration_minutes": int(session.exam.duration_minutes or 0),
            "start_time": session.exam.start_time.isoformat() if session.exam.start_time else None,
            "end_time": session.exam.end_time.isoformat() if session.exam.end_time else None,
            "show_results": bool(session.exam.show_results),
            "show_teacher_name": bool(session.exam.show_teacher_name),
            "teacher_name": session.exam.creator.full_name if session.exam.creator else None,
            "shuffle_questions": bool(session.exam.shuffle_questions),
            "shuffle_options": bool(session.exam.shuffle_options),
            # Backward-compatible fallback:
            # Some deployments do not have `show_exam_timer` as a persisted Exam field.
            # Keep offline package generation resilient by defaulting to timer visible.
            "show_exam_timer": bool(getattr(session.exam, "show_exam_timer", True)),
        },
        "progress": {
            "answered_count": answered_count,
            "total_questions": total_questions,
            "saved_answers": saved_answers,
            "last_question_id": max(
                (int(question_id) for question_id in saved_answers.keys()),
                default=None,
            ),
        },
        "questions": questions_payload,
        "runtime_policy": {
            "auto_save_interval_ms": 30000,
            "answer_sync_debounce_ms": 5000,
            "offline_first": True,
        },
    }

    signature = _sign_offline_package_payload(session.id, package_payload)
    package_hash = hashlib.sha256(
        json.dumps(
            package_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    return {
        "status": "ok",
        "package_id": f"offline-{session.id}-{package_hash[:12]}",
        "signature": signature,
        "signature_algorithm": "HMAC-SHA256",
        "package_hash": package_hash,
        "ttl_seconds": OFFLINE_PACKAGE_TTL_SECONDS,
        "server_time": issued_at.isoformat(),
        "payload": package_payload,
    }


def _is_transient_db_pressure_error(exc: Exception) -> bool:
    if isinstance(exc, sqlalchemy.exc.TimeoutError):
        return True
    if isinstance(exc, sqlalchemy.exc.DBAPIError):
        if bool(getattr(exc, "connection_invalidated", False)):
            return True
        message = str(exc).lower()
        transient_markers = (
            "queuepool limit",
            "connection was closed in the middle of operation",
            "too many clients already",
            "canceling statement due to statement timeout",
            "could not serialize access due to concurrent update",
        )
        return any(marker in message for marker in transient_markers)
    return False


def _build_already_submitted_response(
    *,
    session_id: int,
    score: Optional[float],
    show_results: Optional[bool],
    passing_score: Optional[float],
) -> ExamSubmitResponse:
    resolved_show_results = show_results if show_results is not None else True
    passed = None
    if resolved_show_results and score is not None and passing_score is not None:
        passed = float(score) >= float(passing_score)
    return ExamSubmitResponse(
        session_id=session_id,
        status="submitted",
        score=float(score) if resolved_show_results and score is not None else None,
        total_points=None,
        points_earned=None,
        percentage=float(score) if resolved_show_results and score is not None else None,
        passed=passed if resolved_show_results else None,
        message="Sesi sudah pernah dikumpulkan.",
    )


@router.post("/submit", response_model=ExamSubmitResponse)
async def submit_exam(
    submit_data: ExamSubmitRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user_hot_path),
    db: AsyncSession = Depends(get_db)
):
    """Submit entire exam via priority FinalSubmitService."""
    service = get_final_submit_service(db, current_user)
    return await service.submit_exam(submit_data, request)



def _ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ignored_violation_response(violation_count: int) -> ViolationResponse:
    return ViolationResponse(
        status="ignored",
        violation_count=max(0, int(violation_count or 0)),
        warning=None,
    )


@router.post("/log-violation", response_model=ViolationResponse, status_code=status.HTTP_202_ACCEPTED)
async def log_violation(
    violation_data: ViolationLog,
    current_user: AuthenticatedUser = Depends(get_current_user_hot_path),
    db: AsyncSession = Depends(get_db)
):
    """Log a cheating violation."""
    if settings.violation_async_enabled:
        enqueue_result = await enqueue_violation_event(db, violation_data, current_user)
        return enqueue_result.to_response()

    active_session_statuses = ("in_progress", "active", "paused")
    terminal_session_statuses = {"submitted", "completed", "abandoned", "terminated", "kicked"}

    violation_payload = dict(violation_data.event_data or {})
    reported_at = _ensure_aware_utc(violation_data.timestamp or datetime.now(timezone.utc))
    normalized_event_type = canonical_violation_event_type(
        violation_data.event_type,
        violation_payload,
        assume_violation=True,
    )
    if not normalized_event_type:
        raise HTTPException(status_code=400, detail="Jenis pelanggaran tidak valid")

    session_state_result = await db.execute(
        select(
            ExamSession.id,
            ExamSession.exam_id,
            ExamSession.violation_count,
            ExamSession.status,
            ExamSession.end_time,
        ).where(
            ExamSession.id == violation_data.session_id,
            ExamSession.user_id == current_user.id,
        )
    )
    session_state = session_state_result.mappings().one_or_none()

    if not session_state:
        raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan")

    if is_violation_event_disabled(normalized_event_type):
        logger.info(
            "Ignored disabled violation event session_id=%s event_type=%s",
            violation_data.session_id,
            normalized_event_type,
        )
        return _ignored_violation_response(session_state["violation_count"])

    session_status = str(session_state["status"] or "")
    if session_status in terminal_session_statuses:
        logger.info(
            "Ignored violation for closed session session_id=%s status=%s event_type=%s",
            violation_data.session_id,
            session_status,
            normalized_event_type,
        )
        return _ignored_violation_response(session_state["violation_count"])

    session_end_time = session_state["end_time"]
    if session_end_time is not None:
        if session_end_time.tzinfo is None:
            session_end_time = session_end_time.replace(tzinfo=timezone.utc)
        # Guard late/queued focus events fired on submit transition.
        if reported_at >= (session_end_time - timedelta(seconds=5)):
            logger.info(
                "Ignored late violation near submit session_id=%s status=%s event_type=%s",
                violation_data.session_id,
                session_status,
                normalized_event_type,
            )
            return _ignored_violation_response(session_state["violation_count"])

    should_count_for_score, counting_policy = await should_count_violation_for_score(
        db,
        session_id=int(session_state["id"]),
        normalized_event_type=normalized_event_type,
        violation_payload=violation_payload,
        reported_at=reported_at,
    )
    increment_value = 1 if should_count_for_score else 0

    session_update = await db.execute(
        update(ExamSession)
        .where(
            ExamSession.id == violation_data.session_id,
            ExamSession.user_id == current_user.id,
            ExamSession.status.in_(active_session_statuses),
        )
        .values(
            violation_count=func.coalesce(ExamSession.violation_count, 0) + increment_value
        )
        .returning(
            ExamSession.id,
            ExamSession.exam_id,
            ExamSession.violation_count,
        )
    )
    session_row = session_update.mappings().one_or_none()

    if not session_row:
        latest_state_result = await db.execute(
            select(ExamSession.violation_count, ExamSession.status).where(
                ExamSession.id == violation_data.session_id,
                ExamSession.user_id == current_user.id,
            )
        )
        latest_state = latest_state_result.mappings().one_or_none()

        if not latest_state:
            raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan")

        logger.info(
            "Ignored violation after session state transition session_id=%s status=%s event_type=%s",
            violation_data.session_id,
            str(latest_state["status"] or ""),
            normalized_event_type,
        )
        return _ignored_violation_response(latest_state["violation_count"])

    if not should_count_for_score:
        logger.info(
            "Violation logged as warning-only session_id=%s event_type=%s policy=%s",
            violation_data.session_id,
            normalized_event_type,
            counting_policy,
        )

    # FIX: Fallback exam_id from session if client sent 0
    # This ensures WebSocket broadcast goes to correct channel (exam_monitor_<real_id>)
    effective_exam_id = (
        violation_data.exam_id
        if violation_data.exam_id and violation_data.exam_id > 0
        else int(session_row["exam_id"])
    )

    violation_meta = get_violation_metadata(
        normalized_event_type,
        violation_payload,
        assume_violation=True,
    )

    # Log violation
    log = ExamLog(
        session_id=int(session_row["id"]),
        event_type=normalized_event_type,
        event_data={
            **violation_payload,
            "label": violation_meta["label"],
            "severity": violation_meta["severity"],
            "category": violation_meta["category"],
            "description": violation_meta["description"],
            "raw_event_type": violation_data.event_type,
            "source": violation_payload.get("source", "web"),
            "counted_for_score": should_count_for_score,
            "counting_policy": counting_policy,
            "reported_at": reported_at.isoformat(),
            "user_agent": violation_data.user_agent,
            "screen_resolution": violation_data.screen_resolution,
        }
    )
    db.add(log)
    await db.commit()
    try:
        cached_session_data = await get_session_data(int(session_row["id"]))
        if cached_session_data and safe_int(cached_session_data.get("user_id")) == current_user.id:
            cached_session_data["violation_count"] = int(session_row["violation_count"] or 0)
            cached_session_data["status"] = session_status or "in_progress"
            await store_session_data(int(session_row["id"]), cached_session_data)
    except Exception as cache_exc:
        logger.debug(
            "LOG-VIOLATION | session=%s | failed to refresh runtime snapshot: %s",
            int(session_row["id"]),
            str(cache_exc),
        )

    # Broadcast violation to admin
    event_timestamp = datetime.now(timezone.utc).isoformat()
    broadcast_payload = {
        "type": "violation_detected",
        "exam_id": effective_exam_id,
        "user_id": current_user.id,
        "username": current_user.username,
        "session_id": int(session_row["id"]),
        "event_type": normalized_event_type,
        "violation_type": strip_violation_prefix(normalized_event_type),
        "violation_label": violation_meta["label"],
        "violation_severity": violation_meta["severity"],
        "violation_category": violation_meta["category"],
        "counted_for_score": should_count_for_score,
        "counting_policy": counting_policy,
        "violation_count": int(session_row["violation_count"] or 0),
        "timestamp": event_timestamp,
    }
    try:
        await _publish_exam_monitor_event(effective_exam_id, broadcast_payload)
    except Exception:
        logger.exception(
            "Violation broadcast failed exam_id=%s session_id=%s event_type=%s",
            effective_exam_id,
            int(session_row["id"]),
            normalized_event_type,
        )

    violation_count = int(session_row["violation_count"] or 0)
    warning = get_violation_warning_message(violation_count)

    return ViolationResponse(
        status="logged",
        violation_count=violation_count,
        warning=warning
    )


@router.get("/session/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user_hot_path),
    db: AsyncSession = Depends(get_db_read)
):
    """Get current session status."""
    session_result = await db.execute(
        select(
            ExamSession.id.label("session_id"),
            ExamSession.exam_id.label("exam_id"),
            ExamSession.start_time.label("start_time"),
            ExamSession.status.label("status"),
            ExamSession.violation_count.label("violation_count"),
            ExamSession.total_paused_seconds.label("total_paused_seconds"),
            ExamSession.is_paused.label("is_paused"),
            ExamSession.paused_at.label("paused_at"),
            ExamSession.terminated_by_admin.label("terminated_by_admin"),
            ExamSession.emergency_exit_allowed.label("emergency_exit_allowed"),
            Exam.is_globally_paused.label("is_globally_paused"),
            Exam.globally_paused_by.label("globally_paused_by"),
            Exam.globally_paused_at.label("globally_paused_at"),
            Exam.duration_minutes.label("duration_minutes"),
        )
        .join(Exam, Exam.id == ExamSession.exam_id)
        .where(
            ExamSession.id == session_id,
            ExamSession.user_id == current_user.id,
        )
    )
    session_row = session_result.mappings().one_or_none()
    if not session_row:
        raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan")

    session_exam_id = int(session_row["exam_id"])
    session_status = str(session_row["status"])
    session_violation_count = int(session_row["violation_count"] or 0)

    # Read Redis session runtime snapshot first to avoid extra COUNT queries.
    redis_data = await get_session_data(session_id)
    redis_belongs_to_user = bool(
        redis_data and safe_int((redis_data or {}).get("user_id")) == current_user.id
    )

    total_questions = safe_int((redis_data or {}).get("total_questions")) if redis_belongs_to_user else None
    if total_questions is None or total_questions <= 0:
        total_questions = await _get_exam_question_count_cached(db, session_exam_id)

    answered_count: Optional[int] = None
    if redis_belongs_to_user and not bool((redis_data or {}).get("answered_count_stale")):
        answered_count = safe_int((redis_data or {}).get("answered_count"))
    if answered_count is None:
        try:
            answered_count = await _get_answered_count_from_set(session_id)
        except Exception as runtime_exc:
            logger.debug(
                "SESSION-STATUS | session=%s | runtime answered_count read failed: %s",
                session_id,
                str(runtime_exc),
            )
        if answered_count is None:
            answered_count = await _get_session_answer_count_cached(db, session_id)

    # Check pause state (from session or exam global pause)
    is_paused = bool(session_row["is_paused"]) or bool(session_row["is_globally_paused"])
    paused_by = None
    pause_message = None

    if is_paused:
        pause_message = "Ujian sedang di-pause oleh pengawas"
        # Get pauser info from exam if available
        if bool(session_row["is_globally_paused"]) and session_row["globally_paused_by"]:
            paused_by = await _get_user_display_name_cached(
                db,
                safe_int(session_row["globally_paused_by"]),
            )

    # Release DB transaction before Redis write/update operations.
    await db.commit()

    # Backfill Redis counters so subsequent poll calls stay DB-light.
    if redis_belongs_to_user and redis_data is not None:
        redis_changed = False
        if safe_int(redis_data.get("answered_count")) != int(answered_count):
            redis_data["answered_count"] = int(answered_count)
            redis_changed = True
        if bool(redis_data.get("answered_count_stale")):
            redis_data["answered_count_stale"] = False
            redis_changed = True
        if safe_int(redis_data.get("total_questions")) != int(total_questions):
            redis_data["total_questions"] = int(total_questions)
            redis_changed = True
        if str(redis_data.get("status") or "") != session_status:
            redis_data["status"] = session_status
            redis_changed = True
        if safe_int(redis_data.get("violation_count")) != session_violation_count:
            redis_data["violation_count"] = session_violation_count
            redis_changed = True
        if redis_changed:
            try:
                await store_session_data(session_id, redis_data)
            except Exception as cache_exc:
                logger.debug(
                    "SESSION-STATUS | session=%s | failed to refresh redis snapshot: %s",
                    session_id,
                    str(cache_exc),
                )

    # Build a lightweight timer view object instead of ORM relationships.
    timer_view = SimpleNamespace(
        start_time=(
            parse_iso_datetime_utc((redis_data or {}).get("start_time"))
            or session_row["start_time"]
        ),
        total_paused_seconds=safe_int(session_row["total_paused_seconds"]) or 0,
        is_paused=bool(session_row["is_paused"]),
        paused_at=session_row["paused_at"],
        exam=SimpleNamespace(
            duration_minutes=safe_int(session_row["duration_minutes"]) or 0,
            is_globally_paused=bool(session_row["is_globally_paused"]),
            globally_paused_at=session_row["globally_paused_at"],
        ),
    )
    started_at, total_seconds, total_paused = resolve_timer_context(timer_view, redis_data)
    _effective_elapsed, time_remaining = calculate_effective_timer(
        started_at=started_at,
        total_seconds=total_seconds,
        total_paused_seconds=total_paused,
    )

    # Update Redis activity only while the session is actively running.
    if session_status == "in_progress" and _should_update_session_activity(session_id):
        try:
            await update_session_activity(session_exam_id, current_user.id, {
                "last_active": datetime.now(timezone.utc).isoformat(),
                "status": "online"
            })
        except Exception as e:
            logger.warning(f"Failed to update session activity: {e}")

    # Check for kick/termination states (for Flutter APK polling)
    kick_reason = None
    emergency_exit_allowed = bool(session_row["emergency_exit_allowed"])
    terminated_by_admin = bool(session_row["terminated_by_admin"])

    # Canonical DB state for "force kick" is terminated + terminated_by_admin=True
    # (without emergency exit). Keep backward compatibility by reporting kicked status.
    is_force_kick = (
        session_status == "kicked"
        or (
            session_status == "terminated"
            and terminated_by_admin
            and not emergency_exit_allowed
        )
    )
    if is_force_kick:
        kick_reason = "Dikeluarkan oleh pengawas"

    reported_status = "kicked" if is_force_kick else session_status

    return SessionStatusResponse(
        session_id=session_id,
        status=reported_status,
        time_remaining_seconds=time_remaining,
        answered_count=int(answered_count),
        total_questions=int(total_questions),
        violation_count=session_violation_count,
        is_paused=is_paused,
        paused_by=paused_by,
        pause_message=pause_message,
        kick_reason=kick_reason,
        emergency_exit_allowed=emergency_exit_allowed,
        terminated_by_admin=terminated_by_admin,
        session_poll_token=create_session_poll_token(
            session_id=session_id,
            user_id=current_user.id,
            expires_minutes=SESSION_POLL_TOKEN_EXPIRES_MINUTES,
        ),
        session_poll_token_expires_minutes=SESSION_POLL_TOKEN_EXPIRES_MINUTES,
    )


# ============== PRECISE EXAM RESUME (Phase 7) ==============

class PreciseTimerResponse(BaseModel):
    """Response with second-accurate remaining time."""
    session_id: int
    remaining_seconds: int
    elapsed_seconds: int
    total_seconds: int
    started_at: str
    is_expired: bool


@router.get("/session/{session_id}/remaining-time", response_model=PreciseTimerResponse)
async def get_remaining_time(
    session_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user_hot_path),
    db: AsyncSession = Depends(get_db_read)
):
    """
    Get precise remaining time for exam session.

    Calculates elapsed time from Redis timestamp for accurate
    resume after disconnection.

    Returns:
    - remaining_seconds: Exact seconds left
    - elapsed_seconds: Seconds used so far
    - is_expired: Whether exam time has run out
    """
    redis_data = await get_session_data(session_id)
    redis_belongs_to_user = bool(
        redis_data and safe_int((redis_data or {}).get("user_id")) == current_user.id
    )

    if redis_belongs_to_user:
        redis_duration_seconds = safe_int((redis_data or {}).get("duration_seconds")) or 0
        redis_duration_minutes = safe_int((redis_data or {}).get("duration_minutes")) or 0
        if redis_duration_minutes <= 0 and redis_duration_seconds > 0:
            redis_duration_minutes = max(1, redis_duration_seconds // 60)

        redis_start_time = parse_iso_datetime_utc((redis_data or {}).get("start_time"))
        if redis_start_time and redis_duration_minutes > 0:
            timer_view = SimpleNamespace(
                start_time=redis_start_time,
                total_paused_seconds=safe_int((redis_data or {}).get("total_paused_seconds")) or 0,
                is_paused=bool((redis_data or {}).get("paused", False)),
                paused_at=None,
                exam=SimpleNamespace(
                    duration_minutes=redis_duration_minutes,
                    is_globally_paused=False,
                    globally_paused_at=None,
                ),
            )
            started_at, total_seconds, total_paused = resolve_timer_context(timer_view, redis_data)
            effective_elapsed, remaining = calculate_effective_timer(
                started_at=started_at,
                total_seconds=total_seconds,
                total_paused_seconds=total_paused,
            )
            return PreciseTimerResponse(
                session_id=session_id,
                remaining_seconds=remaining,
                elapsed_seconds=effective_elapsed,
                total_seconds=total_seconds,
                started_at=started_at.isoformat(),
                is_expired=remaining <= 0,
            )

    # Fallback: DB-backed timer lookup when Redis snapshot missing/incomplete.
    session_result = await db.execute(
        select(
            ExamSession.start_time.label("start_time"),
            ExamSession.total_paused_seconds.label("total_paused_seconds"),
            ExamSession.is_paused.label("is_paused"),
            ExamSession.paused_at.label("paused_at"),
            Exam.duration_minutes.label("duration_minutes"),
            Exam.is_globally_paused.label("is_globally_paused"),
            Exam.globally_paused_at.label("globally_paused_at"),
        )
        .join(Exam, Exam.id == ExamSession.exam_id)
        .where(
            ExamSession.id == session_id,
            ExamSession.user_id == current_user.id,
        )
    )
    session_row = session_result.mappings().one_or_none()
    if not session_row:
        raise HTTPException(404, "Sesi ujian tidak ditemukan")

    await db.commit()
    timer_view = SimpleNamespace(
        start_time=session_row["start_time"],
        total_paused_seconds=safe_int(session_row["total_paused_seconds"]) or 0,
        is_paused=bool(session_row["is_paused"]),
        paused_at=session_row["paused_at"],
        exam=SimpleNamespace(
            duration_minutes=safe_int(session_row["duration_minutes"]) or 0,
            is_globally_paused=bool(session_row["is_globally_paused"]),
            globally_paused_at=session_row["globally_paused_at"],
        ),
    )
    started_at, total_seconds, total_paused = resolve_timer_context(timer_view, redis_data)
    effective_elapsed, remaining = calculate_effective_timer(
        started_at=started_at,
        total_seconds=total_seconds,
        total_paused_seconds=total_paused,
    )
    started_at_str = started_at.isoformat()

    return PreciseTimerResponse(
        session_id=session_id,
        remaining_seconds=remaining,
        elapsed_seconds=effective_elapsed,
        total_seconds=total_seconds,
        started_at=started_at_str,
        is_expired=remaining <= 0
    )


# ============== SESSION RESUME (Network Disconnection Recovery) ==============

class SessionResumeResponse(BaseModel):
    """Response for session resume after disconnection."""
    session_id: int
    exam_id: int
    exam_title: str
    remaining_seconds: int
    elapsed_seconds: int
    total_seconds: int
    is_expired: bool
    saved_answers: dict  # {question_id: answer_data}
    answered_count: int
    total_questions: int
    last_question_id: Optional[int] = None
    can_resume: bool
    message: str
    recovery_category: Optional[str] = None
    recovery_message: Optional[str] = None
    session_poll_token: Optional[str] = None
    session_poll_token_expires_minutes: Optional[int] = None


@router.get("/session/{session_id}/resume", response_model=SessionResumeResponse)
async def resume_session(
    session_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user_hot_path),
    db: AsyncSession = Depends(get_db_read)
):
    """
    Resume exam session after network disconnection.

    Returns:
    - All saved answers (from Redis or Database)
    - Remaining time (accurate calculation)
    - Last answered question for navigation
    - Whether session can still be resumed

    Use Case: Student's network goes down, they login again after 10 minutes,
    this endpoint loads their progress so they can continue.
    """
    from app.core.redis_pubsub import get_session_data, get_session_answers

    # Get session from database
    result = await db.execute(
        select(ExamSession)
        .options(
            selectinload(ExamSession.exam).selectinload(Exam.questions),
            selectinload(ExamSession.answers)
        )
        .where(
            ExamSession.id == session_id,
            ExamSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, "Sesi ujian tidak ditemukan")

    logs_result = await db.execute(
        select(ExamLog)
        .where(ExamLog.session_id == session_id)
        .order_by(ExamLog.created_at.desc(), ExamLog.id.desc())
        .limit(30)
    )
    session_logs = logs_result.scalars().all()
    recovery_status = evaluate_session_recovery(session, session_logs)

    # Check if session already completed
    if session.status in ["completed", "submitted"]:
        return SessionResumeResponse(
            session_id=session_id,
            exam_id=session.exam.id,
            exam_title=session.exam.title,
            remaining_seconds=0,
            elapsed_seconds=session.exam.duration_minutes * 60,
            total_seconds=session.exam.duration_minutes * 60,
            is_expired=True,
            saved_answers={},
            answered_count=len(session.answers),
            total_questions=len(session.exam.questions),
            last_question_id=None,
            can_resume=False,
            message=recovery_status.get("message") or "Ujian sudah selesai dikumpulkan",
            recovery_category=recovery_status.get("category"),
            recovery_message=recovery_status.get("message"),
            session_poll_token=create_session_poll_token(
                session_id=session_id,
                user_id=current_user.id,
                expires_minutes=SESSION_POLL_TOKEN_EXPIRES_MINUTES,
            ),
            session_poll_token_expires_minutes=SESSION_POLL_TOKEN_EXPIRES_MINUTES,
        )

    # Close DB transaction before Redis calls and response assembly.
    await db.commit()
    redis_data = await get_session_data(session_id)
    started_at, total_seconds, total_paused = resolve_timer_context(session, redis_data)
    elapsed, remaining = calculate_effective_timer(
        started_at=started_at,
        total_seconds=total_seconds,
        total_paused_seconds=total_paused,
    )
    is_expired = remaining <= 0

    # Get saved answers - try Redis first (faster), fallback to Database
    saved_answers: Dict[str, Any] = {}
    last_question_id = None

    # Try Redis cache
    redis_answers = await get_session_answers(session_id)
    if redis_answers:
        # Copy and ensure keys are strings
        for k, v in redis_answers.items():
            saved_answers[str(k)] = v


    # Get answers from database (authoritative source)
    last_answered_at: Optional[datetime] = None
    for answer in session.answers:
        answer_data = {}
        if answer.selected_option_id:
            answer_data["selected_option_id"] = answer.selected_option_id
        if answer.selected_option_ids:
            answer_data["selected_option_ids"] = answer.selected_option_ids
        if answer.answer_text:
            answer_data["answer_text"] = answer.answer_text
        answer_meta = answer.answer_metadata or {}
        statement_answers = answer_meta.get("statement_answers")
        if isinstance(statement_answers, dict) and statement_answers:
            answer_data["statement_answers"] = statement_answers

        saved_answers[str(answer.question_id)] = answer_data

        # Track last answered question using authoritative timestamp field.
        if answer.answered_at and (last_answered_at is None or answer.answered_at > last_answered_at):
            last_answered_at = answer.answered_at
            last_question_id = answer.question_id

    # Determine if can resume
    can_resume = bool(recovery_status.get("allow_continue")) and not is_expired

    if is_expired:
        message = "Waktu ujian sudah habis. Jawaban tersimpan otomatis."
    elif can_resume:
        message = f"Lanjutkan ujian. {len(saved_answers)} jawaban tersimpan."
    else:
        message = recovery_status.get("message") or "Sesi tidak dapat dilanjutkan."

    return SessionResumeResponse(
        session_id=session_id,
        exam_id=session.exam.id,
        exam_title=session.exam.title,
        remaining_seconds=remaining,
        elapsed_seconds=elapsed,
        total_seconds=total_seconds,
        is_expired=is_expired,
        saved_answers=saved_answers,
        answered_count=len(saved_answers),
        total_questions=len(session.exam.questions),
        last_question_id=last_question_id,
        can_resume=can_resume,
        message=message,
        recovery_category=recovery_status.get("category"),
        recovery_message=recovery_status.get("message"),
        session_poll_token=create_session_poll_token(
            session_id=session_id,
            user_id=current_user.id,
            expires_minutes=SESSION_POLL_TOKEN_EXPIRES_MINUTES,
        ),
        session_poll_token_expires_minutes=SESSION_POLL_TOKEN_EXPIRES_MINUTES,
    )


# ============== EXAM PAUSE CONTROL (Network Outage Recovery) ==============

class PauseResponse(BaseModel):
    """Response for pause/resume operations."""
    exam_id: int
    is_paused: bool
    paused_at: Optional[str] = None
    affected_sessions: int
    message: str


@router.post("/{exam_id}/pause-all", response_model=PauseResponse)
async def pause_exam_globally(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Pause exam for ALL active students.

    Use when network goes down and you need to freeze everyone's timer.
    WebSocket broadcast notifies all connected students immediately.
    """
    from app.core.redis_pubsub import publish_message

    # Get exam
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(404, "Ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
        allow_pengawas=True,
    )

    if exam.is_globally_paused:
        raise HTTPException(400, "Ujian sudah dalam status pause")

    # Update exam global pause status
    now = datetime.now(timezone.utc)
    exam.is_globally_paused = True
    exam.globally_paused_at = now
    exam.globally_paused_by = current_user.id

    # Update all active sessions
    sessions_result = await db.execute(
        select(ExamSession)
        .where(ExamSession.exam_id == exam_id)
        .where(ExamSession.status == "in_progress")
    )
    active_sessions = sessions_result.scalars().all()

    for session in active_sessions:
        session.is_paused = True
        session.paused_at = now

    await db.commit()

    # WebSocket broadcast to admin monitoring
    await publish_message("exam_control", {
        "type": "exam_paused",
        "exam_id": exam_id,
        "paused_at": now.isoformat(),
        "paused_by": current_user.full_name or current_user.username,
        "message": "Ujian telah di-pause oleh pengawas"
    })

    # CRITICAL: Broadcast to each student's individual channel
    for session in active_sessions:
        await publish_message(f"exam_student_{exam_id}_{session.user_id}", {
            "type": "exam_paused",
            "exam_id": exam_id,
            "paused_at": now.isoformat(),
            "paused_by": current_user.full_name or current_user.username,
            "message": "Ujian telah di-pause oleh pengawas"
        })

    # Log admin action for audit trail
    from app.api.activity import log_activity
    await log_activity(
        db=db,
        user_id=current_user.id,
        event_type="admin_pause_exam",
        event_data={
            "exam_id": exam_id,
            "exam_title": exam.title,
            "affected_sessions": len(active_sessions),
            "paused_at": now.isoformat()
        }
    )
    await db.commit()

    return PauseResponse(
        exam_id=exam_id,
        is_paused=True,
        paused_at=now.isoformat(),
        affected_sessions=len(active_sessions),
        message=f"Ujian berhasil di-pause. {len(active_sessions)} sesi terpengaruh."
    )


@router.post("/{exam_id}/resume-all", response_model=PauseResponse)
async def resume_exam_globally(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Resume exam for ALL paused students.

    Calculates pause duration and adjusts remaining time for each student.
    WebSocket broadcast notifies all students to resume their timers.
    """
    from app.core.redis_pubsub import publish_message, get_session_data, store_session_data

    # Get exam
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(404, "Ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
        allow_pengawas=True,
    )

    if not exam.is_globally_paused:
        raise HTTPException(400, "Ujian tidak dalam status pause")

    now = datetime.now(timezone.utc)
    pause_duration = int((now - exam.globally_paused_at).total_seconds()) if exam.globally_paused_at else 0

    # Update exam global pause status
    exam.is_globally_paused = False
    exam.globally_paused_at = None

    # Update all paused sessions
    sessions_result = await db.execute(
        select(ExamSession)
        .where(ExamSession.exam_id == exam_id)
        .where(ExamSession.is_paused == True)
    )
    paused_sessions = sessions_result.scalars().all()
    paused_session_ids: List[int] = []
    paused_session_user_map: Dict[int, int] = {}
    paused_session_total_map: Dict[int, int] = {}

    for session in paused_sessions:
        session.is_paused = False
        session.total_paused_seconds = (session.total_paused_seconds or 0) + pause_duration
        session.paused_at = None
        paused_session_ids.append(int(session.id))
        paused_session_user_map[int(session.id)] = int(session.user_id)
        paused_session_total_map[int(session.id)] = int(session.total_paused_seconds or 0)

    await db.commit()

    # Update Redis timer after DB commit to avoid idle-in-transaction timeouts.
    for paused_session_id in paused_session_ids:
        redis_data = await get_session_data(paused_session_id)
        if redis_data:
            redis_data["total_paused_seconds"] = paused_session_total_map.get(paused_session_id, 0)
            await store_session_data(paused_session_id, redis_data)

    # WebSocket broadcast to admin monitoring
    await publish_message("exam_control", {
        "type": "exam_resumed",
        "exam_id": exam_id,
        "resumed_at": now.isoformat(),
        "pause_duration_seconds": pause_duration,
        "message": "Ujian dilanjutkan. Timer Anda sudah disesuaikan."
    })

    # CRITICAL: Broadcast to each student's individual channel
    for paused_session_id in paused_session_ids:
        target_user_id = paused_session_user_map.get(paused_session_id)
        if target_user_id is None:
            continue
        await publish_message(f"exam_student_{exam_id}_{target_user_id}", {
            "type": "exam_resumed",
            "exam_id": exam_id,
            "resumed_at": now.isoformat(),
            "pause_duration_seconds": pause_duration,
            "message": "Ujian dilanjutkan. Timer Anda sudah disesuaikan."
        })

    # Log admin action for audit trail
    from app.api.activity import log_activity
    await log_activity(
        db=db,
        user_id=current_user.id,
        event_type="admin_resume_exam",
        event_data={
            "exam_id": exam_id,
            "exam_title": exam.title,
            "affected_sessions": len(paused_sessions),
            "pause_duration_seconds": pause_duration
        }
    )
    await db.commit()

    return PauseResponse(
        exam_id=exam_id,
        is_paused=False,
        paused_at=None,
        affected_sessions=len(paused_sessions),
        message=f"Ujian dilanjutkan. {len(paused_sessions)} sesi resumed. Pause duration: {pause_duration}s"
    )


@router.get("/{exam_id}/pause-status")
async def get_pause_status(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current pause status of an exam."""
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(404, "Ujian tidak ditemukan")

    if _is_exam_participant_role(current_user.role):
        creator_role = await _get_exam_creator_role(db, exam.creator_id)
        _ensure_exam_participant_access(
            exam,
            current_user,
            exam_creator_role=creator_role,
        )
    else:
        await _enforce_exam_owner_or_admin_access(
            db,
            current_user,
            exam.creator_id,
            allow_pengawas=True,
        )

    pause_duration = 0
    if exam.is_globally_paused and exam.globally_paused_at:
        pause_duration = int((datetime.now(timezone.utc) - exam.globally_paused_at).total_seconds())

    return {
        "exam_id": exam_id,
        "is_paused": exam.is_globally_paused,
        "paused_at": exam.globally_paused_at.isoformat() if exam.globally_paused_at else None,
        "current_pause_duration": pause_duration
    }


# ============== PDF EXPORT ENDPOINTS ==============

@router.get("/{exam_id}/analytics/pdf")
async def get_exam_analytics_pdf(
    exam_id: int,
    class_name: Optional[str] = Query(
        default=None,
        description="Nama kelas dari tab performa siswa (opsional)"
    ),
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db_read)
):
    """
    Export exam analytics (overview, analisis soal, performa siswa) as formal PDF.
    """
    require_feature_enabled(
        settings.heavy_exports_active,
        "heavy_export",
        status_code=503,
        message="PDF analytics sedang dinonaktifkan selama mode ujian/puncak.",
    )
    from app.api.analytics import (
        _build_class_performance_payload,
        get_question_difficulty_analysis,
    )
    from app.core.pdf_generator import (
        REPORTLAB_AVAILABLE,
        generate_exam_analytics_pdf,
    )

    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="PDF export tidak tersedia. Install ReportLab: pip install reportlab"
        )

    exam_result = await db.execute(
        select(Exam)
        .options(selectinload(Exam.creator))
        .where(
            Exam.id == exam_id,
            Exam.is_deleted == False
        )
    )
    exam = exam_result.scalar_one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
    )

    overview_obj = await get_exam_analytics(exam_id=exam_id, current_user=current_user, db=db)
    overview_payload = (
        overview_obj.model_dump()
        if hasattr(overview_obj, "model_dump")
        else dict(overview_obj)
    )

    question_payload = await get_question_difficulty_analysis(
        exam_id=exam_id,
        current_user=current_user,
        db=db,
    )
    question_rows = question_payload.get("questions", [])

    class_filter = (class_name or "").strip()
    class_payload = None
    if class_filter:
        class_obj = await _build_class_performance_payload(
            class_filter,
            current_user,
            db,
            exam_id=exam_id,
        )
        class_payload = (
            class_obj.model_dump()
            if hasattr(class_obj, "model_dump")
            else dict(class_obj)
        )

    creator_name = "-"
    if exam.creator:
        role_prefix = ""
        if exam.creator.role == "teacher":
            role_prefix = "Guru "
        elif exam.creator.role == ROLE_DEVELOPER:
            role_prefix = "Developer "
        elif exam.creator.role == "admin":
            role_prefix = "Admin "
        creator_name = f"{role_prefix}{exam.creator.full_name or exam.creator.username}"

    exported_at = datetime.now(pytz.timezone("Asia/Jakarta")).strftime(
        "%A, %d %B %Y %H:%M WIB"
    )

    payload = {
        "exam": {
            "id": exam.id,
            "title": exam.title,
            "subject": exam.subject or "-",
            "teacher_name": creator_name,
            "passing_score": float(exam.passing_score or 70),
        },
        "overview": overview_payload,
        "score_distribution": overview_payload.get("score_distribution") or {},
        "question_analysis": question_rows,
        "class_performance": class_payload,
        "class_filter": class_filter or "Belum dipilih",
        "generated_at": exported_at,
    }

    pdf_bytes = generate_exam_analytics_pdf(payload)

    safe_title = re.sub(r"[^\w\s-]", "", exam.title or "ujian").strip()
    safe_title = re.sub(r"\s+", "_", safe_title) or "ujian"
    filename = f"analitik_ujian_{safe_title}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{exam_id}/results/pdf")
async def get_exam_results_pdf(
    exam_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Export exam results as PDF document.
    Includes all student scores, pass/fail status, and summary statistics.
    """
    require_feature_enabled(
        settings.heavy_exports_active,
        "heavy_export",
        status_code=503,
        message="PDF hasil ujian sedang dinonaktifkan selama mode ujian/puncak.",
    )
    from app.core.pdf_generator import generate_exam_results_pdf, REPORTLAB_AVAILABLE

    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="PDF export tidak tersedia. Install ReportLab: pip install reportlab"
        )

    # Verify exam exists and user has access
    result = await db.execute(
        select(Exam)
        .options(selectinload(Exam.creator))
        .where(Exam.id == exam_id)
    )
    exam = result.scalar_one_or_none()

    if not exam:
        raise HTTPException(status_code=404, detail="Ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        exam.creator_id,
    )

    # Generate creator name with role prefix
    creator_name = None
    if exam.creator:
        role_prefix = ""
        if exam.creator.role == "teacher":
            role_prefix = "Guru "
        elif exam.creator.role == ROLE_DEVELOPER:
            role_prefix = "Developer "
        elif exam.creator.role == "admin":
            role_prefix = "Admin "
        creator_name = f"{role_prefix}{exam.creator.full_name or exam.creator.username}"

    # Fetch all submitted sessions
    stmt = (
        select(ExamSession)
        .where(ExamSession.exam_id == exam_id)
        .where(ExamSession.status.in_(["submitted", "completed"]))
        .options(selectinload(ExamSession.user))
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    if not sessions:
        raise HTTPException(status_code=404, detail="Belum ada hasil ujian")

    # Prepare results data
    results = []
    scores = []
    passed_count = 0

    for session in sessions:
        score = float(session.score or 0)
        passed = score >= float(exam.passing_score or 70)

        if passed:
            passed_count += 1
        scores.append(score)

        results.append({
            "student_name": session.user.full_name or session.user.username,
            "student_class": getattr(session.user, 'student_class', '-') or '-',
            "score": score,
            "passed": passed
        })

    # Calculate summary statistics
    summary = {
        "average": sum(scores) / len(scores) if scores else 0,
        "highest": max(scores) if scores else 0,
        "lowest": min(scores) if scores else 0,
        "passed": passed_count,
        "failed": len(sessions) - passed_count,
        "pass_rate": (passed_count / len(sessions) * 100) if sessions else 0
    }

    # Generate PDF
    exam_date = exam.start_time.strftime("%d %B %Y") if exam.start_time else "N/A"
    pdf_bytes = generate_exam_results_pdf(
        exam_title=exam.title,
        exam_date=exam_date,
        results=results,
        summary=summary,
        creator_name=creator_name
    )

    # Return PDF response
    filename = f"hasil_ujian_{exam.title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/{exam_id}/sessions/{session_id}/certificate")
async def get_session_certificate(
    exam_id: int,
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate completion certificate PDF for a passed exam session.
    Peserta ujian (student/GuruPlus) dapat download sertifikat milik sendiri.
    Teachers/Admins can download any certificate.
    """
    require_feature_enabled(
        settings.heavy_exports_active,
        "heavy_export",
        status_code=503,
        message="Sertifikat PDF sedang dinonaktifkan selama mode ujian/puncak.",
    )
    from app.core.pdf_generator import generate_certificate_pdf, REPORTLAB_AVAILABLE
    import hashlib

    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="PDF export tidak tersedia. Install ReportLab: pip install reportlab"
        )

    # Get session
    stmt = (
        select(ExamSession)
        .where(ExamSession.id == session_id, ExamSession.exam_id == exam_id)
        .options(selectinload(ExamSession.user), selectinload(ExamSession.exam))
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan")

    # Check access (participant can only access their own).
    if _is_exam_participant_role(current_user.role) and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses")
    elif not _is_exam_participant_role(current_user.role):
        await _enforce_exam_owner_or_admin_access(
            db,
            current_user,
            session.exam.creator_id,
            allow_pengawas=True,
        )

    # Check if passed
    passing_score = float(session.exam.passing_score or 70)
    score = float(session.score or 0)

    if score < passing_score:
        raise HTTPException(
            status_code=400,
            detail=f"Sertifikat hanya tersedia untuk yang lulus (skor >= {passing_score})"
        )

    # Generate certificate ID
    cert_data = f"{session.id}-{session.user_id}-{session.exam_id}"
    certificate_id = hashlib.sha256(cert_data.encode()).hexdigest()[:12].upper()

    # Generate PDF
    completion_date = session.end_time.strftime("%d %B %Y") if session.end_time else "N/A"

    pdf_bytes = generate_certificate_pdf(
        student_name=session.user.full_name or session.user.username,
        exam_title=session.exam.title,
        score=score,
        completion_date=completion_date,
        certificate_id=f"CERT-{certificate_id}"
    )

    # Return PDF response
    filename = f"sertifikat_{session.user.username}_{session.exam.title.replace(' ', '_')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )






@router.post("/sessions/{session_id}/force-submit", response_model=ExamSubmitResponse)
async def force_submit_session(
    session_id: int,
    current_user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Force submit a specific session (Teacher/Admin only).
    Useful when a student has finished but the status is stuck in 'in_progress'.
    Calculates the score based on answers currently saved in the database.
    """
    # 1. Get session with exam and questions
    stmt = (
        select(ExamSession)
        .options(
            selectinload(ExamSession.exam)
            .selectinload(Exam.questions)
            .selectinload(Question.options),
            selectinload(ExamSession.answers),
            selectinload(ExamSession.user)
        )
        .where(ExamSession.id == session_id)
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Sesi ujian tidak ditemukan")

    await _enforce_exam_owner_or_admin_access(
        db,
        current_user,
        session.exam.creator_id,
        allow_pengawas=True,
    )

    # Idempotent behavior: if session already submitted/completed, return current result
    if session.status in ("submitted", "completed"):
        total_points = sum(float(q.points) for q in session.exam.questions)
        points_earned = sum(float(a.points_earned or 0) for a in session.answers)
        percentage = (points_earned / total_points * 100) if total_points > 0 else 0
        passed = None
        if session.exam.passing_score:
            passed = percentage >= float(session.exam.passing_score)
        return ExamSubmitResponse(
            session_id=session.id,
            status="submitted",
            score=percentage,
            total_points=total_points,
            points_earned=points_earned,
            percentage=percentage,
            passed=passed,
            message="Sesi sudah pernah dikumpulkan."
        )

    if session.status != "in_progress":
        raise HTTPException(status_code=400, detail="Sesi tidak dalam status in_progress")

    submitted_at = session.end_time or datetime.now(timezone.utc)
    finalize_result = finalize_exam_session_submission(session, submitted_at=submitted_at)

    # 5. Log Action
    log = ExamLog(
        session_id=session.id,
        event_type="FORCE_SUBMIT_BY_TEACHER",
        event_data={
            "teacher_id": current_user.id,
            "teacher_name": current_user.full_name,
            "category": "admin_decision",
            "allow_continue": False,
            "score": session.score,
            "reason": "Teacher forced submission via admin panel"
        }
    )
    db.add(log)

    breakdown_log = ExamLog(
        session_id=session.id,
        event_type="SCORE_BREAKDOWN",
        event_data={"score_breakdown": finalize_result.score_breakdown}
    )
    db.add(breakdown_log)

    await db.commit()
    await _invalidate_exam_results_cache(session.exam_id)

    # 6. Broadcast Update (best-effort)
    try:
        await _publish_exam_monitor_event(session.exam_id, {
            "type": "student_submitted",
            "user_id": session.user_id,
            "username": session.user.username,
            "session_id": session.id,
            "score": float(session.score) if session.score is not None else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_forced": True
        })
    except Exception as exc:
        logger.warning("Failed to publish forced submission for session %s: %s", session.id, str(exc))

    # Determine if passed
    passed = None
    if session.exam.passing_score:
        passed = finalize_result.percentage >= float(session.exam.passing_score)

    return ExamSubmitResponse(
        session_id=session.id,
        status="submitted",
        score=finalize_result.percentage,
        total_points=finalize_result.total_points,
        points_earned=finalize_result.points_earned,
        percentage=finalize_result.percentage,
        passed=passed,
        message="Sesi berhasil diselesaikan secara paksa."
    )
