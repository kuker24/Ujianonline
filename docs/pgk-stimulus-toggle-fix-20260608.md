# PGK Stimulus Toggle Fix

Date: 2026-06-08

## 1. Latest GitHub head reviewed

Before this correction, the branch head reviewed was:

```text
bdcd4256a7776656e398b2d84320af45506a9a9b
```

Recent PGK commits reviewed:

```text
ddf0897 docs: record PGK type toggle authoring update
2133243 fix: make PGK type toggles clickable
bdcd425 docs: record PGK type toggle click fix
```

## 2. User-reported bug

The previous implementation made the PGK Tipe A / Tipe B buttons control the active PGK type. This was wrong.

Observed bug:

```text
When a teacher edits PGK Tipe A, chooses Tipe A answer keys, then clicks OFF on Tipe A, the builder switches the question to Tipe B.
```

Expected behavior:

```text
The question must remain Tipe A. Only the stimulus requirement/textarea should turn OFF.
```

## 3. Misinterpretation summary

Previous implementation interpreted the request as:

```text
Turn PGK Tipe A and Tipe B themselves ON/OFF.
```

Correct interpretation:

```text
Turn stimulus ON/OFF for the current PGK type.
```

The PGK type selector remains the only control for actual question type:

```text
checkbox = Tipe A / Multiple Response
table_validation = Tipe B / Tabel Validasi
```

## 4. Root cause

Wrong behavior came from these source patterns:

```text
getEffectivePgkType() switched effective type based on pgk_type_a_enabled / pgk_type_b_enabled.
setPgkTypeEnabled() changed question.pgk_type when Tipe A/B was toggled OFF.
PGK rendering used getEffectivePgkType(), so UI followed the wrong auto-switch.
Validation still required stimulus globally for PGK.
```

## 5. Files changed

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

No APK, final submit, answer runtime, queue/hybrid, Redis runtime buffer, or Phase 6 files were changed.

## 6. Correct behavior

New behavior:

```text
Dropdown selects PGK type.
Stimulus toggle only controls stimulus for the selected type.
Stimulus OFF never changes pgk_type.
Stimulus OFF never clears options/correct_answers/statements/statement_answers.
Stimulus OFF hides/collapses the stimulus textarea.
Stimulus OFF disables only the stimulus-required validation.
Answer/key validation remains active for the selected type.
```

UI label:

```text
Stimulus Tipe A: ON/OFF
Stimulus Tipe B: ON/OFF
```

OFF note:

```text
Stimulus OFF untuk soal ini. Soal tetap Tipe A/Tipe B dan kunci/data jawaban tetap dipakai.
```

## 7. Data fields used

Canonical fields in `question_settings`:

```text
pgk_type_a_stimulus_enabled
pgk_type_b_stimulus_enabled
```

Frontend mirror fields:

```text
question.pgk_type_a_stimulus_enabled
question.pgk_type_b_stimulus_enabled
```

Legacy fields from previous patch:

```text
pgk_type_a_enabled
pgk_type_b_enabled
```

Compatibility behavior:

```text
If the new stimulus-specific flag is missing, the old flag is treated only as a stimulus fallback.
Old flags no longer switch pgk_type.
```

## 8. Backward compatibility

Old questions without stimulus flags:

```text
pgk_type_a_stimulus_enabled defaults true
pgk_type_b_stimulus_enabled defaults true
```

Existing wrong fields from the previous patch:

```text
pgk_type_a_enabled=false does not force table_validation
pgk_type_b_enabled=false does not force checkbox
```

No database migration is required because `question_settings` is JSONB.

## 9. Validation behavior

Frontend publish validation:

```text
Stimulus is required only if getPgkStimulusEnabled(q) is true and there is no image_url.
Tipe A option/correct_answers validation always runs when pgk_type is checkbox.
Tipe B statements/statement_answers validation always runs when pgk_type is table_validation.
```

Backend publish validation in `app/api/exams.py` mirrors the same stimulus flag behavior.

No final-submit or answer-evaluation code was changed.

## 10. Tests run

JavaScript syntax checks:

```text
node --check static/js/exam-builder.js
node --check static/js/exam-builder/modules/00-bootstrap-settings-events.js
node --check static/js/exam-builder/modules/10-question-core-rendering.js
node --check static/js/exam-builder/modules/20-advanced-preview-publish-validate.js
node --check static/js/exam-builder/modules/30-media-modal-publish-time-points.js
```

Python checks:

```text
python -m compileall app
python -m py_compile tests/test_pgk_type_toggle_authoring.py
```

Static test execution without pytest:

```text
PGK_STIMULUS_STATIC_TESTS=PASS
```

Pytest status in this environment:

```text
python -m pytest ... => No module named pytest
```

Git checks:

```text
git diff --check: PASS
FORBIDDEN_ARTIFACT_CHECK=PASS
```

## 11. Manual smoke result

Agent-side manual browser smoke was not executed because an authenticated teacher/admin browser session is required.

Required human smoke:

```text
1. Hard refresh admin builder with Ctrl+F5.
2. Create/edit PGK Tipe A.
3. Select Tipe A answer keys.
4. Turn Stimulus Tipe A OFF.
5. Confirm dropdown remains Tipe A and answer keys/options remain.
6. Publish/check should not fail because stimulus is empty while stimulus OFF.
7. Turn stimulus ON again; textarea returns and stimulus is required if empty.
8. Switch to Tipe B, fill statements/answers, turn Stimulus Tipe B OFF.
9. Confirm dropdown remains Tipe B and statements/answers remain.
10. Reload edit page and confirm state persists.
```

## 12. Deployment action

Deployment performed after safety gate:

```text
deploy=YES
scope=static/admin builder + backend schema/publish validation files that changed
restart=YES, app-plane only
env change=NO
migration=NO
APK touch=NO
answer runtime/final submit/queue/Phase 6 change=NO
DB/Redis/PgBouncer restart=NO
```

VPS backup before deploy:

```text
/root/ujian_online_backups/pgk-stimulus-toggle-fix-20260608T095519Z
```

Post-deploy checks:

```text
local /health=OK
public /health=OK
app-plane containers=healthy
public static bundle marker=OK
container compile for app/api/exams.py and app/schemas/exam.py=OK
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=<unset>
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=<unset>
```

## 13. Forbidden artifact check

Forbidden artifact check passed.

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

## 14. Rollback

Git rollback:

```bash
git revert 71fd99c
```

VPS rollback:

```text
Restore deployed files from the backup directory recorded during deployment.
If backend files are restored, restart app-plane only.
No DB rollback is needed.
```

## 15. Final decision

```text
ready_for_review=YES
corrected_feature=PGK stimulus toggle per selected type
pgk_type_auto_switch_removed=YES
student_answer_runtime_changed=NO
final_submit_changed=NO
queue_hybrid_phase6_changed=NO
apk_touched=NO
```
