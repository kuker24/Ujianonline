# SIAB1 Legacy UI Restore Audit — 2026-06-17

## Objective
Restore the pre-redesign web visual language from commit `67fca39f4b3ec9509381f68917caaa4477d19ca9` while preserving SIAB1 branding and the production cache/deployment fixes.

Target outcome:

- Visual structure/theme: legacy dark/glass UI.
- Visible branding: `SIAB1` and `SIAB1 — Sistem Informasi Asesmen Berintegritas`.
- Cache/deployment behavior: production-safe versioned assets and no-cache service worker.
- Logic: unchanged backend/API/auth/exam/security behavior.

## Root Cause
PR #3 introduced `static/css/siab1-theme.css` as a broad global stylesheet loaded after legacy CSS. That stylesheet redefined legacy surfaces and variables, forced light visual assumptions, disabled legacy decorative background elements, and overrode cards/header/forms/tables/modals.

## Hotfix Strategy

1. Remove global `siab1-theme.css` includes from runtime templates.
2. Delete the broad redesign stylesheet from the hotfix branch so it cannot be reintroduced accidentally.
3. Keep legacy CSS (`admin.css`, `student.css`, `exam.css`, `responsive.css`) as visual source of truth.
4. Add narrow `static/css/siab1-branding.css` for SIAB1 text sizing/spacing only.
5. Restore legacy global modal/autofill styling selectors that were narrowed for the removed theme.
6. Keep SIAB1 text branding across templates, static components, Flutter, Android, PDF/locales/config, and APK Builder.
7. Update cache token to `20260617-siab1-legacy-ui1` in templates, sidebar cache, and service worker.
8. Preserve `/static/sw.js` no-store/no-cache Nginx requirement.

## Files Intentionally Changed

### Visual restore
- `static/css/admin.css`
- `static/css/student.css`
- `static/css/siab1-theme.css` removed
- `templates/admin/**`
- `templates/student/**`
- `templates/seb/**`
- `templates/base.html`

### Branding helper
- `static/css/siab1-branding.css`

Allowed scope only:

- `.sidebar-header .siab1-brand-name`
- `.sidebar-header .siab1-brand-subtitle`
- `.login-header .siab1-brand-name`
- `.login-header .siab1-brand-subtitle`
- `.login-logo .siab1-brand-name`
- `.login-logo .siab1-brand-subtitle`
- `.student-header .siab1-brand-name`
- `.student-header .siab1-brand-subtitle`

The file must not style `body`, `.card`, `.sidebar`, `.main-content`, `.page-header`, tables, modals, forms, buttons, global variables, or light color-scheme.

### Cache-busting
- `static/js/sidebar-loader.js`
- `static/js/sidebar-loader/modules/00-sidebar-loader-core.js`
- `static/sw.js`
- template CSS/JS references

### Regression guards
- `scripts/check_siab1_ui_regressions.py`
- `tests/test_siab1_ui_regressions.py`

## Explicit Non-Goals

This hotfix does not change:

- backend routes or API contracts;
- auth/login/session flow;
- role permissions;
- exam timer/start/save/sync/final submit;
- anti-cheat/kiosk/security behavior;
- WebSocket behavior;
- database schema or migrations;
- database content;
- Android package name;
- APK signing/token/signature logic;
- production VPS files directly.

## Validation Expectations

Before merge/deploy:

- `siab1-theme.css` is not loaded by runtime templates.
- `siab1-branding.css` is scoped to branding text only.
- legacy branding strings are absent from visible runtime sources.
- cache token is consistent: `20260617-siab1-legacy-ui1`.
- `static/sw.js` uses `siab1-v20260617-siab1-legacy-ui1`.
- sidebar loader `componentVersion` uses `20260617-siab1-legacy-ui1`.
- generated bundles are synchronized.
- screenshots are captured from a running app before deployment.
