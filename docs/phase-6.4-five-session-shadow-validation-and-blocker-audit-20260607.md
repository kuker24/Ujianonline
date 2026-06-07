# Phase 6.4 Five-Session Shadow Validation and Blocker Audit

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
head reviewed before validation: d697b3267179bad8efe78846b7fd5e66cc56857f
message: docs: record phase 6.3 shadow summary tool copy result
```

## 2. New commits before validation

```text
new commits after d697b3267179bad8efe78846b7fd5e66cc56857f: none
```

Reviewed areas:

```text
scripts/shadow_validation_summary.py: read-only tool already copied to VPS
answer_runtime_buffer.py/final_submit_service.py: no new runtime changes
answer_sync_service.py: no queue/hybrid activation
config/env/compose: no activation before validation
DB migration/schema: none
APK/AAB/keystore/.env/backup/dump/CSV/raw token/PII/raw answer artifacts: none
```

## 3. Operator approval text

The task prompt contained the exact required approval:

```text
approve Phase 6.4 five-session shadow validation for synthetic sessions only
```

Scope applied:

```text
exactly 5 synthetic sessions
session allowlist only
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
no percentage rollout
no production load-test
no APK touch
no DB migration
no DB/Redis/PgBouncer restart
```

## 4. Pre-validation gates

GitHub and operational pre-gates:

```text
local /health=200
public /health=200
all app containers=running/healthy
DB=healthy
PgBouncer=healthy
Redis=PONG/healthy
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
rejected_connections=0
evicted_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false effective
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0 effective
session/exam allowlists empty
```

Pre-validation summary tool gate:

```json
{
  "checked_answers": 12,
  "checked_sessions": 10,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 0,
  "redis_errors": 0,
  "runtime_answer_buffer_keys_count": 0,
  "answer_queue_keys_count": 0,
  "legacy_answer_queue_keys_count": 0,
  "shadow_keys_without_ttl": 0,
  "post_final_refresh_meta_count": 4,
  "post_final_refresh_missing_count": 0,
  "read_only": true
}
```

Existing runtime shadow keys before activation were known synthetic hash-only TTL keys from prior Phase 6 validations.

Data service StartedAt before validation:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

## 5. Synthetic test scopes

Synthetic prefixes:

```text
exam prefix: __PHASE6_SHADOW_TEST__
account prefix: __PHASE6_SHADOW_TEST__
```

Sanitized scopes:

```text
scope_1: user=***72 exam=***07 session=***00
scope_2: user=***73 exam=***08 session=***01
scope_3: user=***74 exam=***09 session=***02
scope_4: user=***75 exam=***10 session=***03
scope_5: user=***76 exam=***11 session=***04
```

Each synthetic exam/session was unpublished and not visible to real students. No raw answers, tokens, session tokens, usernames, full names, emails, or real student data were printed.

## 6. Env changes made

Temporary shadow activation:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=<five exact synthetic session IDs>
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Unchanged production safety values:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
```

Activation validation:

```text
shadow_enabled=True
shadow_percentage=0
session_allowlist_size=5
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

Each recreate returned local/public health 200.

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

Data service StartedAt stayed unchanged after disable:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

## 9. Per-session answer save results

For each of the 5 synthetic sessions:

```text
submit_q1_http=200
submit_q2_http=200
modify_q1_http=200
batch_q3_http=200
journal_q2_http=200
SHADOW_HASH_ONLY_SESSION=PASS fields=3
runtime_answer_buffer_keys_mid=0
answer_queue_keys_mid=0
legacy_answer_queue_keys_mid=0
```

Each session included at least one correct path and one wrong-answer modification path.

## 10. Per-session checker-before results

```text
session_1 checker_before: checked_answers=15 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
session_2 checker_before: checked_answers=18 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
session_3 checker_before: checked_answers=21 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
session_4 checker_before: checked_answers=24 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
session_5 checker_before: checked_answers=27 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
```

All checker-before validations passed.

## 11. Per-session final submit results

```text
session_1 final_submit_http=200 status=submitted refresh_ok 0→1 refresh_failed=0
session_2 final_submit_http=200 status=submitted refresh_ok 1→2 refresh_failed=0
session_3 final_submit_http=200 status=submitted refresh_ok 2→3 refresh_failed=0
session_4 final_submit_http=200 status=submitted refresh_ok 3→4 refresh_failed=0
session_5 final_submit_http=200 status=submitted refresh_ok 4→5 refresh_failed=0
```

`SHADOW_POST_FINAL_REFRESH_OK` was visible/incremented for all five final submits.

## 12. Per-session checker-after results

```text
session_1 checker_after: checked_answers=15 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
session_2 checker_after: checked_answers=18 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
session_3 checker_after: checked_answers=21 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
session_4 checker_after: checked_answers=24 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
session_5 checker_after: checked_answers=27 payload_hash_mismatch=0 redis_errors=0 missing=0 extra=0
```

All checker-after validations passed.

## 13. Summary tool output

Final summary tool gate before disable:

```json
{
  "checked_answers": 27,
  "checked_sessions": 20,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 0,
  "redis_errors": 0,
  "runtime_answer_buffer_keys_count": 0,
  "answer_queue_keys_count": 0,
  "legacy_answer_queue_keys_count": 0,
  "shadow_keys_without_ttl": 0,
  "sessions_with_shadow": 9,
  "post_final_refresh_meta_count": 9,
  "post_final_refresh_missing_count": 0,
  "read_only": true
}
```

Result:

```text
SUMMARY_TOOL_FINAL_VALIDATE=PASS
```

Post-disable summary tool audit:

```json
{
  "checked_answers": 27,
  "checked_sessions": 20,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 0,
  "redis_errors": 0,
  "runtime_answer_buffer_keys_count": 0,
  "answer_queue_keys_count": 0,
  "legacy_answer_queue_keys_count": 0,
  "shadow_keys_without_ttl": 0,
  "sessions_with_shadow": 9,
  "post_final_refresh_meta_count": 9,
  "post_final_refresh_missing_count": 0,
  "read_only": true
}
```

## 14. Disable/rollback result

Shadow was disabled by restoring the compose backup and recreating app-plane only.

Post-disable validation:

```text
DISABLE_ENV_VALIDATE=PASS
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false effective
session_allowlist=set()
exam_allowlist=set()
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
```

Post-disable gates:

```text
health_post_disable_local=200
health_post_disable_public=200
rejected_connections=0
evicted_keys=0
runtime_answer_buffer_keys_post_disable=0
answer_queue_keys_post_disable=0
legacy_answer_queue_keys_post_disable=0
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
DATA_SERVICE_STARTED_AT_UNCHANGED=PASS
```

## 15. Post-disable observation

Observation duration:

```text
30 minutes
```

Final observation:

```text
health_final_observe_local=200
health_final_observe_public=200
all containers=running/healthy
rejected_connections=0
evicted_keys=0
runtime_shadow_keys_final=19
runtime_answer_buffer_keys_final=0
answer_queue_keys_final=0
legacy_answer_queue_keys_final=0
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

`runtime_shadow_keys_final=19` are synthetic hash-only TTL keys from Phase 6 validations. No broad Redis deletion was performed.

## 16. Error/log aggregate counts

Immediate post-disable:

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
shadow_refresh_failed=0
```

Final observation:

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
shadow_refresh_failed=0
```

## 17. Redis blocker audit

Redis config/status:

```text
maxmemory-policy=allkeys-lru
maxmemory=1468006400
maxmemory_human=1.37G
used_memory_human=10.02M
used_memory_peak_human=14.38M
rejected_connections=0
evicted_keys=0
appendonly=yes
appendfsync=everysec
aof_enabled=1
aof_last_bgrewrite_status=ok
rdb_last_bgsave_status=ok
```

Decision:

```text
Redis policy is NOT safe for answer source-of-truth because allkeys-lru can evict any key under memory pressure. Redis remains acceptable only for hash-only, best-effort shadow evidence while PostgreSQL remains source-of-record.
```

## 18. Celery blocker audit

Celery worker status:

```text
pool implementation=celery.concurrency.solo:TaskPool
max-concurrency=1
prefetch_count=4
runtime_answer_queue_keys=0
legacy_answer_queue_keys=0
celery_keys=0
kombu_keys=0
```

Decision:

```text
Current Celery topology is NOT ready for answer flush production. Solo pool/concurrency=1 is insufficient proof for queue/hybrid answer writes under real load.
```

## 19. Forced flush blocker audit

Code-state audit:

```text
flush_runtime_answer_buffer_for_session_present=True
forced_flush_function_present=True
runtime_buffer_enabled_gate_present=True
final_submit_reads_shadow_keys=False
redis_shadow_source_of_truth=False
```

Decision:

```text
Final submit still does not read Redis shadow for grading/status. Forced flush hooks exist, but production-like forced-flush proof is still missing. This remains a blocker for queue/hybrid production.
```

## 20. Production canary readiness

Effective env/canary audit:

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
shadow_enabled=False
shadow_percentage=0
canary_approved=NO
phase6_production_ready=NO
```

Required guardrails before any production canary:

```text
safe Redis memory policy or non-evicting answer-key design
dedicated scalable answer flush worker topology
forced flush proof under staging/canary topology
read-only validation gate using shadow_validation_summary.py
explicit operator approval
clear rollback plan
no percentage rollout without separate design approval
```

## 21. Forbidden artifact check

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

## 22. Final decision

```text
Phase 6.4 five-session validation: PASS
Summary tool gate: PASS
5/5 synthetic sessions answer-save PASS
5/5 checker-before mismatch=0
5/5 final submit HTTP 200/submitted
5/5 SHADOW_POST_FINAL_REFRESH_OK visible
5/5 checker-after mismatch=0
Phase 6 production: NO
Queue/hybrid: NO
Runtime buffer source-of-truth: NO
```

Next step:

```text
Stop production enablement. Prepare an infrastructure readiness plan focused on Redis eviction policy, Celery worker topology, and forced-flush proof before any queue/hybrid/canary discussion.
```
