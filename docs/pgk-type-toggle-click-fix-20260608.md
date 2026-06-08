# PGK Type Toggle Click Fix

Date: 2026-06-08

## 1. Latest GitHub head reviewed

Before the fix:

```text
branch=review/sanitized-root-20260531-115153
latest_head_before_fix=ddf089732460d5a09433abc57ace100d775a7e90
latest_head_commit=docs: record PGK type toggle authoring update
```

Fix commit:

```text
2133243a8abd69e90586cd8411059e1022ca01ed fix: make PGK type toggles clickable
```

## 2. Root cause

The PGK toggle buttons were rendered correctly with:

```text
data-pgk-type-toggle="A"
data-pgk-type-toggle="B"
```

The click handler existed in `bindPgkTypeToggleEvents()` as a delegated `document.addEventListener('click', ...)` listener.

However, the toggle wrapper in the PGK authoring panel had:

```html
onclick="event.stopPropagation()"
```

Because the delegated listener was attached on `document` in the bubble phase, the wrapper stopped the event before it reached the document handler.

Impact:

```text
Clicking ON/OFF · Tipe A or ON/OFF · Tipe B did not call setPgkTypeEnabled().
The button looked clickable but could not change state.
```

## 3. Files changed

```text
static/js/exam-builder/modules/00-bootstrap-settings-events.js
static/js/exam-builder.js
tests/test_pgk_type_toggle_authoring.py
```

No backend/runtime/final-submit/queue/Phase 6/APK files were changed.

## 4. Fix approach

Minimal fix in `bindPgkTypeToggleEvents()`:

```javascript
document.addEventListener('click', function (event) {
    const button = event.target.closest('[data-pgk-type-toggle]');
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    const index = Number(button.dataset.questionIndex);
    const typeKey = button.dataset.pgkTypeToggle;
    const question = examData.questions?.[index];
    if (!question || question.type !== 'multiple_choice_complex') return;
    const current = typeKey === 'A' ? getPgkTypeAEnabled(question) : getPgkTypeBEnabled(question);
    setPgkTypeEnabled(index, typeKey, !current);
}, true);
```

Key points:

```text
capture=true catches click before parent wrapper stopPropagation
one-time guard window.__pgkTypeToggleEventsBound stays intact
no unrelated stopPropagation was removed
no inline onclick was added to buttons
```

## 5. Expected behavior after fix

```text
New PGK question defaults: Tipe A ON, Tipe B ON
Click Tipe A: toggles OFF/ON and updates question_settings.pgk_type_a_enabled
Click Tipe B: toggles OFF/ON and updates question_settings.pgk_type_b_enabled
Tipe A OFF + Tipe B ON: effective type switches/shows Tipe B
Tipe B OFF + Tipe A ON: effective type switches/shows Tipe A
Both OFF: warning remains and publish validation fails
Old questions with missing flags still default both ON
Autosave still runs via setPgkTypeEnabled()
```

## 6. Tests and checks run

JavaScript syntax checks:

```text
node --check static/js/exam-builder.js
node --check static/js/exam-builder/modules/00-bootstrap-settings-events.js
node --check static/js/exam-builder/modules/10-question-core-rendering.js
node --check static/js/exam-builder/modules/20-advanced-preview-publish-validate.js
node --check static/js/exam-builder/modules/30-media-modal-publish-time-points.js
```

Backend compile check, even though backend was not changed:

```text
python -m compileall app
```

Static regression assertions:

```text
PGK_CLICK_STATIC_ASSERTIONS=PASS
python -m py_compile tests/test_pgk_type_toggle_authoring.py
```

Pytest status in local environment:

```text
python -m pytest ... => No module named pytest
```

Git checks:

```text
git diff --check: PASS
FORBIDDEN_ARTIFACT_CHECK=PASS
```

## 7. Manual smoke result

Automated/source-level confirmation:

```text
module capture marker present: YES
bundle capture marker present: YES
public static bundle capture marker present after deploy: YES
```

Browser manual smoke:

```text
not executed by agent because an authenticated teacher/admin browser session is required
```

Recommended human smoke:

```text
1. Hard refresh admin builder with Ctrl+F5.
2. Add/edit a PGK question.
3. Confirm Tipe A and Tipe B show ON.
4. Click Tipe A; it should become OFF and Tipe B panel should remain usable.
5. Click Tipe B; it should become OFF and both-OFF warning should show.
6. Click Tipe A again; it should become ON and Tipe A panel should return.
7. Save/autosave, reload edit page, confirm state persists.
8. Check browser console: no JS error.
```

## 8. Deployment action

Deployment performed:

```text
deploy=YES
scope=static/admin builder only
restart=NO
env change=NO
migration=NO
APK touch=NO
DB/Redis/PgBouncer restart=NO
Nginx/Celery/host restart=NO
```

Preflight before deploy:

```text
local /health=OK
public /health=OK
active_sessions=0
running_exam_windows=0
long_active_queries_gt60s=0
idle_in_transaction=0
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=<unset>
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=<unset>
EXAM_PEAK_MODE=true
VIOLATION_ASYNC_ENABLED=true
MOBILE_APK_PRIMARY=true
```

Files deployed to VPS:

```text
static/js/exam-builder.js
static/js/exam-builder/modules/00-bootstrap-settings-events.js
```

VPS backup before static extract:

```text
/root/ujian_online_backups/pgk-type-toggle-click-fix-20260608T093514Z
```

Post-deploy checks:

```text
local /health=OK
public /health=OK
public static bundle capture marker=OK
app-plane containers=healthy
```

## 9. Forbidden artifact check

Forbidden artifact check passed.

No committed/deployed artifacts:

```text
no APK/AAB
no keystore/JKS/key.properties/local.properties
no .env/.env.*
no DB dump/backup/sql/sqlite/db
no CSV/session artifact
no raw summary JSON artifact
no token/PII/raw answer artifact
```

## 10. Remaining risk

```text
Browser cache may still serve old static file until hard refresh.
Manual authenticated admin smoke is still required to verify actual click behavior in the UI.
```

Mitigation:

```text
Use Ctrl+F5/hard refresh before testing.
If the button still does not change, verify the loaded static/js/exam-builder.js contains `}, true);` near bindPgkTypeToggleEvents().
```

## 11. Rollback

Git rollback:

```bash
git revert 2133243a8abd69e90586cd8411059e1022ca01ed
```

VPS rollback:

```text
Restore static files from:
/root/ujian_online_backups/pgk-type-toggle-click-fix-20260608T093514Z
```

No DB rollback is needed.
