# Phase 6.2d Shadow Retry After Post-Final Refresh Result

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
head reviewed before trial: fab0b5dc8f302bf7c8aa980d45fddbcec956e4c5
message: docs: record phase 6.2c default-off deploy result
```

## 2. New commits before trial

```text
new commits after fab0b5dc8f302bf7c8aa980d45fddbcec956e4c5: none
```

Reviewed before trial:

```text
answer_runtime_buffer.py: Phase 6.2c refresh_runtime_answer_shadow_from_db live
final_submit_service.py: post-commit best-effort refresh hook live
answer_sync_service.py: no queue/hybrid activation
config/env/compose: no activation before trial
DB migration/schema: none
APK/AAB/keystore/.env/backup/dump/CSV/raw token/PII/raw answer artifacts: none
```

## 3. Operator approval text

The task prompt contained the exact required approval:

```text
approve Phase 6.2c retry shadow trial for test exam only
```

Scope applied:

```text
one synthetic test session only
session allowlist only
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
no percentage rollout
no production load-test
no APK touch
no DB migration
no DB/Redis/PgBouncer restart
```

## 4. Pre-enable gates

Before activation, stale synthetic shadow keys from prior attempts were allowed to expire naturally. Baseline checker after waiting:

```json
{
  "checked_answers": 0,
  "checked_sessions": 10,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 0,
  "redis_errors": 0,
  "stale_runtime_sessions": 0
}
```

Preflight timestamp:

```text
PHASE62D_TRIAL_TS=20260607T101739Z
```

Backup directory:

```text
/root/ujian_online_backups/phase-6.2d-shadow-retry-after-post-final-refresh-20260607T101739Z
```

Health and services:

```text
local_health_http=200
public_health_http=200
all app containers=running/healthy
DB=healthy
PgBouncer=healthy
Redis=healthy/PONG
Nginx=healthy
Celery worker/beat=healthy
```

DB gates:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Redis gates:

```text
rejected_connections=0
evicted_keys=0
runtime_shadow_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
PRE_EXISTING_SHADOW_KEYS_TEST_ONLY=PASS count=0 sessions=0
```

Env/source marker gates before activation:

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
answer_runtime_buffer_shadow_enabled=False
answer_runtime_buffer_shadow_percentage=0
answer_runtime_buffer_shadow_session_ids=
answer_runtime_buffer_shadow_exam_ids=
session_allowlist=set()
exam_allowlist=set()
marker_refresh_runtime_answer_shadow_from_db=True
marker_SHADOW_POST_FINAL_REFRESH_OK=True
marker_SHADOW_POST_FINAL_REFRESH_FAILED=True
PRE_ENV_SOURCE_MARKERS=PASS
```

Data services StartedAt before trial:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

## 5. Synthetic test scope

Synthetic prefixes:

```text
exam prefix: __PHASE6_SHADOW_TEST__
account prefix: __PHASE6_SHADOW_TEST__
```

Sanitized scope:

```text
test user: ***68
test exam: ***03
test session: ***96
questions: 3
```

Safety properties:

```text
exam unpublished / not visible to real students
one synthetic student
one synthetic exam
one synthetic session
no real student PII printed
no raw answer values printed
no raw token/session token printed
```

## 6. Env changes made

Live compose was backed up and temporarily edited only to enable one-session shadow allowlist.

Compose checksum before activation:

```text
b375cd474fd5e88d0c1ee44d46f59a4dcb2df91ded8f192d9b499e7ecb3e90d4  docker-compose.production.yml
```

Temporary activation values:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=<exact synthetic test session ID>
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Unchanged safety values:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
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

## 7. Restart/recreate scope

App-plane only, one by one:

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

Each app-plane recreate returned local `/health=200`.

## 8. Services not restarted

Not restarted/recreated:

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

Data services StartedAt remained unchanged after disable/final observation:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

## 9. Answer save results

Controlled synthetic writes:

```text
submit_q1_http=200
submit_q2_http=200
modify_q1_http=200
batch_q3_http=200
journal_q2_http=200
```

Included:

```text
at least one correct answer path: YES
at least one wrong answer path: YES
```

## 10. Redis shadow key validation

After answer saves:

```text
SHADOW_HASH_ONLY=PASS fields=3 ttl_answers=14397 ttl_meta=14397 shadow_key_count=3
runtime_shadow_keys_after_answers=3
runtime_answer_buffer_keys_after_answers=0
answer_queue_keys_after_answers=0
legacy_answer_queue_keys_after_answers=0
```

Confirmed hash-only payload shape:

```text
question_id
payload_hash
updated_at
```

Not present in Redis shadow payloads:

```text
raw answer_text
raw selected option payload
raw answer_metadata object
username/full name
raw token/session token
```

## 11. Checker-before output

Before final submit:

```json
{
  "checked_answers": 3,
  "checked_sessions": 10,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 0,
  "redis_errors": 0,
  "stale_runtime_sessions": 0
}
```

Result:

```text
CHECKER_BEFORE_VALIDATE=PASS
```

## 12. Final submit result

Final submit was run only after checker-before PASS.

```text
final_submit_http=200
final_submit_status=submitted
```

Final submit remained PostgreSQL/direct:

```text
no Redis shadow read for grading/status
Redis shadow not source-of-truth
```

## 13. Post-final shadow refresh marker

Docker log marker check immediately after final submit:

```text
post_final_refresh_ok_count=0
post_final_refresh_failed_count=0
```

The trial script stopped at this strict log-marker check and triggered cleanup/disable. No retry was performed.

Equivalent sanitized post-final refresh evidence was then collected read-only from Redis meta and checker output:

```json
{
  "session_mask": "***96",
  "status": "submitted",
  "is_synthetic": true,
  "answer_fields": 3,
  "payload_key_sets": [
    ["payload_hash", "question_id", "updated_at"],
    ["payload_hash", "question_id", "updated_at"],
    ["payload_hash", "question_id", "updated_at"]
  ],
  "ttl_answers": 14271,
  "ttl_meta": 14271,
  "meta": {
    "answer_count": "3",
    "exam_id": "MASKED",
    "refreshed_after_final_submit": "true",
    "refreshed_at": "2026-06-07T10:19:37.084685+00:00",
    "refreshed_from_db": "true",
    "session_id": "MASKED",
    "updated_at": "2026-06-07T10:19:37.084685+00:00"
  }
}
```

Interpretation:

```text
Post-final refresh function executed and refreshed hash-only shadow meta, but the INFO log marker was not emitted/visible in Docker logs. The Redis meta fields are an equivalent sanitized success marker for this trial.
```

No `SHADOW_POST_FINAL_REFRESH_FAILED` marker was observed.

## 14. Checker-after output

After final submit and cleanup-disable, checker result:

```json
{
  "checked_answers": 3,
  "checked_sessions": 10,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 0,
  "redis_errors": 0,
  "stale_runtime_sessions": 0
}
```

Result:

```text
checker_exit=0
payload_hash_mismatch=0
redis_errors=0
```

This is the key Phase 6.2c retry success gate.

## 15. Disable/rollback result

Because the strict log marker check returned 0, the shell trap restored compose and disabled shadow immediately:

```text
== cleanup: restore compose and disable shadow ==
```

App-plane cleanup recreate completed for:

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

Synthetic session cleanup:

```text
UPDATE 0
```

Interpretation:

```text
UPDATE 0 is expected because the synthetic session had already been final-submitted successfully and was no longer active/in_progress.
```

Post-disable effective settings:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false effective
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0 effective
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
session_allowlist=set()
exam_allowlist=set()
shadow_probe=False
```

## 16. Post-disable observation

Observation duration:

```text
30 minutes
```

Immediate post-disable timestamp:

```text
PHASE62_READINESS_TS=20260607T102157Z
```

Final observation timestamp:

```text
PHASE62_READINESS_TS=20260607T105213Z
```

Health after observation:

```text
local_health_http=200
public_health_http=200
all containers=running/healthy
DB=healthy
PgBouncer=healthy
Redis=healthy/PONG
```

DB gates after observation:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Redis after observation:

```text
rejected_connections=0
evicted_keys=0
runtime_shadow_keys=3
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

Note:

```text
runtime_shadow_keys=3 are the exact current synthetic Phase 6.2d hash-only shadow keys with TTL. No broad Redis deletion was performed.
```

## 17. Error/log aggregate counts

Immediate post-disable aggregate since 15 minutes:

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

Final observation aggregate since 15 minutes:

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

## 18. Forbidden artifact check

Result:

```text
FORBIDDEN_ARTIFACT_CHECK=PASS
```

No forbidden artifact was committed or deployed:

```text
APK/AAB
keystore/JKS/key.properties/local.properties
.env/.env.*
DB dump/backup/sql/sqlite/db
CSV/session artifacts
summary JSON artifacts
raw token/session token/student PII/raw answer content
```

## 19. Final decision

```text
Phase 6.2d shadow retry: PASS
Checker-before mismatch=0: YES
Checker-after mismatch=0: YES
Final submit with shadow observed: YES
Post-final refresh observed: YES, via equivalent sanitized Redis meta marker
Post-final refresh log marker visible: NO
Queue/hybrid: NO
Runtime buffer production: NO
Phase 6 production: NO
```

Important note:

```text
The functional Phase 6.2c fix is proven by checker-after payload_hash_mismatch=0 and refreshed_after_final_submit=true meta. However, the INFO-level SHADOW_POST_FINAL_REFRESH_OK log was not visible in Docker logs, so future observability work should make this marker visible if operators require log-based proof.
```

Next step:

```text
Stop Phase 6 production. Do not enable queue/hybrid/runtime-buffer production.
Recommended next work is an observability-only source patch or logging configuration review so SHADOW_POST_FINAL_REFRESH_OK appears reliably, followed by another default-OFF deploy if needed. Production Phase 6 remains blocked by Redis allkeys-lru policy, Celery solo worker, no forced flush proof, and no approved production canary.
```
