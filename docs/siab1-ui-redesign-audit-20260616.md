# SIAB1 UI Redesign Audit and Review Remediation

Date: 2026-06-16
Branch/worktree: `review/siab1-ui-redesign` at `/tmp/ujianonline-siab1-ui-work`
Base reviewed against: `67fca39f4b3ec9509381f68917caaa4477d19ca9`

## Scope and hard boundary

Goal: complete the SIAB1 visual redesign and remediate review findings without changing runtime behavior.

Official brand:

```text
SIAB1
SIAB1 — Sistem Informasi Asesmen Berintegritas
```

Confirmed out of scope / not changed:

```text
Exam logic, timer, start/save/sync/final-submit flow
Authentication/login flow and authorization/permission logic
WebSocket behavior
Anti-cheat, kiosk/security, APK token validation, APK signature validation
Routes, endpoint URLs, API payload contracts
Database schema and migrations
Android package name
VPS deployment or merge to a base branch
```

## Review findings remediation

### A. Runtime branding fallbacks

Fixed visible/default runtime branding in:

```text
app/config.py
app/models/system_settings.py
app/locales/id.json
app/main.py
app/utils/telegram_alerts.py
app/core/pdf_generator.py
templates/**
static visual/sidebar/service-worker files
flutter_client_code visible UI/metadata files
tools/apk_builder_gui defaults/docs
```

Examples:

```text
Default app_name: Ujian Online -> SIAB1
system_settings.app_name default/fallback -> SIAB1
Locale welcome message -> Selamat datang di SIAB1 — Sistem Informasi Asesmen Berintegritas
FastAPI docs description -> SIAB1 — Sistem Informasi Asesmen Berintegritas ...
Telegram test alert title -> Test Alert - SIAB1
PDF visible report subtitles/default certificate institution -> SIAB1 wording
```

Technical identifiers intentionally not renamed:

```text
ujian_online repository/folder/package/service/database-style identifiers
Android package name
Environment variable keys
Database table/column names
```

### B. White text on white/light cards

Remediated settings-page contrast regressions caused by the SIAB1 light card treatment:

```text
templates/admin/settings.html
static/css/siab1-theme.css
```

Changes:

```text
Removed the risky global .card surface override from the SIAB1 theme.
Introduced semantic SIAB1 surface classes: .siab1-surface, .siab1-dark-surface, .siab1-brand-surface, .siab1-warning-surface.
Applied .siab1-surface explicitly to settings cards that are intended to be light.
Changed settings card headings/strong labels from inline white to SIAB1 dark text.
Changed light warning/helper text from pale red/amber/green to readable darker tones.
Changed settings form controls/placeholders to dark text on light inputs.
Changed backup option/upload/progress panels to light readable surfaces.
Kept white text only where the element itself remains a dark/colored control (buttons, badges, icon blocks, dark preview panel).
```

Static audit focus included:

```text
Pengaturan Umum
Pengaturan APK Lanjutan / APK Token
Backup Data and backup type cards
Restore Backup / Preview Data
Telegram Broadcast preview
Pembersihan
Warmup/progress/status panels
Developer, Android APK, maintenance, and freeze panels
```

### C. Scoped progress bar styling

Removed the risky global SIAB1 theme selectors:

```css
.progress-bar { ... }
.progress-fill { ... }
```

Replaced with scoped selectors/classes:

```text
static/css/siab1-theme.css: .exam-header > .exam-progress-bar / .exam-header .exam-progress-fill
static/css/exam.css: scoped to .exam-header
static/css/student.css: scoped to .exam-progress

templates/student/exam.html: exam-progress-bar / exam-progress-fill
templates/admin/settings.html: settings-backup-progress-bar
templates/admin/analytics.html: analytics-progress-bar / analytics-progress-fill
templates/admin/system-monitor.html: system-progress-bar / system-progress-fill
```

This keeps exam progress styling isolated from admin analytics, backup, and system monitor progress bars.

### D. Line-ending and noisy diff cleanup

Cleaned the review-noisy files against base `67fca39f4b3ec9509381f68917caaa4477d19ca9` so substantive diffs are small and reviewable:

```text
flutter_client_code/android/app/proguard-rules.pro
flutter_client_code/android_src/AndroidManifest.xml
flutter_client_code/lib/main.dart
flutter_client_code/lib/pages/config_page.dart
flutter_client_code/lib/pages/splash_page.dart
flutter_client_code/lib/widgets/common_widgets.dart
templates/seb/downloads.html
tools/apk_builder_gui/README.md
```

Added `.gitattributes` entries for those legacy CRLF files so `git diff --check` does not misclassify preserved carriage returns / inherited final blank lines as new whitespace errors. This is scoped only to the listed legacy files.

## Runtime branding normalization

Added opt-in maintenance script:

```text
scripts/normalize_siab1_branding.py
```

Purpose:

```text
Normalize existing persisted system_settings.app_name values that exactly match legacy app branding.
```

Exact values eligible for update:

```text
Ujian Online
Sistem Ujian Online
Ujian Online System
Admin Ujian Online
```

Target value:

```text
SIAB1
```

Safety properties:

```text
Not imported by app startup.
Not executed automatically.
Supports --dry-run and --apply.
Prints before/after values per row.
Uses app.config database configuration.
Does not store credentials.
Does not modify custom app_name values.
Idempotent: a second run finds no rows once exact legacy values are normalized.
```

Usage:

```bash
python scripts/normalize_siab1_branding.py --dry-run
python scripts/normalize_siab1_branding.py --apply
```

Local execution note: not run against a database in this worktree because the local Python environment did not have application dependencies (`SQLAlchemy`/`pydantic_settings`) installed. The script now fails with a user-safe error in that case.

## Regression guard added

Added:

```text
scripts/check_siab1_ui_regressions.py
tests/test_siab1_ui_regressions.py
```

The static guard checks:

```text
Runtime UI old branding in configured runtime-visible paths.
Technical identifiers such as ujian_online are not treated as branding failures.
Unscoped .progress-bar/.progress-fill CSS selectors in SIAB1-relevant CSS/style blocks.
Global .card * color overrides.
Bare global heading color overrides.
Settings inline white heading/strong text that can disappear on SIAB1 light cards.
Settings form-control white-text override.
```

## Visual smoke test evidence

Browser screenshots were not produced because no authenticated local web session, seeded accounts, or running full stack was available in this environment.

Static DOM/CSS audit was performed for the required page groups:

```text
Public/auth: admin login, student login
Admin: dashboard, settings, users, exams, monitoring, results, system monitor, account security
Student: dashboard, start-exam modal markup, exam page, question navigator markup, result page, logout modal markup
SEB: landing, downloads
Flutter/APK: splash, native login, loading, config/server failure, exam loading/error/dialog, session ended
```

Viewport-specific browser screenshots/checks at `360x800`, `390x844`, `768x1024`, `1366x768`, and `1920x1080` remain manual follow-up because the authenticated app could not be launched locally here.

Manual smoke checklist for the next authenticated run:

```text
No white text on light SIAB1 cards.
No dark text on navy/dark panels.
Buttons, badges, labels, inputs, placeholders, table headers, alerts, and modals are readable.
Admin tables retain horizontal scrolling on mobile.
Sidebar does not cover content on mobile.
Exam header/timer/progress/navigator remain visible and non-overlapping.
Touch targets remain at least 44px where mobile controls are used.
No unintended horizontal overflow.
Focus ring remains visible on keyboard navigation.
```

## Local validation actually run

```text
git diff --check
Result: PASS (no output)

scripts/verify_frontend_bundles.sh
Result: PASS — Frontend bundle sync check: OK (28 bundles)

node --check static/js/api.js
node --check static/js/auth.js
node --check static/js/exam-system.js
node --check static/js/sidebar-loader.js
node --check static/sw.js
Result: PASS (no output)

python -m compileall app
Result: PASS

python scripts/check_security.py
Result: PASS with non-fatal environment warnings

python scripts/check_siab1_ui_regressions.py
Result: PASS — branding, contrast, and scoped CSS guardrails are clean

python -m py_compile tests/test_apk_builder_gui_config.py tests/test_mobile_first_feature_flags.py tests/test_siab1_ui_regressions.py scripts/check_siab1_ui_regressions.py scripts/normalize_siab1_branding.py
Result: PASS

flutter analyze --no-fatal-infos --no-fatal-warnings
Result: PASS exit 0 with existing non-fatal analyzer findings

flutter test --no-pub test/widget_test.dart
Result: PASS — All tests passed
```

## Tests not run / unavailable

```text
pytest -q tests/test_apk_builder_gui_config.py tests/test_mobile_first_feature_flags.py tests/test_siab1_ui_regressions.py
Result: NOT RUN — pytest command not found in local environment

python scripts/normalize_siab1_branding.py --dry-run
Result: NOT RUN against DB — local app dependencies/database configuration unavailable; script prints a safe dependency error

Authenticated browser visual screenshot run
Result: NOT RUN — no local authenticated sessions/accounts/full stack available
```

## Non-fatal warnings observed

From `python scripts/check_security.py`:

```text
Telnet client binary found at /usr/bin/telnet (low operational hardening warning; not daemon/listening).
pip-audit not installed, vulnerability scan skipped.
10 outdated packages reported, including managed cryptography 48.0.1 -> 49.0.0 and 9 transitive packages.
```

From `flutter analyze --no-fatal-infos --no-fatal-warnings`:

```text
use_build_context_synchronously in lib/pages/config_page.dart
deprecated_member_use for scale in lib/pages/exam_page.dart
unnecessary import package:flutter/foundation.dart in lib/pages/splash_page.dart
unused import ../config.dart in lib/pages/splash_page.dart
unused field _tokenCheckRequired in lib/pages/splash_page.dart
prefer_const_constructors in lib/services/security_service.dart
avoid_relative_lib_imports in test/widget_test.dart
```

These were not fixed because they are pre-existing/non-fatal and outside the visual review-remediation scope.

## CI/GitHub check status

At the time this audit document was updated locally, GitHub PR checks had not run yet. Do not interpret this as CI PASS. Check status must be read from the Pull Request after it is created/pushed.

## Remaining limitations

```text
No screenshots are attached because no authenticated browser/full-stack session was available.
No production/VPS validation was performed, by instruction.
No database normalization was applied; only the opt-in script was added.
Pytest suite could not be run because pytest is not installed in this environment.
GitHub CI status is not claimed as PASS until workflows run on the PR.
Some non-critical legacy dark-card visuals may remain on pages that intentionally keep their old dark card styling; this audit only claims the specific SIAB1 review regressions were remediated and guarded.
```

## Final local status

```text
runtime_branding_defaults_fixed=YES
legacy_database_app_name_handled_by_opt_in_script=YES
settings_white_on_white_fixed=YES
progress_bar_selectors_scoped=YES
line_ending_noise_cleaned=YES
static_regression_guard_added=YES
local_required_checks_passed_except_unavailable_pytest=YES
deployed_to_vps=NO
merged_to_base=NO
backend_exam_logic_changed=NO
api_contract_changed=NO
database_schema_changed=NO
authentication_or_security_logic_changed=NO
apk_aab_keystore_env_database_artifact_added=NO
```
