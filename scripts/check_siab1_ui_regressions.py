#!/usr/bin/env python3
"""Static guardrails for SIAB1 UI/branding regressions.

The checks intentionally focus on runtime-visible UI sources and scoped CSS risk
patterns from the SIAB1 redesign review. Technical identifiers such as
``ujian_online`` are allowed because they are repository/package/schema names,
not visible legacy branding.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]

LEGACY_BRANDING = (
    "Admin Ujian Online",
    "Sistem Ujian Online",
    "Ujian Online System",
    "Ujian Online",
)

# Runtime-visible sources. Docs and maintenance scripts are deliberately not in
# this list so exact legacy values can be documented or used by opt-in cleanup
# scripts without failing the UI regression gate.
BRANDING_SCAN_PATHS = (
    "app/config.py",
    "app/models/system_settings.py",
    "app/locales/id.json",
    "app/main.py",
    "app/utils/telegram_alerts.py",
    "app/core/pdf_generator.py",
    "templates",
    "static/components",
    "static/css",
    "static/js",
    "static/sw.js",
    "flutter_client_code/lib",
    "flutter_client_code/test",
    "flutter_client_code/pubspec.yaml",
    "flutter_client_code/android/app/proguard-rules.pro",
    "flutter_client_code/android/app/src/main/AndroidManifest.xml",
    "flutter_client_code/android_src/AndroidManifest.xml",
    "tools/apk_builder_gui.py",
    "tools/apk_builder_gui",
)

TEXT_SUFFIXES = {
    ".py",
    ".json",
    ".html",
    ".css",
    ".js",
    ".dart",
    ".yaml",
    ".yml",
    ".md",
    ".pro",
    ".xml",
}
CSS_FILE_SOURCES = (
    "static/css/siab1-theme.css",
    "static/css/exam.css",
    "static/css/student.css",
)
CSS_TEMPLATE_SOURCES = (
    "templates/admin/settings.html",
    "templates/admin/analytics.html",
    "templates/admin/system-monitor.html",
    "templates/student/exam.html",
)


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def _iter_files(root: Path, entries: Iterable[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for entry in entries:
        path = root / entry
        if not path.exists():
            continue
        files = path.rglob("*") if path.is_dir() else (path,)
        for file_path in files:
            if not file_path.is_file() or file_path.suffix not in TEXT_SUFFIXES:
                continue
            ignored_parts = {"build", ".dart_tool", "node_modules", "__pycache__"}
            if any(part in ignored_parts for part in file_path.parts):
                continue
            resolved = file_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield file_path


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def check_legacy_branding(root: Path = REPO_ROOT) -> list[Issue]:
    issues: list[Issue] = []
    for file_path in _iter_files(root, BRANDING_SCAN_PATHS):
        rel = file_path.relative_to(root).as_posix()
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for legacy in LEGACY_BRANDING:
            for match in re.finditer(re.escape(legacy), text):
                issues.append(
                    Issue(
                        rel,
                        _line_number(text, match.start()),
                        f"legacy runtime branding {legacy!r}; use 'SIAB1' or the official SIAB1 subtitle",
                    )
                )
    return issues


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _iter_css_rules(css: str) -> Iterable[tuple[int, str, str]]:
    css = _strip_css_comments(css)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, flags=re.S):
        selector = " ".join(match.group(1).split())
        body = match.group(2)
        yield _line_number(css, match.start(1)), selector, body


def _selector_items(selector: str) -> list[str]:
    return [item.strip() for item in selector.split(",") if item.strip()]


def _is_bare_progress_selector(selector: str) -> bool:
    return bool(re.match(r"^\.progress-(?:bar|fill)(?:$|[\s:.#\[])", selector))


def _is_bare_heading_selector(selector: str) -> bool:
    return selector in {"h1", "h2", "h3", "h4", "h5", "h6"}


def _css_sources(root: Path) -> Iterable[tuple[str, str]]:
    for rel in CSS_FILE_SOURCES:
        path = root / rel
        if path.exists():
            yield rel, path.read_text(encoding="utf-8", errors="ignore")

    style_re = re.compile(r"<style[^>]*>(.*?)</style>", re.I | re.S)
    for rel in CSS_TEMPLATE_SOURCES:
        path = root / rel
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8", errors="ignore")
        for idx, match in enumerate(style_re.finditer(html), start=1):
            yield f"{rel}#style-{idx}", match.group(1)


def check_css_selectors(root: Path = REPO_ROOT) -> list[Issue]:
    issues: list[Issue] = []
    for label, css in _css_sources(root):
        for line, selector, body in _iter_css_rules(css):
            selectors = _selector_items(selector)
            if any(_is_bare_progress_selector(item) for item in selectors):
                issues.append(
                    Issue(
                        label,
                        line,
                        "unscoped .progress-bar/.progress-fill selector; scope it to exam/admin component DOM",
                    )
                )
            has_global_card_color = any(
                re.search(r"\.card\s+\*", item) for item in selectors
            ) and re.search(r"\bcolor\s*:", body)
            if has_global_card_color:
                issues.append(
                    Issue(
                        label,
                        line,
                        "global '.card *' color override is not allowed; use semantic surface classes",
                    )
                )
            if any(_is_bare_heading_selector(item) for item in selectors) and re.search(r"\bcolor\s*:", body):
                issues.append(
                    Issue(
                        label,
                        line,
                        "bare heading color override can break dark surfaces; scope to SIAB1 surfaces",
                    )
                )
    return issues


def check_settings_inline_contrast(root: Path = REPO_ROOT) -> list[Issue]:
    path = root / "templates/admin/settings.html"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    issues: list[Issue] = []

    risky_inline = re.compile(
        r"<(?:h[1-6]|strong)\b[^>]*style=[\"'][^\"']*color\s*:\s*(?:white|#fff(?:fff)?)\b",
        re.I,
    )
    for match in risky_inline.finditer(text):
        issues.append(
            Issue(
                "templates/admin/settings.html",
                _line_number(text, match.start()),
                "inline white heading/strong text in settings can disappear on SIAB1 light cards",
            )
        )

    form_control_white = re.compile(
        r"\.form-control\s*\{[^{}]*color\s*:\s*white\s*!important",
        re.I | re.S,
    )
    for match in form_control_white.finditer(text):
        issues.append(
            Issue(
                "templates/admin/settings.html",
                _line_number(text, match.start()),
                "settings form controls must not force white text on light SIAB1 inputs",
            )
        )
    return issues


def run_checks(root: Path = REPO_ROOT) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(check_legacy_branding(root))
    issues.extend(check_css_selectors(root))
    issues.extend(check_settings_inline_contrast(root))
    return sorted(issues, key=lambda issue: (issue.path, issue.line, issue.message))


def main() -> int:
    issues = run_checks()
    if issues:
        print("SIAB1 UI regression check failed:")
        for issue in issues:
            print(f"  - {issue.format()}")
        return 1
    print("SIAB1 UI regression check passed: branding, contrast, and scoped CSS guardrails are clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
