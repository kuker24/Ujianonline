# SIAB1 Rebrand Implementation Status

Date: 2026-06-16

## Canonical identity

- Short name: **SIAB1**
- Full name: **SIAB1 — Sistem Informasi Asesmen Berintegritas**

## Repository audit

The old visible brand appears across backend defaults, Jinja templates, browser metadata, JavaScript, locale data, generated PDF text, Flutter pages and configuration, Android application metadata, APK Builder GUI defaults, shell tooling, and documentation.

## Implemented in the review branch

- Flutter `AppConfig.appName` now uses the full SIAB1 identity.
- Backend `SystemSettings.app_name` default and fallback now use the full SIAB1 identity.
- APK Builder JSON defaults now use the full SIAB1 identity.
- `tools/apk_builder_gui_siab1.py` provides a SIAB1-branded launcher without rewriting the proven builder engine.
- `tools/siab1_rebrand.py` performs repository-wide visible-brand replacement, validation, Python compilation checks, and audit-report generation from a local checkout.

## Compatibility boundary

The migration deliberately preserves technical identifiers whose renaming could break deployments or installed clients: repository name `Ujianonline`, package/application IDs, server URLs, database and service identifiers such as `ujian_online`, migration keys, and deployment paths.

## Local commands

```bash
python3 tools/siab1_rebrand.py --dry-run --json
python3 tools/siab1_rebrand.py --json
python3 tools/apk_builder_gui_siab1.py
```

The GUI launcher uses the existing APK Builder implementation. A release APK still requires a local checkout with Flutter, Android SDK, JDK, Gradle dependencies, and signing material configured.
