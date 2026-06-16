#!/usr/bin/env python3
"""Static guardrails for SIAB1 UI/branding regressions.

The checks intentionally focus on runtime-visible UI sources and scoped CSS risk
patterns from the SIAB1 redesign review. Technical identifiers such as
``ujian_online`` are allowed because they are repository/package/schema names,
not visible legacy branding.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "67fca39f4b3ec9509381f68917caaa4477d19ca9"
THEME_HREF = "/static/css/siab1-theme.css"
BRANDING_HREF = "/static/css/siab1-branding.css"
RELEASE_TOKEN = "20260617-siab1-legacy-ui1"
CONTROLLED_RUNTIME_ASSETS = (
    "/static/css/admin.css",
    "/static/css/student.css",
    "/static/css/exam.css",
    "/static/css/responsive.css",
    "/static/css/siab1-branding.css",
    "/static/js/sidebar-loader.js",
    "/static/js/api.js",
    "/static/js/auth.js",
    "/static/js/exam-system.js",
    "/static/js/profile-modal.js",
)
SERVICE_WORKER_CACHE_ASSETS = (
    "/static/css/admin.css",
    "/static/css/student.css",
    "/static/css/exam.css",
    "/static/css/responsive.css",
    "/static/css/siab1-branding.css",
    "/static/js/auth.js",
    "/static/js/api.js",
    "/static/js/sidebar-loader.js",
    "/static/js/exam-system.js",
)
STALE_CACHE_TOKENS = (
    "20260430-perf1",
    "20260418-richtext1",
    "20260610-siab1-ui1",
    "20260616-siab1-ui2",
)
SEMANTIC_SURFACES = {
    "siab1-surface",
    "siab1-dark-surface",
    "siab1-brand-surface",
    "siab1-warning-surface",
}

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
    "static/css/siab1-branding.css",
    "static/css/admin.css",
    "static/css/exam.css",
    "static/css/student.css",
    "static/css/responsive.css",
)
CSS_TEMPLATE_SOURCES = (
    "templates/admin/settings.html",
    "templates/admin/analytics.html",
    "templates/admin/system-monitor.html",
    "templates/student/exam.html",
)
TEMPLATE_THEME_SCAN_ROOTS = (
    "templates/admin",
    "templates/student",
    "templates/seb",
)
TEMPLATE_THEME_SCAN_FILES = ("templates/base.html",)

# Explicit duplicate IDs that already exist as alternate exam navigator shells.
# They are preserved to avoid changing DOM contracts used by existing JS.
ALLOWED_DUPLICATE_IDS = {
    "templates/student/exam.html": {
        "question-container",
        "question-navigator",
        "sidebar-panel",
        "answered-count",
        "flagged-count",
        "remaining-count",
    }
}

PRESERVED_DIFF_PATTERNS = (
    re.compile(r"\bid\s*="),
    re.compile(r"\bon(?:click|change|submit)\s*="),
    re.compile(r"\bname\s*="),
    re.compile(r"\btype\s*=\s*['\"](?:submit|button|reset|checkbox|radio|hidden)['\"]", re.I),
    re.compile(r"['\"]/(?:api|admin|student|seb|ws)[^'\"]*['\"]"),
)


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


@dataclass
class CardInventory:
    total_card: int = 0
    light_surface: int = 0
    dark_surface: int = 0
    brand_surface: int = 0
    warning_surface: int = 0
    unclassified: int = 0


class ElementCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[int, str, dict[str, str]]] = []
        self.ids: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: (value or "") for key, value in attrs}
        self.elements.append((self.getpos()[0], tag, attr_map))
        element_id = attr_map.get("id")
        if element_id:
            self.ids.append((self.getpos()[0], element_id))


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


def _parse_html(path: Path) -> ElementCollector:
    parser = ElementCollector()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    return parser


def _class_tokens(attr_map: dict[str, str]) -> set[str]:
    return set((attr_map.get("class") or "").split())


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


def admin_card_inventory(
    root: Path = REPO_ROOT,
    *,
    allowlist: dict[str, set[str]] | None = None,
) -> tuple[dict[str, CardInventory], list[Issue]]:
    allowlist = allowlist or {}
    issues: list[Issue] = []
    inventory: dict[str, CardInventory] = {}
    for file_path in sorted((root / "templates" / "admin").rglob("*.html")):
        rel = file_path.relative_to(root).as_posix()
        parser = _parse_html(file_path)
        item = CardInventory()
        for line, _tag, attrs in parser.elements:
            tokens = _class_tokens(attrs)
            if "card" not in tokens:
                continue
            item.total_card += 1
            surfaces = tokens & SEMANTIC_SURFACES
            if "siab1-surface" in surfaces:
                item.light_surface += 1
            if "siab1-dark-surface" in surfaces:
                item.dark_surface += 1
            if "siab1-brand-surface" in surfaces:
                item.brand_surface += 1
            if "siab1-warning-surface" in surfaces:
                item.warning_surface += 1
            if not surfaces:
                element_id = attrs.get("id", "")
                if element_id and element_id in allowlist.get(rel, set()):
                    continue
                item.unclassified += 1
                issues.append(
                    Issue(
                        rel,
                        line,
                        "admin .card element must declare a SIAB1 semantic surface class",
                    )
                )
        inventory[rel] = item
    return inventory, issues


def check_admin_card_surfaces(root: Path = REPO_ROOT) -> list[Issue]:
    _inventory, issues = admin_card_inventory(root)
    return issues


def _templates_for_theme_scan(root: Path) -> Iterable[Path]:
    for rel in TEMPLATE_THEME_SCAN_FILES:
        path = root / rel
        if path.exists():
            yield path
    for rel in TEMPLATE_THEME_SCAN_ROOTS:
        base = root / rel
        if base.exists():
            yield from sorted(base.rglob("*.html"))


def check_theme_includes(root: Path = REPO_ROOT) -> list[Issue]:
    """The broad SIAB1 redesign theme must not be loaded on legacy UI pages."""
    issues: list[Issue] = []
    for path in _templates_for_theme_scan(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "<head" not in text.lower():
            continue
        for match in re.finditer(re.escape(THEME_HREF), text):
            issues.append(
                Issue(
                    rel,
                    _line_number(text, match.start()),
                    "siab1-theme.css must not be loaded globally; keep legacy CSS as the visual source of truth",
                )
            )
        branding_count = text.count(BRANDING_HREF)
        if branding_count > 1:
            issues.append(Issue(rel, 1, f"SIAB1 branding CSS must be included at most once, found {branding_count}"))

        is_admin_like = rel.startswith("templates/admin/") or rel.startswith("templates/seb/")
        is_student_like = rel.startswith("templates/student/")
        if is_admin_like and "templates/admin/index.html" != rel and "templates/seb/landing.html" != rel:
            if "/static/css/admin.css" not in text:
                issues.append(Issue(rel, 1, "legacy admin.css must remain loaded"))
        if is_student_like and rel != "templates/student/index.html" and "/static/css/student.css" not in text:
            issues.append(Issue(rel, 1, "legacy student.css must remain loaded"))
        if rel == "templates/base.html" and "/static/css/exam.css" not in text:
            issues.append(Issue(rel, 1, "legacy exam.css must remain loaded"))
    return issues


def _controlled_asset_pattern(asset: str) -> re.Pattern[str]:
    return re.compile(re.escape(asset) + r"(?:\?v=([^\"'\s)<>]+))?")


def _runtime_cache_scan_files(root: Path) -> Iterable[Path]:
    yield from _templates_for_theme_scan(root)
    for rel in (
        "static/sw.js",
        "static/js/sidebar-loader.js",
        "static/js/sidebar-loader/modules/00-sidebar-loader-core.js",
        "docker/nginx.production.conf",
    ):
        path = root / rel
        if path.exists():
            yield path


def check_static_cache_versions(root: Path = REPO_ROOT) -> list[Issue]:
    """Ensure SIAB1 rollout assets cannot be pinned by old production caches."""
    issues: list[Issue] = []

    for path in _templates_for_theme_scan(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        for asset in CONTROLLED_RUNTIME_ASSETS:
            for match in _controlled_asset_pattern(asset).finditer(text):
                token = match.group(1)
                if token != RELEASE_TOKEN:
                    issues.append(
                        Issue(
                            rel,
                            _line_number(text, match.start()),
                            f"{asset} must use release token v={RELEASE_TOKEN}",
                        )
                    )

    for rel in (
        "static/js/sidebar-loader/modules/00-sidebar-loader-core.js",
        "static/js/sidebar-loader.js",
    ):
        path = root / rel
        if not path.exists():
            issues.append(Issue(rel, 1, "sidebar loader source/bundle is missing"))
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        expected = f"const componentVersion = '{RELEASE_TOKEN}';"
        if expected not in text:
            issues.append(Issue(rel, 1, f"sidebar componentVersion must be {RELEASE_TOKEN}"))

    sw_path = root / "static/sw.js"
    if sw_path.exists():
        sw_text = sw_path.read_text(encoding="utf-8", errors="ignore")
        expected_cache = f"const CACHE_NAME = 'siab1-v{RELEASE_TOKEN}';"
        if expected_cache not in sw_text:
            issues.append(Issue("static/sw.js", 1, f"service worker CACHE_NAME must be siab1-v{RELEASE_TOKEN}"))
        for asset in SERVICE_WORKER_CACHE_ASSETS:
            expected_asset = f"'{asset}?v={RELEASE_TOKEN}'"
            if expected_asset not in sw_text:
                issues.append(Issue("static/sw.js", 1, f"CACHE_ASSETS must include {asset}?v={RELEASE_TOKEN}"))
    else:
        issues.append(Issue("static/sw.js", 1, "service worker file is missing"))

    nginx_path = root / "docker/nginx.production.conf"
    if nginx_path.exists():
        nginx_text = nginx_path.read_text(encoding="utf-8", errors="ignore")
        sw_pos = nginx_text.find("location = /static/sw.js")
        static_pos = nginx_text.find("location /static/")
        if sw_pos == -1:
            issues.append(Issue("docker/nginx.production.conf", 1, "/static/sw.js no-cache location is required"))
        elif static_pos != -1 and sw_pos > static_pos:
            issues.append(Issue("docker/nginx.production.conf", 1, "/static/sw.js location must appear before /static/"))
        if sw_pos != -1:
            block = nginx_text[sw_pos : static_pos if static_pos != -1 and static_pos > sw_pos else len(nginx_text)]
            if "no-store" not in block or "no-cache" not in block or "max-age=0" not in block:
                issues.append(Issue("docker/nginx.production.conf", 1, "/static/sw.js must send no-store/no-cache headers"))
    else:
        issues.append(Issue("docker/nginx.production.conf", 1, "production Nginx config is missing"))

    for path in _runtime_cache_scan_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        for stale_token in STALE_CACHE_TOKENS:
            for match in re.finditer(re.escape(stale_token), text):
                issues.append(
                    Issue(rel, _line_number(text, match.start()), f"stale cache token {stale_token!r} must not remain in runtime assets")
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


def _contains_color_property(body: str) -> bool:
    return bool(re.search(r"\b(?:color|background|background-color|-webkit-text-fill-color)\s*:", body))


def check_branding_css_scope(root: Path = REPO_ROOT) -> list[Issue]:
    path = root / "static/css/siab1-branding.css"
    if not path.exists():
        return [Issue("static/css/siab1-branding.css", 1, "branding-only CSS file is required")]

    text = path.read_text(encoding="utf-8", errors="ignore")
    issues: list[Issue] = []
    forbidden_patterns = (
        (r"(^|[^\w-])body($|[^\w-])", "body selector is not allowed in branding CSS"),
        (r"(^|[^\w-])\.card($|[^\w-])", ".card selector is not allowed in branding CSS"),
        (r"(^|[^\w-])\.sidebar(?!-header)(?:$|[^\w-])", "generic .sidebar selector is not allowed in branding CSS"),
        (r"\.main-content(?:$|[^\w-])", ".main-content selector is not allowed in branding CSS"),
        (r"\.page-header(?:$|[^\w-])", ".page-header selector is not allowed in branding CSS"),
        (r"color-scheme\s*:", "color-scheme is not allowed in branding CSS"),
        (r"--(?:dark-bg|dark-card|dark-hover|glass-bg|glass-border|text-primary|text-secondary|bg-card)\s*:", "legacy surface variables must not be redefined in branding CSS"),
        (r"!important", "!important is not allowed in branding CSS"),
    )
    for pattern, message in forbidden_patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            issues.append(Issue("static/css/siab1-branding.css", _line_number(text, match.start()), message))

    allowed_prefixes = (
        ".sidebar-header ",
        ".sidebar-header.",
        ".sidebar-header:",
        ".login-header ",
        ".login-header.",
        ".login-header:",
        ".login-logo ",
        ".login-logo.",
        ".login-logo:",
        ".student-header ",
        ".student-header.",
        ".student-header:",
    )
    for line, selector, body in _iter_css_rules(text):
        if selector.strip().startswith("@media"):
            continue
        for item in _selector_items(selector):
            if not item.startswith(allowed_prefixes):
                issues.append(
                    Issue(
                        "static/css/siab1-branding.css",
                        line,
                        f"selector {item!r} is outside allowed branding scopes",
                    )
                )
        if re.search(r"\b(?:background|background-color|border|box-shadow)\s*:", body):
            issues.append(
                Issue(
                    "static/css/siab1-branding.css",
                    line,
                    "branding CSS must not alter backgrounds, borders, or shadows",
                )
            )
    return issues


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

            if any(item == ".card" for item in selectors) and re.search(
                r"background(?:-color)?\s*:\s*(?:white|#fff|#ffffff|var\(--siab1-surface\))[^;]*!important",
                body,
                flags=re.I,
            ):
                issues.append(
                    Issue(label, line, "global .card forced white surface is not allowed; classify cards semantically")
                )

            if any(item in {"span", "p", "label", "strong"} for item in selectors) and re.search(
                r"\bcolor\s*:[^;]+!important", body
            ):
                issues.append(
                    Issue(label, line, "global text color !important selector is not allowed")
                )


            if "!important" in body and _contains_color_property(body):
                risky_global = any(item in {"*", ".card", ".modal"} for item in selectors)
                if risky_global:
                    issues.append(
                        Issue(label, line, "global important color/surface override is not allowed")
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

    light_bg_light_text = re.compile(
        r"style=[\"'][^\"']*background\s*:\s*(?:#fff|#ffffff|white|#f8fafc|#fffbeb)[^\"']*color\s*:\s*(?:white|#fff|#ffffff|#fcd34d|#fca5a5)",
        re.I,
    )
    dark_bg_dark_text = re.compile(
        r"style=[\"'][^\"']*background\s*:\s*(?:var\(--dark\)|#0f172a|#081a2f)[^\"']*color\s*:\s*(?:var\(--siab1-text\)|#0f172a|#111827)",
        re.I,
    )
    for pattern, message in (
        (light_bg_light_text, "light background with light text in settings"),
        (dark_bg_dark_text, "dark background with dark text in settings"),
    ):
        for match in pattern.finditer(text):
            issues.append(Issue("templates/admin/settings.html", _line_number(text, match.start()), message))

    if "settings-backup-progress-bar" not in text or "class=\"fill\"" not in text:
        issues.append(
            Issue(
                "templates/admin/settings.html",
                1,
                "settings backup progress must have a scoped track and distinct fill element",
            )
        )
    return issues


def check_duplicate_ids(root: Path = REPO_ROOT) -> list[Issue]:
    issues: list[Issue] = []
    for file_path in sorted((root / "templates").rglob("*.html")):
        rel = file_path.relative_to(root).as_posix()
        parser = _parse_html(file_path)
        by_id: dict[str, list[int]] = defaultdict(list)
        for line, element_id in parser.ids:
            by_id[element_id].append(line)
        allowed = ALLOWED_DUPLICATE_IDS.get(rel, set())
        for element_id, lines in by_id.items():
            if len(lines) <= 1 or element_id in allowed:
                continue
            issues.append(Issue(rel, lines[1], f"duplicate DOM id {element_id!r} within template"))
    return issues


def _git_available(root: Path) -> bool:
    return (root / ".git").exists()


def _git_show(root: Path, spec: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "show", spec],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
    except Exception:
        return None
    return result.stdout


def _changed_files(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{BASE_COMMIT}...HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
    except Exception:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _count_preserved_patterns(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    labels = ("id", "event", "name", "button_type", "endpoint")
    for label, pattern in zip(labels, PRESERVED_DIFF_PATTERNS):
        counts[label] = len(pattern.findall(text))
    return counts


def check_inline_contract_preservation(root: Path = REPO_ROOT) -> list[Issue]:
    if not _git_available(root):
        return []
    issues: list[Issue] = []
    for rel in _changed_files(root):
        if not rel.startswith("templates/") or not rel.endswith(".html"):
            continue
        current_path = root / rel
        if not current_path.exists():
            continue
        before = _git_show(root, f"{BASE_COMMIT}:{rel}")
        if before is None:
            continue
        after = current_path.read_text(encoding="utf-8", errors="ignore")
        before_counts = _count_preserved_patterns(before)
        after_counts = _count_preserved_patterns(after)
        for label, before_count in before_counts.items():
            after_count = after_counts[label]
            if after_count < before_count:
                issues.append(
                    Issue(
                        rel,
                        1,
                        f"UI diff appears to remove {label} contract tokens ({before_count} -> {after_count})",
                    )
                )
    return issues


def run_checks(root: Path = REPO_ROOT) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(check_legacy_branding(root))
    issues.extend(check_admin_card_surfaces(root))
    issues.extend(check_theme_includes(root))
    issues.extend(check_static_cache_versions(root))
    issues.extend(check_branding_css_scope(root))
    issues.extend(check_css_selectors(root))
    issues.extend(check_settings_inline_contrast(root))
    issues.extend(check_duplicate_ids(root))
    issues.extend(check_inline_contract_preservation(root))
    return sorted(issues, key=lambda issue: (issue.path, issue.line, issue.message))


def _format_inventory(root: Path = REPO_ROOT) -> list[str]:
    inventory, _issues = admin_card_inventory(root)
    lines = ["Admin card inventory:"]
    lines.append("Template | Total | Light | Dark | Brand | Warning | Unclassified")
    for rel, item in sorted(inventory.items()):
        lines.append(
            f"{rel} | {item.total_card} | {item.light_surface} | {item.dark_surface} | "
            f"{item.brand_surface} | {item.warning_surface} | {item.unclassified}"
        )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    show_inventory = "--inventory" in argv
    issues = run_checks()
    if show_inventory:
        for line in _format_inventory():
            print(line)
    if issues:
        print("SIAB1 UI regression check failed:")
        for issue in issues:
            print(f"  - {issue.format()}")
        return 1
    print("SIAB1 UI regression check passed: legacy UI theme, SIAB1 branding, cache-busting, and scoped CSS guardrails are clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
