#!/usr/bin/env python3
"""Staging-only forced-flush proof harness skeleton.

This tool is intentionally guarded and defaults to dry-run/stubbed proof
outputs. It must not be pointed at production. It never prints raw answer
values, tokens, session tokens, real user identifiers, credentials, or raw
metadata objects.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED_STAGING_FLAG = "STAGING_FORCE_FLUSH_PROOF"
REQUIRED_SYNTHETIC_MARKER = "PHASE6_FORCE_FLUSH_TEST"
CONFIRMATION_FLAG = "i_understand_this_is_staging_only"

PRODUCTION_ENV_VALUES = {"production", "prod"}
PRODUCTION_HOST_PATTERNS = {
    "man1rokanhulu.cloud",
    "103.175.218.56",
    "adminujian",
}
PRODUCTION_DB_NAMES = {
    "exam_system",
    "ujian_online",
    "ujianonline",
}
SENSITIVE_OUTPUT_KEYS = {
    "answer",
    "answer_text",
    "raw_answer",
    "token",
    "session_token",
    "access_token",
    "refresh_token",
    "username",
    "full_name",
    "email",
    "phone",
    "metadata",
    "answer_metadata",
}

READ_ONLY_COMMANDS = {"preflight", "inspect-readiness", "summarize", "cleanup-plan"}
SCENARIO_COMMANDS = {
    "run-direct-baseline",
    "run-shadow-baseline",
    "run-buffer-drain",
    "run-worker-restart",
    "run-final-submit-pending",
}


class GuardError(RuntimeError):
    """Raised when staging safety guards fail."""


@dataclass(frozen=True)
class TargetInfo:
    database_host: str | None
    database_name: str | None
    redis_host: str | None
    target_base_host: str | None


def _split_csv(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _host_from_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    parsed = urlparse(raw_url)
    if parsed.hostname:
        return parsed.hostname.lower()
    return None


def _db_name_from_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    parsed = urlparse(raw_url)
    path = (parsed.path or "").strip("/")
    if not path:
        return None
    return path.split("/")[-1].lower()


def _target_info(env: Mapping[str, str]) -> TargetInfo:
    database_url = env.get("DATABASE_URL") or ""
    redis_url = env.get("REDIS_URL") or ""
    target_url = env.get("STAGING_PROOF_TARGET_BASE_URL") or env.get("BASE_URL") or ""
    return TargetInfo(
        database_host=_host_from_url(database_url) or (env.get("DB_HOST") or "").lower() or None,
        database_name=_db_name_from_url(database_url) or (env.get("DB_NAME") or "").lower() or None,
        redis_host=_host_from_url(redis_url) or (env.get("REDIS_HOST") or "").lower() or None,
        target_base_host=_host_from_url(target_url),
    )


def _contains_production_pattern(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(pattern in lowered for pattern in PRODUCTION_HOST_PATTERNS)


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _redact_id(value: int | str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return "***" + text[-2:]


def _env_is_true(env: Mapping[str, str], key: str) -> bool:
    return str(env.get(key, "")).strip().lower() == "true"


def _readiness_report(env: Mapping[str, str], target: TargetInfo) -> Dict[str, Any]:
    allowed_db_hosts = _split_csv(env.get("STAGING_PROOF_ALLOWED_DB_HOSTS"))
    allowed_redis_hosts = _split_csv(env.get("STAGING_PROOF_ALLOWED_REDIS_HOSTS"))
    redis_policy = str(env.get("STAGING_PROOF_REDIS_MAXMEMORY_POLICY", "")).strip().lower()
    redis_aof_enabled = _env_is_true(env, "STAGING_PROOF_REDIS_AOF_ENABLED")
    celery_answer_flush = _env_is_true(env, "STAGING_PROOF_CELERY_ANSWER_FLUSH_WORKER")
    celery_queue_bound = _env_is_true(env, "STAGING_PROOF_CELERY_ANSWER_FLUSH_QUEUE_BOUND")
    synthetic_data_ready = _env_is_true(env, "STAGING_PROOF_SYNTHETIC_DATA_READY")
    cleanup_ready = _env_is_true(env, "STAGING_PROOF_CLEANUP_PLAN_READY")

    checks = {
        "staging_flag_enabled": _env_is_true(env, REQUIRED_STAGING_FLAG),
        "db_host_allowlisted": bool(target.database_host and target.database_host in allowed_db_hosts),
        "redis_host_allowlisted": bool(target.redis_host and target.redis_host in allowed_redis_hosts),
        "target_not_known_production": not any(
            _contains_production_pattern(item)
            for item in (target.database_host, target.redis_host, target.target_base_host)
        ),
        "database_name_not_production_like": target.database_name not in PRODUCTION_DB_NAMES,
        "redis_policy_noeviction_declared": redis_policy == "noeviction",
        "redis_aof_enabled_declared": redis_aof_enabled,
        "celery_answer_flush_worker_declared": celery_answer_flush,
        "celery_answer_flush_queue_bound_declared": celery_queue_bound,
        "synthetic_data_ready_declared": synthetic_data_ready,
        "cleanup_plan_ready_declared": cleanup_ready,
        "real_execution_paths_present": False,
    }
    blocking = [name for name, passed in checks.items() if not passed]
    return {
        "readiness_check_only": True,
        "staging_environment_verified": False,
        "staging_readiness_result": "blocked" if blocking else "ready_for_review",
        "safe_to_execute_harness_now": False,
        "blocking_checks": blocking,
        "readiness_checks": checks,
        "database_host": _redact_id(target.database_host),
        "database_name": "[redacted]" if target.database_name else None,
        "redis_host": _redact_id(target.redis_host),
        "target_base_host": _redact_id(target.target_base_host),
        "real_execution_note": "scenario commands are still dry_run_stub; real staging DB/Redis execution is not implemented",
        "no_db_writes": True,
        "no_redis_writes": True,
        "cleanup_deletion_executed": False,
    }


def _base_result(
    *,
    scenario: str,
    env: Mapping[str, str],
    read_only: bool,
    writes_synthetic_only: bool,
) -> Dict[str, Any]:
    simulate_mismatch = int(env.get("STAGING_PROOF_SIMULATE_MISMATCH", "0") or 0)
    simulate_redis_errors = int(env.get("STAGING_PROOF_SIMULATE_REDIS_ERRORS", "0") or 0)
    simulate_missing = int(env.get("STAGING_PROOF_SIMULATE_MISSING_IN_REDIS", "0") or 0)
    simulate_extra = int(env.get("STAGING_PROOF_SIMULATE_EXTRA_IN_REDIS", "0") or 0)
    is_read_only = bool(read_only)
    final_submit_success = 0 if is_read_only else int(env.get("STAGING_PROOF_SIMULATE_FINAL_SUBMIT_SUCCESS", "0") or 0)
    final_submit_fail = int(env.get("STAGING_PROOF_SIMULATE_FINAL_SUBMIT_FAIL", "0") or 0)
    forced_flush_verified = bool(env.get("STAGING_PROOF_SIMULATE_FORCED_FLUSH_VERIFIED", "").lower() == "true")

    return {
        "git_head": _git_head(),
        "environment_type": "staging",
        "staging_guard_passed": True,
        "synthetic_prefix": REQUIRED_SYNTHETIC_MARKER,
        "scenario": scenario,
        "checked_sessions": int(env.get("STAGING_PROOF_SIMULATE_CHECKED_SESSIONS", "0") or 0),
        "checked_answers": int(env.get("STAGING_PROOF_SIMULATE_CHECKED_ANSWERS", "0") or 0),
        "payload_hash_mismatch": simulate_mismatch,
        "redis_errors": simulate_redis_errors,
        "missing_in_redis": simulate_missing,
        "extra_in_redis": simulate_extra,
        "answer_queue_pending": int(env.get("STAGING_PROOF_SIMULATE_PENDING", "0") or 0),
        "answer_queue_processing": int(env.get("STAGING_PROOF_SIMULATE_PROCESSING", "0") or 0),
        "answer_queue_deadletter": int(env.get("STAGING_PROOF_SIMULATE_DEADLETTER", "0") or 0),
        "runtime_answer_buffer_keys_count": int(
            env.get("STAGING_PROOF_SIMULATE_RUNTIME_BUFFER_KEYS", "0") or 0
        ),
        "answer_queue_keys_count": int(env.get("STAGING_PROOF_SIMULATE_ANSWER_QUEUE_KEYS", "0") or 0),
        "legacy_answer_queue_keys_count": int(
            env.get("STAGING_PROOF_SIMULATE_LEGACY_QUEUE_KEYS", "0") or 0
        ),
        "final_submit_success_count": final_submit_success,
        "final_submit_fail_count": final_submit_fail,
        "worker_restart_tested": scenario == "run-worker-restart" and not is_read_only,
        "redis_reconnect_tested": False,
        "forced_flush_verified": forced_flush_verified,
        "safe_to_continue": (
            simulate_mismatch == 0
            and simulate_redis_errors == 0
            and simulate_missing == 0
            and simulate_extra == 0
            and final_submit_fail == 0
        ),
        "read_only": is_read_only,
        "writes_synthetic_only": bool(writes_synthetic_only),
        "redacted": True,
        "execution_mode": "dry_run_stub",
    }


def _sanitize_output(payload: Mapping[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if lowered in SENSITIVE_OUTPUT_KEYS:
            continue
        if isinstance(value, Mapping):
            sanitized[key] = _sanitize_output(value)
        elif isinstance(value, list):
            sanitized[key] = ["[redacted-list-item]" if isinstance(item, Mapping) else item for item in value]
        else:
            sanitized[key] = value
    sanitized["redacted"] = True
    return sanitized


def should_fail_summary(result: Mapping[str, Any]) -> bool:
    failure_keys = [
        "payload_hash_mismatch",
        "redis_errors",
        "missing_in_redis",
        "extra_in_redis",
        "answer_queue_deadletter",
        "runtime_answer_buffer_keys_count",
        "answer_queue_keys_count",
        "legacy_answer_queue_keys_count",
        "final_submit_fail_count",
    ]
    return any(int(result.get(key, 0) or 0) > 0 for key in failure_keys)


def validate_staging_guards(args: argparse.Namespace, env: Mapping[str, str]) -> TargetInfo:
    if not getattr(args, CONFIRMATION_FLAG, False):
        raise GuardError("missing --i-understand-this-is-staging-only confirmation")

    if str(env.get(REQUIRED_STAGING_FLAG, "")).strip().lower() != "true":
        raise GuardError(f"{REQUIRED_STAGING_FLAG}=true is required")

    for key in ("APP_ENV", "ENVIRONMENT", "ENV"):
        value = str(env.get(key, "")).strip().lower()
        if value in PRODUCTION_ENV_VALUES:
            raise GuardError(f"refusing production environment via {key}")

    if hasattr(args, "synthetic_prefix"):
        prefix = str(getattr(args, "synthetic_prefix") or "")
        if REQUIRED_SYNTHETIC_MARKER not in prefix:
            raise GuardError(f"synthetic prefix must contain {REQUIRED_SYNTHETIC_MARKER}")

    target = _target_info(env)
    for candidate in (target.database_host, target.redis_host, target.target_base_host):
        if _contains_production_pattern(candidate):
            raise GuardError("refusing known production host/domain/IP")

    if target.database_name and target.database_name in PRODUCTION_DB_NAMES:
        raise GuardError("refusing production-like database name")

    allowed_db_hosts = _split_csv(env.get("STAGING_PROOF_ALLOWED_DB_HOSTS"))
    allowed_redis_hosts = _split_csv(env.get("STAGING_PROOF_ALLOWED_REDIS_HOSTS"))
    if not allowed_db_hosts:
        raise GuardError("STAGING_PROOF_ALLOWED_DB_HOSTS is required")
    if not allowed_redis_hosts:
        raise GuardError("STAGING_PROOF_ALLOWED_REDIS_HOSTS is required")
    if not target.database_host or target.database_host.lower() not in allowed_db_hosts:
        raise GuardError("database host is not in STAGING_PROOF_ALLOWED_DB_HOSTS")
    if not target.redis_host or target.redis_host.lower() not in allowed_redis_hosts:
        raise GuardError("Redis host is not in STAGING_PROOF_ALLOWED_REDIS_HOSTS")

    artifacts_dir = Path(env.get("STAGING_PROOF_ARTIFACT_DIR", "/tmp/ujianonline-staging-proof"))
    try:
        artifacts_dir.resolve().relative_to(ROOT.resolve())
        raise GuardError("temporary artifacts must be outside the Git tree")
    except ValueError:
        pass

    return target


def _add_common_flags(parser: argparse.ArgumentParser, *, synthetic_prefix: bool = False) -> None:
    parser.add_argument("--staging-only", action="store_true", help="Document that the target is staging-only.")
    parser.add_argument(
        "--i-understand-this-is-staging-only",
        dest=CONFIRMATION_FLAG,
        action="store_true",
        help="Required explicit confirmation that this is not production.",
    )
    parser.add_argument("--redact", dest="redact", action="store_true", default=True)
    parser.add_argument("--no-redact", dest="redact", action="store_false", help=argparse.SUPPRESS)
    if synthetic_prefix:
        parser.add_argument("--synthetic-prefix", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Staging-only forced-flush proof harness with hard production refusal guards.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Run guard-only preflight; no DB/Redis writes.")
    _add_common_flags(preflight)

    readiness = subparsers.add_parser(
        "inspect-readiness",
        help="Inspect declared staging readiness from environment; no DB/Redis writes.",
    )
    _add_common_flags(readiness)

    for command in sorted(SCENARIO_COMMANDS):
        scenario = subparsers.add_parser(command, help=f"Dry-run/stub structure for {command}.")
        _add_common_flags(scenario, synthetic_prefix=True)

    summarize = subparsers.add_parser("summarize", help="Emit sanitized summary gate result; no DB/Redis writes.")
    _add_common_flags(summarize)
    summarize.add_argument("--fail-on-mismatch", action="store_true")

    cleanup = subparsers.add_parser("cleanup-plan", help="Print reviewed cleanup plan only; no deletion.")
    _add_common_flags(cleanup)

    return parser


def run_command(args: argparse.Namespace, env: Mapping[str, str]) -> Dict[str, Any]:
    target = validate_staging_guards(args, env)
    command = str(args.command)

    if command == "preflight":
        result = _base_result(scenario=command, env=env, read_only=True, writes_synthetic_only=False)
        result.update(
            {
                "preflight_only": True,
                "no_db_writes": True,
                "no_redis_writes": True,
                "cleanup_deletion_executed": False,
            }
        )
        return _sanitize_output(result)

    if command == "inspect-readiness":
        result = _base_result(scenario=command, env=env, read_only=True, writes_synthetic_only=False)
        result.update(_readiness_report(env, target))
        result["safe_to_continue"] = False
        return _sanitize_output(result)

    if command == "summarize":
        result = _base_result(scenario=command, env=env, read_only=True, writes_synthetic_only=False)
        result.update(
            {
                "summary_only": True,
                "no_db_writes": True,
                "no_redis_writes": True,
                "cleanup_deletion_executed": False,
            }
        )
        return _sanitize_output(result)

    if command == "cleanup-plan":
        result = _base_result(scenario=command, env=env, read_only=True, writes_synthetic_only=False)
        result.update(
            {
                "cleanup_plan_only": True,
                "cleanup_deletion_executed": False,
                "cleanup_requires_separate_approval": True,
                "allowed_cleanup_scope": "exact synthetic keys only after review; no broad Redis deletion",
            }
        )
        return _sanitize_output(result)

    if command in SCENARIO_COMMANDS:
        result = _base_result(scenario=command, env=env, read_only=False, writes_synthetic_only=True)
        result.update(
            {
                "synthetic_prefix": REQUIRED_SYNTHETIC_MARKER,
                "planned_only": True,
                "no_production_target": True,
                "raw_values_printed": False,
            }
        )
        return _sanitize_output(result)

    raise GuardError(f"unsupported command: {command}")


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    effective_env: Mapping[str, str] = env if env is not None else os.environ
    try:
        result = run_command(args, effective_env)
    except GuardError as exc:
        error = {
            "git_head": _git_head(),
            "environment_type": "unknown",
            "staging_guard_passed": False,
            "scenario": getattr(args, "command", "unknown"),
            "safe_to_continue": False,
            "read_only": True,
            "writes_synthetic_only": False,
            "redacted": True,
            "error": str(exc),
        }
        print(json.dumps(_sanitize_output(error), sort_keys=True))
        return 2

    print(json.dumps(result, sort_keys=True))
    if getattr(args, "command", "") == "summarize" and getattr(args, "fail_on_mismatch", False):
        return 2 if should_fail_summary(result) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
