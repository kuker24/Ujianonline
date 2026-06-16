#!/usr/bin/env python3
"""Normalize legacy SIAB1 app_name values in system_settings.

This maintenance script is intentionally opt-in. It is never imported by the
application startup path and only updates app_name when the current value is an
exact legacy branding value.

Usage:
    python scripts/normalize_siab1_branding.py --dry-run
    python scripts/normalize_siab1_branding.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.config import settings
except ModuleNotFoundError as import_error:  # pragma: no cover - environment guardrail
    settings = None
    CONFIG_IMPORT_ERROR = import_error
else:
    CONFIG_IMPORT_ERROR = None

try:
    from sqlalchemy import bindparam, text
    from sqlalchemy.ext.asyncio import create_async_engine
except ModuleNotFoundError as import_error:  # pragma: no cover - environment guardrail
    bindparam = None
    text = None
    create_async_engine = None
    SQLALCHEMY_IMPORT_ERROR = import_error
else:
    SQLALCHEMY_IMPORT_ERROR = None


LEGACY_APP_NAMES: tuple[str, ...] = (
    "Ujian Online",
    "Sistem Ujian Online",
    "Ujian Online System",
    "Admin Ujian Online",
)
TARGET_APP_NAME = "SIAB1"


@dataclass(frozen=True)
class BrandingRow:
    id: int
    before: str
    after: str = TARGET_APP_NAME


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize exact legacy system_settings.app_name values to SIAB1.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Preview rows without updating data.")
    mode.add_argument("--apply", action="store_true", help="Apply idempotent app_name updates.")
    return parser


def _async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def _safe_database_label(database_url: str) -> str:
    parsed = urlparse(database_url)
    host = parsed.hostname or "unknown-host"
    database = parsed.path.lstrip("/") or "unknown-db"
    return f"{host}/{database}"


def _validate_database_url() -> str:
    if CONFIG_IMPORT_ERROR is not None or settings is None:
        raise RuntimeError(
            "Application dependencies are required to load app.config. "
            "Run this script from the application environment after installing requirements.txt."
        ) from CONFIG_IMPORT_ERROR

    database_url = (settings.database_url or "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set the application database configuration "
            "before running this maintenance script."
        )
    return _async_database_url(database_url)


async def _fetch_legacy_rows(conn) -> list[BrandingRow]:
    stmt = text(
        "SELECT id, app_name FROM system_settings "
        "WHERE app_name IN :legacy_names ORDER BY id"
    ).bindparams(bindparam("legacy_names", expanding=True))
    result = await conn.execute(stmt, {"legacy_names": LEGACY_APP_NAMES})
    return [BrandingRow(id=int(row.id), before=str(row.app_name)) for row in result]


def _print_plan(rows: Iterable[BrandingRow], *, dry_run: bool) -> None:
    prefix = "[DRY-RUN]" if dry_run else "[APPLY]"
    rows = list(rows)
    if not rows:
        print(f"{prefix} No legacy app_name values found. Nothing to change.")
        return
    for row in rows:
        print(f"{prefix} system_settings.id={row.id}: {row.before!r} -> {row.after!r}")


async def _run(*, apply: bool) -> int:
    if SQLALCHEMY_IMPORT_ERROR is not None:
        raise RuntimeError(
            "SQLAlchemy is required. Run this script from the application environment "
            "after installing requirements.txt."
        ) from SQLALCHEMY_IMPORT_ERROR

    database_url = _validate_database_url()
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=settings.db_pool_pre_ping,
    )
    print(f"Database target: {_safe_database_label(database_url)}")

    try:
        if apply:
            async with engine.begin() as conn:
                rows = await _fetch_legacy_rows(conn)
                _print_plan(rows, dry_run=False)
                for row in rows:
                    await conn.execute(
                        text(
                            "UPDATE system_settings "
                            "SET app_name = :after, updated_at = NOW() "
                            "WHERE id = :id AND app_name = :before"
                        ),
                        {"id": row.id, "before": row.before, "after": row.after},
                    )
                if rows:
                    print(f"[APPLY] Updated {len(rows)} row(s).")
        else:
            async with engine.connect() as conn:
                rows = await _fetch_legacy_rows(conn)
                _print_plan(rows, dry_run=True)
        return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(apply=args.apply))
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
