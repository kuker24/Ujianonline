"""APK/mobile runtime policy builder.

This policy is intentionally small and safe to expose to APK/web clients. It lets
operators change sync intervals through server-side runtime modes without
rebuilding the APK.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal

from app.config import settings
from app.core.degrade_mode import get_runtime_policy as get_internal_runtime_policy

RuntimeMode = Literal["normal", "busy", "exam_peak", "degraded", "maintenance"]

_POLICY_BY_MODE: Dict[str, Dict[str, Any]] = {
    "normal": {
        "answer_sync_interval_seconds": 15,
        "answer_sync_batch_size": 30,
        "command_poll_seconds": 25,
        "violation_flush_seconds": 30,
        "retry_after_seconds": 8,
    },
    "busy": {
        "answer_sync_interval_seconds": 25,
        "answer_sync_batch_size": 40,
        "command_poll_seconds": 35,
        "violation_flush_seconds": 60,
        "retry_after_seconds": 8,
    },
    "exam_peak": {
        "answer_sync_interval_seconds": 45,
        "answer_sync_batch_size": 50,
        "command_poll_seconds": 60,
        "violation_flush_seconds": 120,
        "retry_after_seconds": 8,
    },
    "degraded": {
        "answer_sync_interval_seconds": 45,
        "answer_sync_batch_size": 50,
        "command_poll_seconds": 60,
        "violation_flush_seconds": 120,
        "retry_after_seconds": 8,
    },
    "maintenance": {
        "answer_sync_interval_seconds": 60,
        "answer_sync_batch_size": 20,
        "command_poll_seconds": 60,
        "violation_flush_seconds": 120,
        "retry_after_seconds": 15,
    },
}


def resolve_mobile_runtime_mode(internal_policy: Dict[str, Any]) -> RuntimeMode:
    """Map internal resource/degrade flags to APK-facing runtime modes."""
    if settings.exam_peak_mode:
        return "exam_peak"

    resource_mode = str(internal_policy.get("resource_mode") or "normal").strip().lower()
    degrade_mode = bool(internal_policy.get("degrade_mode", False))

    if resource_mode == "extreme":
        return "degraded"
    if resource_mode == "high" or degrade_mode:
        return "busy"
    return "normal"


def build_mobile_runtime_policy(
    mode: RuntimeMode,
    *,
    internal_policy: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the stable APK-facing policy response."""
    normalized_mode = mode if mode in _POLICY_BY_MODE else "normal"
    values = dict(_POLICY_BY_MODE[normalized_mode])
    internal_policy = internal_policy or {}

    values.update(
        {
            "mode": normalized_mode,
            "cheating_detection_enabled": True,
            "cheating_detail_level": "aggregate",
            "final_submit_priority": True,
            "server_time": datetime.now(timezone.utc).isoformat(),
            "policy_version": "20260602-mobile-runtime-v1",
            "source": "server_runtime_policy",
            "resource_mode": internal_policy.get("resource_mode", "normal"),
            "degrade_mode": bool(internal_policy.get("degrade_mode", False)),
            "expires_at": internal_policy.get("resource_mode_expires_at") or internal_policy.get("expires_at"),
        }
    )
    return values


async def get_mobile_runtime_policy(force_refresh: bool = False) -> Dict[str, Any]:
    """Return APK/web policy with safe fallback when Redis/degrade state is unavailable."""
    try:
        internal_policy = await get_internal_runtime_policy(force_refresh=force_refresh)
    except Exception:
        internal_policy = {"resource_mode": "normal", "degrade_mode": False}

    mode = resolve_mobile_runtime_mode(internal_policy)
    return build_mobile_runtime_policy(mode, internal_policy=internal_policy)
