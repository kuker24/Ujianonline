# SIAB1 Form Control Visibility Audit — 2026-06-17

Base scope: templates/admin/**, templates/student/**, templates/seb/**, templates/base.html, static/css/**, static/js/**.

## Root cause fixed

- Firefox checkbox/radio invisibility was caused by a global `@-moz-document url-prefix()` rule in `static/css/responsive.css` that set `appearance: none` for every `input`, `textarea`, and `select`.
- Android/Chrome select arrows were at risk because a global WebKit media query removed native select background/appearance for every `select`.
- The Template modal had a broad `.custom-modal-body * { color: white !important; }` override that could force semantic states and native control internals to the wrong color.

## Control inventory by source

| Path | Controls found | Browser risk addressed |
| --- | --- | --- |
| `templates/admin/bulk-users.html` | checkbox: 2, number: 1, select: 2 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved; number input remains native except page-specific styling |
| `templates/admin/exam-analytics.html` | checkbox: 3, select: 3 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved |
| `templates/admin/exam-builder.html` | checkbox: 11, datetime-local: 2, number: 7, select: 4 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved; date/time picker appearance not globally disabled; number input remains native except page-specific styling |
| `templates/admin/exam-templates.html` | checkbox: 1, datetime-local: 3, select: 1 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved; date/time picker appearance not globally disabled |
| `templates/admin/exams.html` | checkbox: 5, datetime-local: 2, number: 2, select: 2, textarea: 1 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved; date/time picker appearance not globally disabled; number input remains native except page-specific styling; textarea not caught by Firefox appearance reset |
| `templates/admin/grading.html` | select: 1 | native select arrow preserved |
| `templates/admin/index.html` | checkbox: 2 | native checkbox/radio appearance preserved; custom controls scoped |
| `templates/admin/media.html` | select: 1 | native select arrow preserved |
| `templates/admin/monitoring.html` | select: 1 | native select arrow preserved |
| `templates/admin/results.html` | checkbox: 1, select: 2 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved |
| `templates/admin/seb-builder.html` | checkbox: 10, select: 1 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved |
| `templates/admin/settings.html` | checkbox: 8, file: 1, radio: 5, select: 1, textarea: 3 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved; file button/filename native appearance preserved; textarea not caught by Firefox appearance reset |
| `templates/admin/users.html` | checkbox: 3, select: 3 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved |
| `templates/admin/violations.html` | date: 4, select: 2 | native select arrow preserved; date/time picker appearance not globally disabled |
| `static/js/admin/monitoring/modules/00-core-ops-and-sessions.js` | date: 1, time: 1 | date/time picker appearance not globally disabled |
| `static/js/admin/monitoring/modules/20-fullscreen-and-cleanup.js` | checkbox: 1 | native checkbox/radio appearance preserved; custom controls scoped |
| `static/js/admin/monitoring.js` | checkbox: 1, date: 1, time: 1 | native checkbox/radio appearance preserved; custom controls scoped; date/time picker appearance not globally disabled |
| `static/js/exam-builder/modules/10-question-core-rendering.js` | checkbox: 6, number: 1, radio: 2, select: 2, textarea: 1 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved; number input remains native except page-specific styling; textarea not caught by Firefox appearance reset |
| `static/js/exam-builder/modules/20-advanced-preview-publish-validate.js` | checkbox: 1, radio: 2 | native checkbox/radio appearance preserved; custom controls scoped |
| `static/js/exam-builder/modules/30-media-modal-publish-time-points.js` | checkbox: 4 | native checkbox/radio appearance preserved; custom controls scoped |
| `static/js/exam-builder.js` | checkbox: 11, number: 1, radio: 4, select: 2, textarea: 1 | native checkbox/radio appearance preserved; custom controls scoped; native select arrow preserved; number input remains native except page-specific styling; textarea not caught by Firefox appearance reset |
| `static/js/exam-scheduling/modules/00-exam-scheduling-core.js` | datetime-local: 2 | date/time picker appearance not globally disabled |
| `static/js/exam-scheduling.js` | datetime-local: 2 | date/time picker appearance not globally disabled |
| `static/js/exam-system/modules/20-exam-qa-submit-navigation.js` | checkbox: 2, radio: 2, textarea: 1 | native checkbox/radio appearance preserved; custom controls scoped; textarea not caught by Firefox appearance reset |
| `static/js/exam-system.js` | checkbox: 2, radio: 2, textarea: 1 | native checkbox/radio appearance preserved; custom controls scoped; textarea not caught by Firefox appearance reset |
| `static/js/exam-templates/modules/00-exam-templates-core.js` | datetime-local: 2, number: 3, textarea: 1 | date/time picker appearance not globally disabled; number input remains native except page-specific styling; textarea not caught by Firefox appearance reset |
| `static/js/exam-templates.js` | datetime-local: 2, number: 3, textarea: 1 | date/time picker appearance not globally disabled; number input remains native except page-specific styling; textarea not caught by Firefox appearance reset |
| `static/js/media-library/modules/10-media-library-class.js` | file: 1, textarea: 1 | file button/filename native appearance preserved; textarea not caught by Firefox appearance reset |
| `static/js/media-library.js` | file: 1, textarea: 1 | file button/filename native appearance preserved; textarea not caught by Firefox appearance reset |
| `static/js/profile-modal/modules/00-sanitize-template-assets.js` | file: 1 | file button/filename native appearance preserved |
| `static/js/profile-modal.js` | file: 1 | file button/filename native appearance preserved |
| `static/js/user-management/modules/00-user-management-core.js` | checkbox: 1 | native checkbox/radio appearance preserved; custom controls scoped |
| `static/js/user-management.js` | checkbox: 1 | native checkbox/radio appearance preserved; custom controls scoped |

## Page coverage summary

- Admin: login, dashboard, users, bulk users, exams, exam templates, exam builder, monitoring, results, analytics, settings, system monitor, account security, media, SEB builder.
- Student: login, dashboard, exam listing/dashboard, exam page answer controls, submit/session modal sources.
- SEB/public: landing and downloads pages.

## CSS controls preserved

- Native checkbox/radio: `appearance: auto`, visible dimensions where page-specific (`.class-checkbox`), keyboard `:focus-visible`, disabled state, and checked row enhancement.
- Existing custom checkbox: `.custom-checkbox` keeps scoped `appearance: none` and `::before` checkmark.
- Toggle switch: `.toggle-switch input:checked` checked selector preserved.
- Select: native arrows stay enabled by default; optional `.custom-select-arrow` is the only class allowed to opt into custom select appearance.
- Modal text scope: `.custom-modal-body` now scopes textual colors and no longer overrides all descendants.

## Regression guards added

- `check_form_control_visibility()` blocks global `appearance:none` on all inputs and native checkbox/radio.
- Blocks Firefox `@-moz-document` global input reset.
- Blocks global WebKit select arrow removal.
- Requires Template class checkbox row/label/dimensions/focus/disabled/checked styling.
- Requires existing `.custom-checkbox` checkmark and toggle checked selector to remain present.

## Non-goals / unchanged contracts

- No backend, API, database, auth, permissions, exam timer, answer save/sync, final submit, anti-cheat, WebSocket, APK validation, Android package, or credential changes.
- No IDs, names, values, event handlers, data attributes, payloads, endpoints, or form submission behavior intentionally changed.
- `siab1-theme.css` remains absent.
