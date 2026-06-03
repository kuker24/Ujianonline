from pathlib import Path


SHORTCUTS = Path("static/js/api/modules/30-ui-shortcuts.js").read_text(encoding="utf-8")
API_BUNDLE = Path("static/js/api.js").read_text(encoding="utf-8")
SETTINGS_TEMPLATE = Path("templates/admin/settings.html").read_text(encoding="utf-8")
SECURITY_SERVICE = Path("flutter_client_code/lib/services/security_service.dart").read_text(
    encoding="utf-8"
)
APK_BUILDER_CONFIG = Path("tools/apk_builder_gui/apk_builder_config.json").read_text(
    encoding="utf-8"
)


def test_admin_apk_shortcuts_accept_alt_or_meta_modifier() -> None:
    assert "const deepModifier = e.altKey || e.metaKey" in SHORTCUTS
    assert "if (e.ctrlKey && e.shiftKey && deepModifier)" in SHORTCUTS
    assert "Ctrl+Shift+(Alt/Meta)+K" in SHORTCUTS
    assert "Ctrl+Shift+(Alt/Meta)+L" in SHORTCUTS
    assert "Ctrl+Shift+(Alt/Meta)+F" in SHORTCUTS


def test_admin_apk_shortcuts_are_role_gated_and_actionable() -> None:
    assert "Akses ditolak: hanya admin/developer." in SHORTCUTS
    assert "Panel token APK tidak ditemukan, refresh halaman atau cek template." in SHORTCUTS
    assert "Panel Token APK ditampilkan/disembunyikan." in SHORTCUTS
    assert "Menu Pengaturan Umum ditampilkan/disembunyikan." in SHORTCUTS
    assert "findElementWithRetry('settings-general-item')" in SHORTCUTS


def test_settings_page_has_visible_admin_apk_fallback_button() -> None:
    assert 'id="show-advanced-apk-settings"' in SETTINGS_TEMPLATE
    assert "Tampilkan Pengaturan APK Lanjutan" in SETTINGS_TEMPLATE
    assert "window.initAdvancedApkSettingsButton" in SETTINGS_TEMPLATE
    assert 'id="apk-token-section"' in SETTINGS_TEMPLATE
    assert 'id="token-bypass"' in SETTINGS_TEMPLATE
    assert "Ctrl+Shift+Windows+K" in SETTINGS_TEMPLATE


def test_api_bundle_contains_synced_shortcut_changes() -> None:
    assert "const deepModifier = e.altKey || e.metaKey" in API_BUNDLE
    assert "Tampilkan Pengaturan APK Lanjutan" not in API_BUNDLE
    assert "Panel Token APK ditampilkan/disembunyikan." in API_BUNDLE


def test_security_service_contract_matches_exam_page_usage() -> None:
    assert "Future<void> initialize({" in SECURITY_SERVICE
    assert "bool runInitialChecks = true" in SECURITY_SERVICE
    assert "bool startPeriodicChecks = true" in SECURITY_SERVICE
    assert "void startPeriodicChecks()" in SECURITY_SERVICE
    assert "void stopPeriodicChecks()" in SECURITY_SERVICE
    assert "static Future<void> disableClipboard()" in SECURITY_SERVICE
    assert "static Future<KeyboardSecurityResult> checkKeyboardSecurity()" in SECURITY_SERVICE
    assert "static String getJsToDisableAutocomplete()" in SECURITY_SERVICE
    assert "void startAntiCheatMonitoring({" in SECURITY_SERVICE
    assert "void stopAntiCheatMonitoring()" in SECURITY_SERVICE
    assert "class KeyboardSecurityResult" in SECURITY_SERVICE


def test_apk_builder_config_uses_production_https_default() -> None:
    assert '"server_url": "https://man1rokanhulu.cloud/"' in APK_BUILDER_CONFIG
    assert "192.168." not in APK_BUILDER_CONFIG
    assert '"force_https": true' in APK_BUILDER_CONFIG
    assert '"allow_cleartext_traffic": false' in APK_BUILDER_CONFIG
