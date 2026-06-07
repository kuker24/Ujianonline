# Phase 6.2e Post-Final Shadow Refresh Observability Fix

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
head reviewed before work: 70f5ff26e3392952e4fa363ca3ef300e0ae67ee2
message: docs: record phase 6.2d shadow retry result
```

## 2. New commits before work

```text
new commits after 70f5ff26e3392952e4fa363ca3ef300e0ae67ee2: none
```

Reviewed before work:

```text
answer_runtime_buffer.py: no unsafe activation
final_submit_service.py: no Redis source-of-truth dependency
logging/config/main.py: production logging uses WARNING when DEBUG=false
answer_sync_service.py: no queue/hybrid activation
config/env/compose: no production activation changes
DB migration/schema: none
APK/AAB/keystore/.env/backup/dump/CSV/raw token/PII/raw answer artifacts: none
```

## 3. Phase 6.2d result summary

```text
Phase 6.2d shadow retry: PASS
Checker-before mismatch=0: YES
Checker-after mismatch=0: YES
Final submit with shadow observed: YES
Post-final refresh observed: YES, via sanitized Redis meta marker
Post-final refresh log marker visible: NO
Queue/hybrid: NO
Runtime buffer production: NO
Phase 6 production: NO
```

Functional proof from Phase 6.2d:

```text
Redis meta contained refreshed_from_db=true and refreshed_after_final_submit=true.
Post-final consistency checker returned payload_hash_mismatch=0.
```

## 4. Best explanation for missing log marker

The original success marker was emitted only from `answer_runtime_buffer.py` at INFO level:

```text
logger.info("SHADOW_POST_FINAL_REFRESH_OK ...")
```

Production `app/main.py` configures logging with:

```text
logging.basicConfig(level=logging.INFO if settings.debug else logging.WARNING, ...)
```

Because production has `DEBUG=false`, INFO-level logs are not reliably emitted to Docker stdout/stderr. The helper executed and refreshed Redis meta, but the INFO marker was filtered out, so `docker compose logs ... | grep SHADOW_POST_FINAL_REFRESH_OK` returned 0.

## 5. Files changed

```text
app/services/answer_runtime_buffer.py
app/services/final_submit_service.py
tests/test_answer_runtime_buffer_post_final_refresh.py
tests/test_final_submit_shadow_refresh_logging.py
docs/phase-6.2e-post-final-shadow-refresh-observability-fix-20260607.md
```

## 6. Logging/observability implementation

Implemented source-only observability fix:

```text
- final_submit_service now emits a grep-visible WARNING marker when post-final shadow refresh succeeds.
- Marker string is literal: SHADOW_POST_FINAL_REFRESH_OK.
- The success marker is emitted only when refresh_result.status is ok/refreshed.
- Skipped refresh stays DEBUG-only to avoid noisy production logs while shadow is default-OFF.
- Failed refresh emits SHADOW_POST_FINAL_REFRESH_FAILED at WARNING with exception class/reason only.
- The refresh helper now returns refreshed_after_final_submit bool in the structured status.
- Helper-side markers were sanitized to avoid printing session IDs.
```

New success marker shape:

```text
SUBMIT-EXAM | SHADOW_POST_FINAL_REFRESH_OK | status=<ok/refreshed> | answer_count=<n> | refreshed_after_final_submit=<bool>
```

New/controlled failure marker shape:

```text
SUBMIT-EXAM | SHADOW_POST_FINAL_REFRESH_FAILED | reason=<class-or-reason>
SUBMIT-EXAM | SHADOW_POST_FINAL_REFRESH_FAILED | error=<ExceptionClass>
```

Skipped marker remains DEBUG-only:

```text
SUBMIT-EXAM | SHADOW_POST_FINAL_REFRESH_SKIPPED | reason=<disabled/not_selected>
```

## 7. Sanitization guarantee

Visible markers contain only:

```text
status
answer_count
refreshed_after_final_submit
reason or exception class for failure
```

Visible markers do not include:

```text
raw answer text
selected option raw payload
raw answer metadata object
username/full name/email/phone
raw token/session token/access token
raw exception message
session_id/exam_id/user_id
```

The tests explicitly assert that sensitive strings do not appear in captured logs.

## 8. Why production behavior remains unchanged

No production behavior changes were made:

```text
ANSWER_WRITE_MODE default remains direct
ANSWER_QUEUE_ENABLED default remains false
ANSWER_QUEUE_PERCENTAGE default remains 0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED default remains false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE default remains 0
session/exam allowlists remain empty by default
```

Final submit remains PostgreSQL/direct:

```text
PostgreSQL commit still happens first.
Redis shadow refresh remains after-commit best-effort.
Redis failure cannot fail final submit.
Final submit does not read Redis shadow for grading/status.
Redis shadow is not source-of-truth.
```

No DB schema, API contract, APK, env, or compose changes were made.

## 9. Tests run and results

Environment:

```text
SECRET_KEY=test-secret-key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test
```

Results:

```text
python -m compileall app
PASS

pytest tests/test_final_submit_shadow_refresh_logging.py -q
4 passed

pytest tests/test_final_submit_shadow_refresh_best_effort.py -q
4 passed

pytest tests/test_answer_runtime_buffer_post_final_refresh.py -q
4 passed

pytest tests/test_answer_runtime_buffer_shadow.py -q
10 passed

pytest tests/test_answer_runtime_buffer_consistency.py -q
3 passed

pytest tests/test_production_readiness_defaults.py -q
7 passed

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

Result:

```text
FORBIDDEN_ARTIFACT_CHECK=PASS
```

No forbidden artifact was added:

```text
APK/AAB
keystore/JKS/key.properties/local.properties
.env/.env.*
DB dump/backup/sql/sqlite/db
CSV/session artifacts
summary JSON artifacts
raw token/session token/student PII/raw answer content
```

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

This is source-only and default-OFF.

## 12. Rollback

Source rollback:

```text
revert the Phase 6.2e fix commit that changes shadow refresh log markers
revert the Phase 6.2e test commit if desired
```

If deployed later and rollback is needed:

```text
restore previous app/services/answer_runtime_buffer.py and app/services/final_submit_service.py
recreate app-plane only
keep DB/Redis/PgBouncer untouched
keep shadow disabled
```

## 13. Final decision

```text
observability source fix ready: YES
safe for default-OFF deploy plan: YES
Phase 6 production: NO
queue/hybrid: NO
```

Next step:

```text
Create a controlled Phase 6.2e default-OFF deploy plan. After default-OFF deploy passes, run a repeated one-session shadow validation only with separate explicit approval. Do not enable queue/hybrid/runtime-buffer production.
```
