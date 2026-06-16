from pathlib import Path

from scripts.check_siab1_ui_regressions import (
    admin_card_inventory,
    check_admin_card_surfaces,
    check_css_selectors,
    check_duplicate_ids,
    check_legacy_branding,
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
