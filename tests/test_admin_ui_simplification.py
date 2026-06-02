from pathlib import Path


VIOLATIONS_TEMPLATE = Path("templates/admin/violations.html")
MONITORING_TEMPLATE = Path("templates/admin/monitoring.html")


def test_violations_dashboard_defaults_to_summary_detail_level() -> None:
    template = VIOLATIONS_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="detail-level"' in template
    assert '<option value="summary" selected>Ringkas / agregat</option>' in template
    assert "{ detailLevel: getSelectedDetailLevel() }" in template


def test_violations_dashboard_explains_summary_mode_instead_of_empty_detail_table() -> None:
    template = VIOLATIONS_TEMPLATE.read_text(encoding="utf-8")
    assert "Mode ringkas aktif: dashboard hanya memuat agregat pelanggaran." in template
    assert "Log detail tidak dimuat otomatis agar admin ringan saat peak." in template
    assert "Detail lengkap" in template


def test_monitoring_page_shows_admin_lite_mode_banner() -> None:
    template = MONITORING_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="admin-lite-mode-banner"' in template
    assert "Mode admin ringkas saat ujian ramai" in template
    assert "Prioritaskan pantauan agregat, sesi aktif, dan final submit siswa" in template
