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
from typing import Any, Callable, Iterable, Protocol
from urllib.parse import urlparse, urlunparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LEGACY_APP_NAMES: tuple[str, ...] = (
    "Ujian Online",
    "Sistem Ujian Online",
    "Ujian Online System",
    "Admin Ujian Online",
)
TARGET_APP_NAME = "SIAB1"


class SettingsLike(Protocol):
    database_url: str
    db_pool_pre_ping: bool


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


def load_application_settings() -> SettingsLike:
    """Load app settings lazily so importing this script never needs app deps/env."""
    try:
        from app.config import settings
    except Exception as exc:  # pragma: no cover - exercised via CLI/integration tests
        raise RuntimeError(
            "Konfigurasi aplikasi tidak dapat dimuat. Pastikan dependency dan environment "
            "aplikasi tersedia."
        ) from exc
    return settings


def load_sqlalchemy_async() -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    """Load SQLAlchemy lazily and return create_async_engine, text, bindparam."""
    try:
        from sqlalchemy import bindparam, text
        from sqlalchemy.ext.asyncio import create_async_engine
    except Exception as exc:  # pragma: no cover - exercised via CLI/integration tests
        raise RuntimeError(
            "SQLAlchemy async tidak tersedia. Jalankan dari environment aplikasi setelah "
            "dependency requirements.txt terpasang."
        ) from exc
    return create_async_engine, text, bindparam


def async_database_url(database_url: str) -> str:
    """Convert a sync PostgreSQL URL to the asyncpg SQLAlchemy form."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def safe_database_label(database_url: str) -> str:
    """Return host/db only; never include username, password, or full URL."""
    parsed = urlparse(database_url)
    hostname = parsed.hostname or "unknown-host"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/") or "unknown-db"
    return f"{hostname}{port}/{database}"


def redacted_database_url(database_url: str) -> str:
    """Return a password-safe URL useful for tests/logging if ever needed."""
    parsed = urlparse(database_url)
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def validate_database_url(settings: SettingsLike) -> str:
    database_url = (getattr(settings, "database_url", "") or "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL tidak tersedia. Konfigurasikan database aplikasi sebelum "
            "menjalankan maintenance script ini."
        )
    return async_database_url(database_url)


async def fetch_legacy_rows(conn: Any, *, text_fn: Callable[..., Any], bindparam_fn: Callable[..., Any]) -> list[BrandingRow]:
    stmt = text_fn(
        "SELECT id, app_name FROM system_settings "
        "WHERE app_name IN :legacy_names ORDER BY id"
    ).bindparams(bindparam_fn("legacy_names", expanding=True))
    result = await conn.execute(stmt, {"legacy_names": LEGACY_APP_NAMES})
    return [BrandingRow(id=int(row.id), before=str(row.app_name)) for row in result]


async def apply_rows(conn: Any, rows: Iterable[BrandingRow], *, text_fn: Callable[..., Any]) -> int:
    updated = 0
    for row in rows:
        result = await conn.execute(
            text_fn(
                "UPDATE system_settings "
                "SET app_name = :after, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = :id AND app_name = :before"
            ),
            {"id": row.id, "before": row.before, "after": row.after},
        )
        rowcount = getattr(result, "rowcount", None)
        updated += 1 if rowcount is None else int(rowcount)
    return updated


def print_plan(rows: Iterable[BrandingRow], *, dry_run: bool, print_fn: Callable[[str], None]) -> None:
    prefix = "[DRY-RUN]" if dry_run else "[APPLY]"
    rows = list(rows)
    if not rows:
        print_fn(f"{prefix} No legacy app_name values found. Nothing to change.")
        return
    for row in rows:
        print_fn(f"{prefix} system_settings.id={row.id}: {row.before!r} -> {row.after!r}")


async def run_normalization(
    *,
    apply: bool,
    settings_loader: Callable[[], SettingsLike] = load_application_settings,
    sqlalchemy_loader: Callable[[], tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]] = load_sqlalchemy_async,
    print_fn: Callable[[str], None] = print,
) -> int:
    settings = settings_loader()
    database_url = validate_database_url(settings)
    create_async_engine, text_fn, bindparam_fn = sqlalchemy_loader()

    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=bool(getattr(settings, "db_pool_pre_ping", True)),
    )
    print_fn(f"Database target: {safe_database_label(database_url)}")

    try:
        if apply:
            async with engine.begin() as conn:
                rows = await fetch_legacy_rows(conn, text_fn=text_fn, bindparam_fn=bindparam_fn)
                print_plan(rows, dry_run=False, print_fn=print_fn)
                updated = await apply_rows(conn, rows, text_fn=text_fn)
                print_fn(f"[APPLY] Updated {updated} row(s).")
        else:
            async with engine.connect() as conn:
                rows = await fetch_legacy_rows(conn, text_fn=text_fn, bindparam_fn=bindparam_fn)
                print_plan(rows, dry_run=True, print_fn=print_fn)
                print_fn(f"[DRY-RUN] Matched {len(rows)} row(s); no UPDATE executed.")
        return 0
    finally:
        await engine.dispose()


def run_cli(
    argv: list[str] | None = None,
    *,
    settings_loader: Callable[[], SettingsLike] = load_application_settings,
    sqlalchemy_loader: Callable[[], tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]] = load_sqlalchemy_async,
    print_fn: Callable[[str], None] = print,
    error_print_fn: Callable[[str], None] | None = None,
) -> int:
    error_print_fn = error_print_fn or (lambda message: print(message, file=sys.stderr))
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    try:
        return asyncio.run(
            run_normalization(
                apply=args.apply,
                settings_loader=settings_loader,
                sqlalchemy_loader=sqlalchemy_loader,
                print_fn=print_fn,
            )
        )
    except Exception as exc:
        error_print_fn(f"ERROR: {exc}")
        return 2


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
