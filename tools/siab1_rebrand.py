#!/usr/bin/env python3
"""Apply and verify the SIAB1 visible-brand migration.

This tool intentionally does not rename compatibility-sensitive identifiers such as
repository names, package IDs, database/service names, URLs, migration keys, or
paths containing ``ujian_online``.
"""
from __future__ import annotations

import argparse
import json
import py_compile
from dataclasses import dataclass
from pathlib import Path

SHORT_NAME = "SIAB1"
FULL_NAME = "SIAB1 — Sistem Informasi Asesmen Berintegritas"

REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("UJIAN ONLINE MAN 1 Rokan Hulu", FULL_NAME),
    ("Ujian Online MAN 1 Rokan Hulu", FULL_NAME),
    ("SISTEM UJIAN ONLINE ENTERPRISE-GRADE", FULL_NAME),
    ("Sistem Ujian Online Enterprise-Grade", FULL_NAME),
    ("SISTEM UJIAN ONLINE", FULL_NAME),
    ("Sistem Ujian Online", FULL_NAME),
    ("Ujian Online System", SHORT_NAME),
    ("UJIAN ONLINE SYSTEM", SHORT_NAME),
    ("Tim Ujian Online", "Tim SIAB1"),
    ("UJIAN ONLINE SEB", SHORT_NAME),
    ("Ujian Online", SHORT_NAME),
    ("UJIAN ONLINE", SHORT_NAME),
    ("ujian online", SHORT_NAME),
)

SKIP_DIRS = {
    ".git", ".dart_tool", ".gradle", "build", "__pycache__", "node_modules",
    ".venv", "venv",
}
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".apk",
    ".aab", ".zip", ".gz", ".tar", ".7z", ".jar", ".jks", ".keystore",
    ".so", ".class", ".woff", ".woff2", ".ttf", ".otf", ".db", ".sqlite",
    ".pyc",
}
SELF_PATH = "tools/siab1_rebrand.py"
AUDIT_PATH = "docs/SIAB1_REBRAND_AUDIT_20260616.md"
MAX_TEXT_SIZE = 2_000_000


@dataclass(frozen=True)
class Change:
    path: str
    replacements: int


def iter_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in {SELF_PATH, AUDIT_PATH}:
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_TEXT_SIZE:
                continue
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        yield path, rel, text


def apply(root: Path, dry_run: bool = False) -> tuple[list[Change], dict[str, int]]:
    changes: list[Change] = []
    totals: dict[str, int] = {}
    for path, rel, original in iter_text_files(root):
        updated = original
        count = 0
        for old, new in REPLACEMENTS:
            found = updated.count(old)
            if found:
                updated = updated.replace(old, new)
                totals[old] = totals.get(old, 0) + found
                count += found
        if updated != original:
            changes.append(Change(rel, count))
            if not dry_run:
                path.write_text(updated, encoding="utf-8")
    return changes, totals


def validate(root: Path) -> list[str]:
    failures: list[str] = []
    required = {
        "app/config.py": SHORT_NAME,
        "app/models/system_settings.py": SHORT_NAME,
        "templates/base.html": SHORT_NAME,
        "flutter_client_code/lib/config.dart": SHORT_NAME,
        "flutter_client_code/android/app/src/main/AndroidManifest.xml": SHORT_NAME,
        "tools/apk_builder_gui.py": SHORT_NAME,
    }
    for rel, needle in required.items():
        path = root / rel
        if not path.exists():
            failures.append(f"missing required file: {rel}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append(f"cannot read {rel}: {exc}")
            continue
        if needle not in text:
            failures.append(f"{rel}: missing {needle}")

    forbidden = ("Ujian Online", "UJIAN ONLINE", "ujian online", "Sistem Ujian Online")
    for _path, rel, text in iter_text_files(root):
        for phrase in forbidden:
            if phrase in text:
                failures.append(f"{rel}: old visible phrase {phrase!r}")
                break

    for path in sorted((root / "app").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"python compile failed: {path.relative_to(root)}: {exc.msg}")
    return failures


def write_audit(root: Path, changes: list[Change], totals: dict[str, int], failures: list[str]) -> None:
    audit = root / AUDIT_PATH
    audit.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SIAB1 Rebrand Audit",
        "",
        "Date: 2026-06-16",
        "",
        "## Canonical brand",
        "",
        f"- Short name: `{SHORT_NAME}`",
        f"- Full name: `{FULL_NAME}`",
        "",
        "## Scope",
        "",
        "Visible product branding was replaced across UTF-8 source code, templates, Flutter/Android configuration, JavaScript, scripts, configuration, and documentation.",
        "",
        "Compatibility-sensitive technical identifiers were intentionally preserved: repository name `Ujianonline`, package IDs, URLs, migration identifiers, deployment paths, and database/service tokens such as `ujian_online`.",
        "",
        f"## Files changed ({len(changes)})",
        "",
    ]
    lines.extend(f"- `{item.path}` ({item.replacements} replacement(s))" for item in changes)
    lines.extend(["", "## Replacement totals", ""])
    lines.extend(f"- `{old}`: {count}" for old, count in sorted(totals.items()))
    lines.extend(["", "## Validation", ""])
    if failures:
        lines.append("Status: **FAILED**")
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.extend([
            "Status: **PASS**",
            "- Required backend, web, Flutter, Android manifest, and APK Builder GUI files contain `SIAB1`.",
            "- No old visible branding phrase remains in scanned UTF-8 sources.",
            "- Python files under `app/` compile successfully.",
        ])
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    root = args.root.resolve()
    changes: list[Change] = []
    totals: dict[str, int] = {}
    if not args.validate_only:
        changes, totals = apply(root, dry_run=args.dry_run)
    failures = validate(root) if args.validate_only or not args.dry_run else []
    if not args.dry_run:
        write_audit(root, changes, totals, failures)

    payload = {
        "brand": FULL_NAME,
        "root": str(root),
        "dry_run": args.dry_run,
        "changed_files": len(changes),
        "replacement_count": sum(totals.values()),
        "failures": failures,
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Brand: {FULL_NAME}")
        print(f"Changed files: {len(changes)}")
        print(f"Replacements: {sum(totals.values())}")
        print("Validation: PASS" if not failures else "Validation: FAILED")
        for failure in failures:
            print(f"- {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
