# PGK Type Toggle Authoring Update

Date: 2026-06-08

## 1. Latest GitHub head reviewed

Before implementation, GitHub branch was fetched and reviewed:

```text
branch=review/sanitized-root-20260531-115153
latest_head_before_patch=2759eb7039ff3fa409594f19361f011f9ab5dda7
latest_head_commit=docs: add vps storage audit and cleanup candidates
```

Local-only commits that were not on GitHub were not used.

## 2. Problem summary

Teacher authoring need:

```text
For Pilihan Ganda Kompleks (PGK) questions with stimulus, teachers need small per-question controls to enable/disable Tipe A and Tipe B.
Disabled type sections should not block validation/publish and should not be shown in authoring/preview for that question.
Old PGK behavior must remain compatible.
```

## 3. Files changed

```text
app/api/exams.py
app/schemas/exam.py
static/js/exam-builder.js
static/js/exam-builder/modules/00-bootstrap-settings-events.js
static/js/exam-builder/modules/10-question-core-rendering.js
static/js/exam-builder/modules/20-advanced-preview-publish-validate.js
static/js/exam-builder/modules/30-media-modal-publish-time-points.js
tests/test_pgk_type_toggle_authoring.py
```

No APK/Flutter/keystore/env/DB migration/final-submit/queue/Phase 6 files were changed.

## 4. Data model used

Canonical storage is `question_settings`:

```json
{
  "pgk_type_a_enabled": true,
  "pgk_type_b_enabled": true
}
```

For authoring preservation only, disabled type data is mirrored in `question_settings`:

```json
{
  "pgk_type_a_options": [],
  "pgk_type_a_correct_answers": [],
  "pgk_type_b_statements": [],
  "pgk_type_b_statement_answers": []
}
```

The existing `pgk_type` remains the selected active PGK subtype:

```text
checkbox = Tipe A
 table_validation = Tipe B
```

Root mirrors are kept only for frontend convenience:

```text
q.pgk_type_a_enabled
q.pgk_type_b_enabled
```

## 5. Backward compatibility

Default behavior for old questions:

```text
missing pgk_type_a_enabled => true
missing pgk_type_b_enabled => true
```

Result:

```text
old PGK questions behave as before
existing checkbox PGK remains Tipe A
existing table_validation PGK remains Tipe B
missing flags do not make old questions invalid
```

Duplication behavior:

```text
duplicateQuestion() deep-copies question_settings, so toggle state is preserved.
```

Disabled type data behavior:

```text
Toggling a type OFF does not clear its local authoring data.
Save payload mirrors hidden type data into question_settings so it can be restored when editing later.
```

## 6. UI behavior

In the PGK authoring panel, small pill buttons are shown near the PGK subtype selector:

```text
ON/OFF · Tipe A
ON/OFF · Tipe B
```

Behavior:

```text
Tipe A OFF: checkbox/multiple-response authoring section is hidden/disabled.
Tipe B OFF: table-validation authoring section is hidden/disabled.
If current selected type is turned OFF and the other type is ON, builder auto-switches to the other type.
If both are OFF, a warning panel is shown.
```

Warning text:

```text
Soal PGK harus memiliki minimal satu tipe aktif: Tipe A atau Tipe B.
```

## 7. Validation behavior

Frontend publish validation now reads:

```javascript
const settings = q.question_settings || {};
const typeAEnabled = settings.pgk_type_a_enabled !== false && q.pgk_type_a_enabled !== false;
const typeBEnabled = settings.pgk_type_b_enabled !== false && q.pgk_type_b_enabled !== false;
```

Rules:

```text
Tipe A validation runs only when Tipe A is enabled and selected/effective.
Tipe B validation runs only when Tipe B is enabled and selected/effective.
If both are OFF, publish is blocked.
Stimulus validation for PGK remains in place.
```

Error examples:

```text
Soal No. X (PGK Tipe A): Minimal harus ada ... opsi jawaban
Soal No. X (PGK Tipe A): Minimal 2 kunci jawaban harus dicentang
Soal No. X (PGK Tipe B): Minimal harus ada 2 pernyataan
Soal No. X (PGK Tipe B): Jawaban Benar/Salah belum lengkap
Soal No. X (PGK): Soal PGK harus memiliki minimal satu tipe aktif: Tipe A atau Tipe B.
```

Backend publish validation in `app/api/exams.py` also respects the same flags.

## 8. Preview / student impact

Admin preview:

```text
Uses the effective PGK type and hides disabled current type section.
Both-OFF shows no active type and publish validation blocks.
```

Student display:

```text
No broad student runtime rewrite was performed.
No final submit/evaluation/answer runtime changes were made.
Published questions still use existing pgk_type rendering/evaluation.
Because both-OFF is blocked at publish and effective type is saved, disabled stale authoring data is not used for student runtime.
```

## 9. Tests and checks run

JavaScript syntax checks:

```text
node --check static/js/exam-builder.js
node --check static/js/exam-builder/modules/10-question-core-rendering.js
node --check static/js/exam-builder/modules/20-advanced-preview-publish-validate.js
node --check static/js/exam-builder/modules/30-media-modal-publish-time-points.js
node --check static/js/api.js
node --check static/js/auth.js
```

Backend compile:

```text
python -m compileall app
```

Static assertions:

```text
PGK_STATIC_ASSERTIONS=PASS
python -m py_compile tests/test_pgk_type_toggle_authoring.py
TEST_FILE_PY_COMPILE=PASS
```

Pytest status:

```text
pytest command: not installed in local worktree environment
python -m pytest: No module named pytest
```

Bundle sync:

```text
scripts/build_exam_builder_bundle.sh executed successfully
static/js/exam-builder.js rebuilt from modules
```

Git checks:

```text
git diff --check: PASS
FORBIDDEN_ARTIFACT_CHECK=PASS
```

## 10. Forbidden artifact check

Forbidden artifact grep passed.

No committed artifacts:

```text
no APK/AAB
no keystore/JKS/key.properties/local.properties
no .env/.env.*
no DB dump/backup/sql/sqlite/db
no CSV/session artifact
no raw summary JSON artifact
no token/PII/raw answer artifact
```

## 11. Deployment action

Deployment decision:

```text
deploy=YES
restart=YES, app-plane only
env change=NO
migration=NO
APK touch=NO
DB/Redis/PgBouncer restart=NO
queue/hybrid/Phase 6 change=NO
```

Safety gate before deploy:

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

VPS backup created before extract:

```text
/root/ujian_online_backups/pgk-type-toggle-authoring-20260608T092604Z
```

Deployed files:

```text
app/api/exams.py
app/schemas/exam.py
static/js/exam-builder.js
static/js/exam-builder/modules/00-bootstrap-settings-events.js
static/js/exam-builder/modules/10-question-core-rendering.js
static/js/exam-builder/modules/20-advanced-preview-publish-validate.js
static/js/exam-builder/modules/30-media-modal-publish-time-points.js
tests/test_pgk_type_toggle_authoring.py
```

Restarted services only:

```text
api
api2
api3
api4
api5
api6
api7
api8
api_admin
api_admin2
```

Not restarted:

```text
db
redis
pgbouncer
nginx
celery_worker
celery_beat
host
```

Post-deploy checks:

```text
local /health=OK
public /health=OK
app-plane containers=healthy
runtime env still direct safe-mode / queue OFF / shadow OFF
static/js/exam-builder.js marker OK
app/api/exams.py marker OK
app/schemas/exam.py marker OK
container compile for app/api/exams.py and app/schemas/exam.py OK
public static bundle marker OK
```

## 12. Commits

Feature/test commit:

```text
f63572ad9a8fb14ebb6500bf2af4b3da5ec1eeb8 feat: add PGK type toggles in exam builder
```

This report commit will follow as docs-only.

## 13. Rollback

Source rollback:

```bash
git revert f63572ad9a8fb14ebb6500bf2af4b3da5ec1eeb8
```

VPS rollback option:

```text
restore changed files from /root/ujian_online_backups/pgk-type-toggle-authoring-20260608T092604Z
restart app-plane only if backend files are restored
```

Data rollback impact:

```text
Existing questions with pgk_type_a_enabled/pgk_type_b_enabled fields remain harmless JSON fields.
Old code ignores unknown question_settings fields.
No DB migration rollback required.
```

## 14. Final decision

```text
ready_for_review=YES
safe_for_admin_authoring_deployment=YES
student_answer_runtime_changed=NO
final_submit_changed=NO
queue_hybrid_phase6_changed=NO
apk_touched=NO
```

Next recommendation:

```text
Have a teacher/admin open one PGK stimulus question in the builder and manually smoke:
1. toggle Tipe A OFF, verify Tipe B stays visible/validates;
2. toggle Tipe B OFF, verify Tipe A stays visible/validates;
3. turn both OFF, verify publish warning;
4. turn type back ON, verify old data returns.
```
