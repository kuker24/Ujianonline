# Phase 6.2c Post-Final Shadow Refresh Source Fix

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
latest head reviewed before work: 78a557b6cbcb8719fb6fa30dc92e13bcefdf28f5
message: docs: record phase 6.2b shadow retry result
```

## 2. New commits before work

```text
new commits after 78a557b6cbcb8719fb6fa30dc92e13bcefdf28f5: none
```

Reviewed for forbidden/unsafe changes before work:

```text
answer_runtime_buffer.py: no new unsafe activation before work
answer_sync_service.py: no new queue/hybrid activation before work
final_submit_service.py: no Redis source-of-truth before work
config/env/compose: no production queue/hybrid/shadow activation before work
DB migration/schema: none
APK/AAB/keystore/.env/backup/dump/CSV/raw token/PII/raw answer artifacts: none
```

## 3. Root cause summary from Phase 6.2b

Phase 6.2b result:

```text
before final submit: payload_hash_mismatch=0
final submit: HTTP 200/submitted
after final submit: payload_hash_mismatch=2
redis_errors=0
answer save path=OK
shadow hash-only write=OK
queue/hybrid=NO
runtime buffer production=NO
```

Root cause:

```text
Final submit/grading can change committed PostgreSQL answer state after the direct answer-save shadow hash has already been written to Redis. The shadow hash stayed stale, so the post-final consistency checker compared the new DB payload against an old Redis hash.
```

This was distinct from the Phase 6.2a numeric normalization bug.

## 4. Files changed

```text
app/services/answer_runtime_buffer.py
app/services/final_submit_service.py
tests/test_answer_runtime_buffer_post_final_refresh.py
tests/test_final_submit_shadow_refresh_best_effort.py
docs/phase-6.2c-post-final-shadow-refresh-fix-20260607.md
```

## 5. Implementation summary

Added `refresh_runtime_answer_shadow_from_db(...)` in `app/services/answer_runtime_buffer.py`.

Behavior:

```text
- no-op when ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
- no-op when the session/exam is not selected by allowlist/selector
- reads committed PostgreSQL answers for exactly one session
- builds the same canonical payload shape used by answer_payload_hash()
- refreshes only hash-only Redis shadow fields:
  - question_id
  - payload_hash
  - updated_at
- refreshes safe meta fields:
  - session_id
  - exam_id
  - answer_count
  - updated_at
  - refreshed_at
  - refreshed_from_db=true
  - refreshed_after_final_submit=true
- maintains TTL
- catches Redis/DB/helper exceptions and returns sanitized failed status
```

Added final-submit hook in `app/services/final_submit_service.py`:

```text
_finalize_and_commit() commits PostgreSQL first.
_after_submit_best_effort() then calls refresh_runtime_answer_shadow_from_db(...).
Any refresh failure is logged with sanitized marker and does not raise to the student response.
```

New log markers:

```text
SHADOW_POST_FINAL_REFRESH_SKIPPED
SHADOW_POST_FINAL_REFRESH_OK
SHADOW_POST_FINAL_REFRESH_FAILED
```

## 6. Why final submit remains PostgreSQL/direct

Final submit still uses PostgreSQL as source of truth:

```text
- final grading still runs through finalize_exam_session_submission(...)
- answer rows/session score are committed by SQLAlchemy/PostgreSQL
- Redis shadow is not read for grading
- Redis shadow is not read for final submit status
- direct answer mode remains the production default
```

No code sets or requires:

```text
ANSWER_WRITE_MODE=queue
ANSWER_WRITE_MODE=hybrid
ANSWER_QUEUE_ENABLED=true
ANSWER_QUEUE_PERCENTAGE>0
```

## 7. Why Redis shadow remains best-effort/hash-only

Redis shadow refresh stores only deterministic hashes and small safe metadata.

It does not store:

```text
raw answer_text
raw selected option payload
raw answer metadata object
username/full name/email/phone
raw token/session token
```

Redis remains an observability mirror only. It is not source-of-truth and is not used to submit/grade answers.

## 8. Why Redis failure cannot fail final submit

The refresh helper catches exceptions and returns:

```text
{"status": "failed", "reason": "<ExceptionClass>", "answer_count": 0}
```

The final submit service also wraps the call in its own `try/except` block.

Therefore:

```text
PostgreSQL commit is already complete before refresh.
Redis failure after commit only logs SHADOW_POST_FINAL_REFRESH_FAILED.
The final submit response remains successful if DB finalization succeeded.
```

## 9. Tests run and results

Environment used for tests:

```text
SECRET_KEY=test-secret-key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test
```

Commands and results:

```text
python -m compileall app
PASS

pytest tests/test_answer_runtime_buffer_shadow.py -q
10 passed

pytest tests/test_answer_runtime_buffer_consistency.py -q
3 passed

pytest tests/test_answer_runtime_buffer_post_final_refresh.py -q
4 passed

pytest tests/test_final_submit_shadow_refresh_best_effort.py -q
4 passed

pytest tests/test_production_readiness_defaults.py -q
7 passed

pytest tests/test_answer_sync_service_routing.py -q
25 passed

pytest tests/test_final_submit_service.py -q
6 passed

python -m py_compile scripts/runtime_buffer_consistency_check.py
PASS

SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test python scripts/runtime_buffer_consistency_check.py --help
PASS

git diff --check
PASS
```

## 10. Forbidden artifact check

Command pattern:

```text
git status --short | grep -E "(\.apk|\.aab|\.jks|\.keystore|key\.properties|local\.properties|\.env|apk_builds|static/apk|flutter_client_code/build|backup|dump|\.sql|\.sqlite|\.db|sessions.*\.csv|summary.*\.json)"
```

Result:

```text
FORBIDDEN_ARTIFACT_CHECK=PASS
```

No APK/AAB/keystore/env/DB dump/CSV/session artifact/summary JSON/raw token/raw PII/raw answer content was committed.

## 11. Production action

```text
deploy: NO
restart: NO
env change: NO
migration: NO
load-test: NO
APK touch: NO
DB/Redis/PgBouncer restart: NO
```

Production expected defaults remain:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

## 12. Rollback note

Source rollback is straightforward:

```text
revert the fix commit that added refresh_runtime_answer_shadow_from_db and the final-submit best-effort hook
```

Operational rollback for any future default-OFF deploy:

```text
restore previous app/services/answer_runtime_buffer.py and app/services/final_submit_service.py from backup
restart app-plane only if the patch had been deployed
keep DB/Redis/PgBouncer untouched
keep shadow disabled
```

## 13. Final decision

```text
source fix ready for review: YES
safe for default-OFF deploy plan: YES
Phase 6 production: NO
queue/hybrid: NO
```

Next step:

```text
Create a controlled default-OFF deploy plan for Phase 6.2c. After default-OFF deploy passes, request separate explicit approval for another allowlisted synthetic shadow retry. Do not enable production queue/hybrid/runtime-buffer.
```
