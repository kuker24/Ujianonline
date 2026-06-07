# Phase 6.2 Allowlisted Shadow Trial Result

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
base reviewed before trial: 2974b268c9bfafc929321ca946173d116f57a304
message: docs: update phase 6.2 shadow trial readiness check
new commits before trial: none
```

Source/activation review before trial:

```text
unexpected queue/hybrid activation: none
unexpected runtime-buffer production activation: none
unexpected final submit Redis dependency: none
unexpected migration/schema change: none
forbidden artifact check: PASS
```

Note:

```text
A grep marker for ANSWER_WRITE_MODE=queue/hybrid exists only in a production guard comment in app/tasks/answer_processor.py.
It is not an activation marker.
```

## 2. Operator approval

Approval received:

```text
Approve Phase 6.0 shadow trial for test exam only
```

Treated as operator intent equivalent to the required approval for test-only Phase 6 shadow trial.

Scope constraints maintained:

```text
queue/hybrid: OFF
ANSWER_WRITE_MODE: direct
ANSWER_QUEUE_ENABLED: false
ANSWER_QUEUE_PERCENTAGE: 0
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE: 0
Redis source-of-truth: NO
final submit Redis dependency: NO
production load-test: NO
APK touched: NO
DB migration/schema change: NO
DB/Redis/PgBouncer restart: NO
```

## 3. Source verification before trial

Commands run:

```bash
python -m compileall app
pytest tests/test_answer_runtime_buffer_shadow.py -q
pytest tests/test_answer_runtime_buffer_consistency.py -q
pytest tests/test_production_readiness_defaults.py -q
pytest tests/test_answer_sync_service_routing.py -q
python -m py_compile scripts/runtime_buffer_consistency_check.py
SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test python scripts/runtime_buffer_consistency_check.py --help
git diff --check
```

Results:

```text
compileall app: PASS
tests/test_answer_runtime_buffer_shadow.py: 9 passed
tests/test_answer_runtime_buffer_consistency.py: 3 passed
tests/test_production_readiness_defaults.py: 7 passed
tests/test_answer_sync_service_routing.py: 25 passed
runtime_buffer_consistency_check.py py_compile: PASS
runtime_buffer_consistency_check.py --help: PASS
git diff --check: PASS
forbidden artifact check: PASS
```

## 4. Pre-enable gates

Initial preflight timestamp:

```text
20260607T045532Z
```

Preflight before actual answer-writing attempt:

```text
local /health=200
public /health=200
all containers=healthy
DB=healthy
PgBouncer=healthy
Redis=PONG
```

DB gates:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Redis gates before first trial attempt:

```text
rejected_connections=0
evicted_keys=0
runtime_shadow_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

After one failed checker-path attempt, known old shadow keys existed only for synthetic Phase 6 sessions:

```text
runtime_shadow_keys=3
PRE_EXISTING_SHADOW_KEYS_TEST_ONLY=PASS count=3 sessions=1
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

This complied with the rule allowing pre-existing known old test keys.

## 5. Test scope

Synthetic test scope was created with prefix:

```text
__PHASE6_SHADOW_TEST__
```

Sanitized test identifiers from final meaningful attempt:

```text
test user: ***66
test exam: ***01
test session: ***94
questions: 3
```

Safety properties:

```text
exam is unpublished / not visible to real students
test student/account synthetic only
session allowlist used
no real student PII used
no raw password/token/session token printed or committed
raw answers not printed
```

## 6. Env changes made for activation

Because the live VPS compose does not include shadow allowlist placeholders, the live `docker-compose.production.yml` was backed up and edited by targeted insertion in the `x-api-service` environment anchor only.

Backup directory for final attempt:

```text
/root/ujian_online_backups/phase-6.2-shadow-trial-20260607T051606Z
```

Pre-trial live compose checksum:

```text
b375cd474fd5e88d0c1ee44d46f59a4dcb2df91ded8f192d9b499e7ecb3e90d4  docker-compose.production.yml
```

Activated env values:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=<exact synthetic test session ID>
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Activation validation:

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
shadow_enabled=True
shadow_percentage=0
session_allowlist_size=1
exam_allowlist_size=0
expected_session_allowlisted=True
probe_expected=True
ACTIVATION_ENV_VALIDATE=PASS
```

## 7. Restart scope

Activation and cleanup used app-plane-only recreate because Docker environment changes require container recreation, not a simple restart.

App-plane services recreated:

```text
api_admin
api_admin2
api
api2
api3
api4
api5
api6
api7
api8
```

Health after each app-plane recreate returned 200.

Services not restarted/recreated:

```text
DB
Redis
PgBouncer
Nginx
Celery worker
Celery beat
Prometheus
Grafana
host machine
```

Data service StartedAt stayed unchanged throughout:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

## 8. Execution attempts and safety handling

### Attempt 1

Result:

```text
Failed before shadow activation due to host command `python` not existing on VPS.
VPS has python3, not python.
No shadow env activated.
No answer save executed.
Cleanup restored compose and closed synthetic session as abandoned.
```

### Attempt 2

Result:

```text
Shadow env activated successfully.
First answer request returned HTTP 403 before endpoint write.
Root cause: test User-Agent did not contain `seb` / `safe exam browser`, so SXBEnforcer blocked the API request.
Cleanup restored compose and closed synthetic session as abandoned.
No Redis shadow answer keys were created by this attempt.
```

403 body:

```json
{"detail":"Akses ditolak. Gunakan Aplikasi Ujian (APK) atau Safe Exam Browser."}
```

### Attempt 3

Result:

```text
Shadow env activated successfully.
SXB/SEB headers accepted after using User-Agent `Safe Exam Browser Phase6ShadowTrial/1.0`.
Answer saves succeeded.
Redis shadow hash-only validation passed.
Consistency checker invocation failed because scripts/runtime_buffer_consistency_check.py is not present inside the running API container image/mount.
Cleanup restored compose and closed synthetic session as abandoned.
```

Important result from this attempt:

```text
submit_q1_http=200
submit_q2_http=200
modify_q1_http=200
batch_q3_http=200
journal_q2_http=200
SHADOW_HASH_ONLY=PASS fields=3 ttl_answers=14398 ttl_meta=14398 shadow_key_count=3
runtime_answer_buffer_keys_after_answers=0
answer_queue_keys_after_answers=0
legacy_answer_queue_keys_after_answers=0
```

### Attempt 4 / final meaningful attempt

The consistency checker script was copied into the API container `/tmp` and run with `PYTHONPATH=/app`.

Answer save result:

```text
submit_q1_http=200
submit_q2_http=200
modify_q1_http=200
batch_q3_http=200
journal_q2_http=200
```

Redis shadow key validation:

```text
SHADOW_HASH_ONLY=PASS fields=3 ttl_answers=14398 ttl_meta=14398 shadow_key_count=5
runtime_shadow_keys_after_answers=5
runtime_answer_buffer_keys_after_answers=0
answer_queue_keys_after_answers=0
legacy_answer_queue_keys_after_answers=0
```

Interpretation:

```text
Shadow keys were hash-only.
No raw answer text, option arrays, answer metadata payload, username/full name, token, or session token was stored in shadow values.
The count of 5 includes prior known synthetic test shadow keys plus the final attempt keys and the shared shadow index.
```

## 9. Consistency checker result

Manual checker run after cleanup, including abandoned synthetic statuses, produced:

```json
{
  "checked_answers": 6,
  "checked_sessions": 10,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 2,
  "redis_errors": 0,
  "stale_runtime_sessions": 0
}
```

Result:

```text
payload_hash_mismatch=2
redis_errors=0
missing_in_redis=0
extra_in_redis=0
```

Decision:

```text
Phase 6.2 shadow trial: FAIL
Do not retry blindly.
Do not proceed to Phase 6 production.
```

## 10. Root cause analysis

Read-only diagnostic without raw answers/tokens/PII showed mismatches only on wrong-answer rows where `points_earned` was zero:

```json
{"session_mask":"***93","answer_count":3,"mismatch_count":1,"mismatches":[{"db_is_correct":false,"db_points_repr":"Decimal('0.00')","db_points_type":"Decimal","metadata_keys":["phase","step"],"question_mask":"***05","redis_hash_present":true}]}
{"session_mask":"***94","answer_count":3,"mismatch_count":1,"mismatches":[{"db_is_correct":false,"db_points_repr":"Decimal('0.00')","db_points_type":"Decimal","metadata_keys":["phase","step"],"question_mask":"***08","redis_hash_present":true}]}
```

Root cause:

```text
Redis shadow hash was generated at write time from runtime Python numeric values, e.g. float 0.0.
Consistency checker recomputed hashes from PostgreSQL Numeric values, e.g. Decimal('0.00').
answer_payload_hash() used str(points_earned), so 0.0 and Decimal('0.00') produced different canonical payloads.
```

Failure point:

```text
answer payload normalization / hash generation
```

This is not a Redis write failure and not a queue/hybrid issue.

## 11. Final submit result

```text
NOT RUN
```

Reason:

```text
The trial failed at the consistency checker gate before final submit.
Per failure rules, shadow was disabled and the synthetic session was closed as abandoned.
No further trial steps were executed.
```

## 12. Disable / rollback result

Rollback/disable executed automatically after each failed attempt:

```text
live docker-compose.production.yml restored from pretrial backup
app-plane recreated default-OFF
synthetic in-progress session closed as abandoned if still active
```

Final effective env after cleanup:

```text
ANSWER_WRITE_MODE=direct | settings.answer_write_mode=direct
ANSWER_QUEUE_ENABLED=false | settings.answer_queue_enabled=False
ANSWER_QUEUE_PERCENTAGE=0 | settings.answer_queue_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=UNSET | settings.answer_runtime_buffer_shadow_enabled=False
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=UNSET | settings.answer_runtime_buffer_shadow_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=UNSET | settings.answer_runtime_buffer_shadow_session_ids=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=UNSET | settings.answer_runtime_buffer_shadow_exam_ids=
session_allowlist=set()
exam_allowlist=set()
shadow_probe=False
```

Final health/readiness after cleanup:

```text
local /health=200
public /health=200
all containers=healthy
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Redis after cleanup:

```text
rejected_connections=0
evicted_keys=0
runtime_shadow_keys=5
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

Note:

```text
Exact old test shadow keys were not deleted because separate cleanup approval was not requested/granted.
They have TTL and are known synthetic Phase 6 test keys.
No broad Redis deletion was performed.
```

## 13. Error/log aggregate after cleanup

Final post-failure readiness timestamp:

```text
20260607T052344Z
```

Log aggregate since 15 minutes:

```text
traceback=0
connection_does_not_exist=0
broken_pipe=0
http_500=0
http_503_409=0
queue_hybrid_evidence=0
runtime_shadow_evidence=0
answer_save_errors=0
final_submit_errors=0
```

## 14. Source patch prepared default-OFF

A source-only patch was prepared after the failed trial:

```text
app/services/answer_runtime_buffer.py
```

Patch summary:

```text
Add canonical numeric normalization for answer payload hashes.
Make Decimal('0.00') and float 0.0 hash identically.
Make Decimal('1.00') and float 1.0 hash identically.
Make Decimal('0.50') and float 0.5 hash identically.
```

Regression test added:

```text
tests/test_answer_runtime_buffer_shadow.py
```

Patch validation:

```text
python -m compileall app: PASS
tests/test_answer_runtime_buffer_shadow.py: 10 passed
tests/test_answer_runtime_buffer_consistency.py: 3 passed
tests/test_production_readiness_defaults.py: 7 passed
tests/test_answer_sync_service_routing.py: 25 passed
runtime_buffer_consistency_check.py py_compile: PASS
runtime_buffer_consistency_check.py --help: PASS
git diff --check: PASS
forbidden artifact check: PASS
```

Deployment status of this patch:

```text
NOT DEPLOYED TO VPS in this task.
```

Per failure protocol:

```text
Do not re-run trial until the patch is reviewed and deployed default-OFF in a separate controlled deploy.
```

## 15. Forbidden artifact check

Result:

```text
PASS
```

No committed/copied artifacts in Git:

```text
APK/AAB
keystore/JKS/key.properties/local.properties
.env/.env.*
DB dump/backup/sql/sqlite/db
CSV/session artifacts
summary JSON artifacts
raw token/session token/student PII/raw answer content
```

Ephemeral VPS artifacts:

```text
backup directories under /root/ujian_online_backups/
remote /tmp scripts and temporary token file were used for execution only
raw token was removed by cleanup
```

## 16. Remaining blockers

Still blocked:

```text
Redis maxmemory-policy=allkeys-lru
Celery worker pool=solo / max-concurrency=1
No forced flush proof
No successful 0-mismatch real allowlisted shadow trial yet
No approval for queue/hybrid/runtime-buffer production
```

## 17. Final decision

```text
Phase 6.2 shadow trial: FAIL
Mismatch = 0: NO
payload_hash_mismatch: 2
Redis errors: 0
Answer save path: OK for controlled test session
Redis shadow hash-only write: OK
Final submit: NOT RUN due consistency failure
Shadow disabled after trial: YES
Queue/hybrid: NO
Runtime buffer source-of-truth: NO
Phase 6 production: NO
```

## 18. Next exact recommendation

Do not proceed to Phase 6 production.

Next safe step:

```text
Review and deploy the default-OFF hash normalization patch in a controlled Phase 6.2a fix deploy.
```

After that, request separate approval for a retry:

```text
approve Phase 6.2 retry shadow trial for test exam only
```

Retry constraints:

```text
one synthetic test session
session allowlist only
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
final submit only after consistency checker reports payload_hash_mismatch=0
```
