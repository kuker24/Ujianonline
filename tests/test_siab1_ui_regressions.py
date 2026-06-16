from pathlib import Path

from scripts.check_siab1_ui_regressions import (
    RELEASE_TOKEN,
    admin_card_inventory,
    check_admin_card_surfaces,
    check_css_selectors,
    check_duplicate_ids,
    check_legacy_branding,
    check_static_cache_versions,
    check_theme_includes,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _template_with_head(extra_head: str = "", body: str = "") -> str:
    return f"""
<!doctype html>
<html>
<head>
    <link rel="stylesheet" href="/static/css/admin.css">
    {extra_head}
    <link rel="stylesheet" href="/static/css/siab1-theme.css?v=test">
</head>
<body>{body}</body>
</html>
"""


def test_branding_check_ignores_technical_identifier(tmp_path):
    _write(tmp_path / "app/config.py", 'DATABASE_NAME = "ujian_online"\napp_name = "SIAB1"\n')

    assert check_legacy_branding(tmp_path) == []


def test_branding_check_flags_runtime_legacy_brand(tmp_path):
    legacy_brand = "Ujian " + "Online"
    _write(tmp_path / "templates/admin/index.html", f"<h1>{legacy_brand}</h1>\n")

    issues = check_legacy_branding(tmp_path)

    assert len(issues) == 1
    assert "legacy runtime branding" in issues[0].message


def test_admin_card_without_semantic_class_is_detected(tmp_path):
    _write(
        tmp_path / "templates/admin/users.html",
        _template_with_head(body='<div class="card" id="filters"></div>'),
    )

    issues = check_admin_card_surfaces(tmp_path)

    assert len(issues) == 1
    assert "semantic surface" in issues[0].message


def test_admin_card_with_siab1_surface_passes(tmp_path):
    _write(
        tmp_path / "templates/admin/users.html",
        _template_with_head(body='<div class="card siab1-surface"></div>'),
    )

    assert check_admin_card_surfaces(tmp_path) == []


def test_admin_dark_surface_card_passes(tmp_path):
    _write(
        tmp_path / "templates/admin/monitoring.html",
        _template_with_head(body='<div class="card siab1-dark-surface"></div>'),
    )

    assert check_admin_card_surfaces(tmp_path) == []


def test_admin_card_allowlist_is_specific(tmp_path):
    _write(
        tmp_path / "templates/admin/users.html",
        _template_with_head(body='<div class="card" id="legacy-component"></div>'),
    )

    inventory, issues = admin_card_inventory(
        tmp_path,
        allowlist={"templates/admin/users.html": {"legacy-component"}},
    )

    assert issues == []
    assert inventory["templates/admin/users.html"].total_card == 1


def test_duplicate_id_detected_within_template(tmp_path):
    _write(
        tmp_path / "templates/admin/users.html",
        _template_with_head(body='<input id="same"><div id="same"></div>'),
    )

    issues = check_duplicate_ids(tmp_path)

    assert len(issues) == 1
    assert "duplicate DOM id" in issues[0].message


def test_missing_theme_is_detected(tmp_path):
    _write(
        tmp_path / "templates/admin/users.html",
        "<html><head><link rel='stylesheet' href='/static/css/admin.css'></head><body></body></html>",
    )

    issues = check_theme_includes(tmp_path)

    assert len(issues) == 1
    assert "exactly once" in issues[0].message


def test_duplicate_theme_is_detected(tmp_path):
    _write(
        tmp_path / "templates/admin/users.html",
        _template_with_head(extra_head='<link rel="stylesheet" href="/static/css/siab1-theme.css?v=again">'),
    )

    issues = check_theme_includes(tmp_path)

    assert len(issues) == 1
    assert "exactly once" in issues[0].message


def test_theme_loaded_before_local_css_is_detected(tmp_path):
    _write(
        tmp_path / "templates/admin/users.html",
        """
<html><head>
<link rel="stylesheet" href="/static/css/siab1-theme.css?v=test">
<link rel="stylesheet" href="/static/css/admin.css">
</head><body></body></html>
""",
    )

    issues = check_theme_includes(tmp_path)

    assert len(issues) == 1
    assert "must load after" in issues[0].message


def test_css_check_flags_unscoped_progress_and_bare_heading(tmp_path):
    _write(
        tmp_path / "static/css/siab1-theme.css",
        ".progress-bar { background: red; }\nh1 { color: white; }\n",
    )

    messages = [issue.message for issue in check_css_selectors(tmp_path)]

    assert any("unscoped .progress-bar" in message for message in messages)
    assert any("bare heading color override" in message for message in messages)


def test_scoped_progress_selector_passes(tmp_path):
    _write(
        tmp_path / "static/css/siab1-theme.css",
        ".exam-header > .progress-bar { background: red; }\n",
    )

    assert check_css_selectors(tmp_path) == []


def test_global_card_white_override_is_detected(tmp_path):
    _write(
        tmp_path / "static/css/siab1-theme.css",
        ".card { background: white !important; }\n",
    )

    issues = check_css_selectors(tmp_path)

    assert any("global .card forced white" in issue.message for issue in issues)


def test_dark_autofill_override_on_light_surface_is_detected(tmp_path):
    _write(
        tmp_path / "static/css/admin.css",
        "input:-webkit-autofill { -webkit-box-shadow: 0 0 0 30px rgba(15, 23, 42, 0.9) inset !important; caret-color: white; }",
    )

    issues = check_css_selectors(tmp_path)

    assert any("dark autofill" in issue.message for issue in issues)


def test_settings_inline_contrast_flags_white_heading(tmp_path):
    from scripts.check_siab1_ui_regressions import check_settings_inline_contrast

    _write(
        tmp_path / "templates/admin/settings.html",
        '<div class="card siab1-surface"><h3 style="color: white;">Pengaturan Umum</h3></div>',
    )

    issues = check_settings_inline_contrast(tmp_path)

    assert any("inline white" in issue.message for issue in issues)


def _write_valid_cache_guard_files(root: Path) -> None:
    _write(
        root / "templates/admin/users.html",
        f"""
<html><head>
<link rel="stylesheet" href="/static/css/admin.css?v={RELEASE_TOKEN}">
<link rel="stylesheet" href="/static/css/siab1-theme.css?v={RELEASE_TOKEN}">
</head><body>
<script src="/static/js/api.js?v={RELEASE_TOKEN}"></script>
<script src="/static/js/auth.js?v={RELEASE_TOKEN}"></script>
<script src="/static/js/sidebar-loader.js?v={RELEASE_TOKEN}"></script>
</body></html>
""",
    )
    _write(
        root / "templates/student/exam.html",
        f"""
<html><head>
<link rel="stylesheet" href="/static/css/student.css?v={RELEASE_TOKEN}">
<link rel="stylesheet" href="/static/css/exam.css?v={RELEASE_TOKEN}">
<link rel="stylesheet" href="/static/css/siab1-theme.css?v={RELEASE_TOKEN}">
</head><body>
<script src="/static/js/exam-system.js?v={RELEASE_TOKEN}"></script>
</body></html>
""",
    )
    sidebar_source = f"const componentVersion = '{RELEASE_TOKEN}';\n"
    _write(root / "static/js/sidebar-loader/modules/00-sidebar-loader-core.js", sidebar_source)
    _write(root / "static/js/sidebar-loader.js", sidebar_source)
    _write(
        root / "static/sw.js",
        f"""
const CACHE_NAME = 'siab1-v{RELEASE_TOKEN}';
const CACHE_ASSETS = [
    '/static/css/student.css?v={RELEASE_TOKEN}',
    '/static/css/exam.css?v={RELEASE_TOKEN}',
    '/static/js/auth.js?v={RELEASE_TOKEN}',
    '/static/js/api.js?v={RELEASE_TOKEN}',
    '/static/js/exam-system.js?v={RELEASE_TOKEN}'
];
""",
    )
    _write(
        root / "docker/nginx.production.conf",
        """
location = /static/sw.js {
    expires -1;
    add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
}
location /static/ {
    expires 30d;
}
""",
    )


def test_static_cache_versions_pass_with_release_token(tmp_path):
    _write_valid_cache_guard_files(tmp_path)

    assert check_static_cache_versions(tmp_path) == []


def test_static_cache_versions_flags_unversioned_controlled_assets(tmp_path):
    _write_valid_cache_guard_files(tmp_path)
    _write(
        tmp_path / "templates/admin/users.html",
        f"""
<html><head>
<link rel="stylesheet" href="/static/css/admin.css">
<link rel="stylesheet" href="/static/css/siab1-theme.css?v={RELEASE_TOKEN}">
</head><body></body></html>
""",
    )

    issues = check_static_cache_versions(tmp_path)

    assert any("/static/css/admin.css must use release token" in issue.message for issue in issues)


def test_static_cache_versions_flags_sidebar_and_service_worker_stale_tokens(tmp_path):
    _write_valid_cache_guard_files(tmp_path)
    _write(
        tmp_path / "static/js/sidebar-loader/modules/00-sidebar-loader-core.js",
        "const componentVersion = '20260430-perf1';\n",
    )
    _write(
        tmp_path / "static/sw.js",
        "const CACHE_NAME = 'exam-system-v20260430-perf1';\n"
        "const CACHE_ASSETS = ['/static/css/exam.css?v=20260418-richtext1'];\n",
    )

    messages = [issue.message for issue in check_static_cache_versions(tmp_path)]

    assert any("sidebar componentVersion" in message for message in messages)
    assert any("service worker CACHE_NAME" in message for message in messages)
    assert any("stale cache token" in message for message in messages)


def test_static_cache_versions_requires_sw_no_cache_location_before_static(tmp_path):
    _write_valid_cache_guard_files(tmp_path)
    _write(
        tmp_path / "docker/nginx.production.conf",
        """
location /static/ {
    expires 30d;
}
location = /static/sw.js {
    add_header Cache-Control "public, immutable";
}
""",
    )

    messages = [issue.message for issue in check_static_cache_versions(tmp_path)]

    assert any("must appear before /static/" in message for message in messages)
    assert any("no-store/no-cache" in message for message in messages)
