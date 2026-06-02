from pathlib import Path


ROOT = Path("flutter_client_code/android/app/src")


def test_release_manifest_disables_cleartext_traffic() -> None:
    manifest = (ROOT / "main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert 'android:usesCleartextTraffic="false"' in manifest
    assert 'android:usesCleartextTraffic="true"' not in manifest
    assert 'android:networkSecurityConfig="@xml/network_security_config"' in manifest


def test_release_network_security_config_disables_cleartext_and_user_ca() -> None:
    config = (ROOT / "main/res/xml/network_security_config.xml").read_text(encoding="utf-8")
    assert 'cleartextTrafficPermitted="false"' in config
    assert 'cleartextTrafficPermitted="true"' not in config
    assert '<certificates src="system" />' in config
    assert '<certificates src="user" />' not in config


def test_debug_and_profile_can_override_cleartext_for_local_testing() -> None:
    for build_type in ("debug", "profile"):
        manifest = (ROOT / f"{build_type}/AndroidManifest.xml").read_text(encoding="utf-8")
        config = (ROOT / f"{build_type}/res/xml/network_security_config.xml").read_text(
            encoding="utf-8"
        )
        assert 'android:usesCleartextTraffic="true"' in manifest
        assert 'tools:replace="android:usesCleartextTraffic,android:networkSecurityConfig"' in manifest
        assert 'cleartextTrafficPermitted="true"' in config
        assert '<certificates src="user" />' in config


def test_api_service_forces_https_when_config_enabled() -> None:
    source = Path("flutter_client_code/lib/services/api_service.dart").read_text(encoding="utf-8")
    assert "if (AppConfig.forceHttps && value.startsWith('http://'))" in source
    assert "value.replaceFirst('http://', 'https://')" in source
