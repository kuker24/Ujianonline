from pathlib import Path

from scripts.check_siab1_ui_regressions import (
    check_css_selectors,
    check_legacy_branding,
    check_settings_inline_contrast,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_branding_check_ignores_technical_identifier(tmp_path):
    _write(tmp_path / "app/config.py", 'DATABASE_NAME = "ujian_online"\napp_name = "SIAB1"\n')

    assert check_legacy_branding(tmp_path) == []


def test_branding_check_flags_runtime_legacy_brand(tmp_path):
    legacy_brand = "Ujian " + "Online"
    _write(tmp_path / "templates/admin/index.html", f"<h1>{legacy_brand}</h1>\n")

    issues = check_legacy_branding(tmp_path)

    assert len(issues) == 1
    assert "legacy runtime branding" in issues[0].message


def test_css_check_flags_unscoped_progress_and_bare_heading(tmp_path):
    _write(
        tmp_path / "static/css/siab1-theme.css",
        ".progress-bar { background: red; }\nh1 { color: white; }\n",
    )

    messages = [issue.message for issue in check_css_selectors(tmp_path)]

    assert any("unscoped .progress-bar" in message for message in messages)
    assert any("bare heading color override" in message for message in messages)


def test_settings_inline_contrast_flags_white_heading(tmp_path):
    _write(
        tmp_path / "templates/admin/settings.html",
        '<div class="card"><h3 style="color: white;">Pengaturan Umum</h3></div>',
    )

    issues = check_settings_inline_contrast(tmp_path)

    assert len(issues) == 1
    assert "inline white" in issues[0].message
