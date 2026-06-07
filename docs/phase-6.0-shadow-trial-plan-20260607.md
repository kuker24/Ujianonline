# Phase 6.0 Shadow Trial Plan — Runtime Answer Buffer Hash Mirror

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
reviewed head before this plan: 16a95565085ad7937b9e95f6700571088618ca60
message: docs: record phase 5.7 vps deploy result for activity logs read path
new commits before planning: none
```

Forbidden/new-activation review:

```text
queue/hybrid activation: none
runtime shadow activation: none
.env change: none
DB migration/schema change: none
APK/AAB/keystore/.env/backup/dump/CSV artifacts: none
```

## 2. Phase 5.7 status summary

Source of record:

```text
docs/phase-5.7-vps-deploy-result-activity-logs-read-path-20260607.md
```

Key result:

```text
Phase 5.6 deploy: PASS
Activity logs read path live: YES
Admin API noise clean: YES for about 65 minutes
ConnectionDoesNotExistError: 0 during observation
BrokenPipeError: 0 during observation
/api/activity/logs ~74s behavior reproduced: NO
HTTP 500: 0
answer/final-submit errors: 0
queue/hybrid evidence: 0
runtime shadow evidence: 0
```

Decision from Phase 5.7:

```text
Phase 6 production may start: NO
Queue/hybrid may start: NO
Phase 6 shadow trial can be planned next: PARTIAL
```

## 3. Current direct safe-mode confirmation

VPS read-only readiness check timestamp:

```text
20260607T034819Z
```

Effective application settings:

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
answer_runtime_buffer_shadow_enabled=False
answer_runtime_buffer_shadow_percentage=0
exam_peak_mode=True
violation_async_enabled=True
admin_monitoring_detail_level=summary
mobile_apk_primary=True
```

Production behavior remains:

```text
PostgreSQL direct write is source-of-truth: YES
Redis answer buffer source-of-truth: NO
queue/hybrid: OFF
runtime shadow: OFF
final submit highest priority: unchanged
```

## 4. Current source shadow behavior review

Reviewed files:

```text
app/config.py
app/services/answer_runtime_buffer.py
app/services/answer_sync_service.py
app/services/final_submit_service.py
scripts/runtime_buffer_consistency_check.py
tests/test_answer_runtime_buffer_shadow.py
tests/test_answer_runtime_buffer_consistency.py
docs/phase-5.1-direct-hardening-and-phase-6-shadow-readiness-20260606.md
docs/phase-5-6-vps-architecture-readiness-audit-20260606.md
docs/phase-5.7-vps-deploy-result-activity-logs-read-path-20260607.md
```

Confirmed before the allowlist patch:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED default false: YES
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE default 0: YES
Shadow stores deterministic payload hashes only: YES
Shadow does not store raw answers: YES
Shadow failure is best-effort and returns 0: YES
Direct DB write still happens before/around shadow marker: YES
Final submit does not read Redis shadow keys: YES
Queue/hybrid flags remain false/0 by default: YES
Consistency checker is read-only: YES
Consistency checker does not print raw answers/PII/tokens: YES
```

Gap found:

```text
The existing shadow selector was only percentage-based.
It could not safely restrict a live trial to one named test session or one named test exam.
```

## 5. Source-only guard patch added

Because the current shadow code could not scope a trial to a specific test session/exam, this plan includes a source-only default-off guard patch.

New config keys:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=""
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=""
```

Behavior:

```text
Shadow remains disabled unless ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true.
When enabled, shadow is active for a write only if:
  1. session_id is explicitly allowlisted; OR
  2. exam_id is explicitly allowlisted; OR
  3. percentage gate passes.
Default empty allowlists and percentage 0 mean no shadow writes.
```

Changed files for source guard:

```text
app/config.py
app/services/answer_runtime_buffer.py
.env.example
docker-compose.production.yml
tests/test_answer_runtime_buffer_shadow.py
tests/test_production_readiness_defaults.py
```

Important deployment note:

```text
This patch is source-only in GitHub. It was not deployed to VPS by this plan.
The live docker-compose.production.yml on VPS must not be overwritten blindly because it differs from GitHub.
Any later deployment of compose/env plumbing requires separate diff review and explicit operator approval.
```

## 6. VPS readiness check

Health:

```text
local /health: 200
public /health: 200
DB: accepting connections
PgBouncer: accepting connections
Redis: PONG
```

DB gates:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Redis:

```text
used_memory_human=10.31M
used_memory_peak_human=14.00M
maxmemory_human=1.37G
maxmemory=1468006400
maxmemory-policy=allkeys-lru
rejected_connections=0
evicted_keys=0
runtime_shadow_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

Celery:

```text
celery_worker: running/healthy
celery_beat: running/healthy
pool implementation: celery.concurrency.solo:TaskPool
max-concurrency: 1
prefetch_count: 4
```

## 7. Redis readiness and allkeys-lru warning

Redis is healthy for a controlled shadow/hash-only test:

```text
PING=PONG
rejected_connections=0
evicted_keys=0
runtime shadow keys=0
runtime buffer keys=0
queue keys=0
```

But Redis remains unsafe as a production answer source-of-truth:

```text
maxmemory-policy=allkeys-lru
```

Implication:

```text
Redis may evict keys under pressure.
Therefore Redis must not be the only copy of answers.
Redis must not be used by final submit as source-of-truth.
Runtime buffer production remains blocked.
```

For Phase 6.0 shadow only:

```text
Acceptable only because Redis stores hash mirrors only, PostgreSQL remains source-of-truth, final submit ignores Redis shadow, and Redis failures do not affect student responses.
```

## 8. Worker readiness and solo-pool warning

Celery worker is healthy but not production-ready for answer flush workload:

```text
pool=solo
max-concurrency=1
```

Implication:

```text
Queue/hybrid answer flushing remains blocked.
No Phase 6 production buffer/canary should run with this worker profile.
```

Phase 6.0 shadow does not require Celery answer flush because it does not route writes to queue/hybrid.

## 9. Why Phase 6 production remains blocked

Production queue/hybrid/runtime-buffer remains blocked by:

```text
1. Redis maxmemory-policy=allkeys-lru; unsafe for source-of-truth answer storage.
2. Celery worker pool=solo and concurrency=1; not proven for answer flush load.
3. No forced-flush proof under real staging/shadow/canary.
4. No 0-mismatch evidence from runtime_buffer_consistency_check.py under a real shadow mirror yet.
5. Queue/hybrid would change production write path; not approved.
6. Final submit must remain PostgreSQL/direct-first and not depend on Redis.
```

Final decision:

```text
Phase 6 production: NO
Queue/hybrid production: NO
Runtime buffer production source-of-truth: NO
```

## 10. Shadow trial design

Purpose:

```text
Prove that direct PostgreSQL answer writes can be mirrored to Redis as deterministic payload hashes without changing student response behavior, final submit behavior, scoring, or source-of-truth.
```

Scope:

```text
one internal/test exam only
one or a few test accounts only
not during real exam
short test window, recommended 10-30 minutes
no production load-test
no APK change
no DB migration/schema change
```

Write path invariant:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
PostgreSQL direct write remains source-of-truth
Redis shadow is best-effort hash-only mirror
Final submit ignores Redis shadow
```

Shadow data shape:

```text
runtime:answer_shadow:session:{session_id}:answers
  field: question_id
  value JSON keys only:
    question_id
    payload_hash
    updated_at

runtime:answer_shadow:session:{session_id}:meta
  session_id
  exam_id
  answer_count
  updated_at
```

No raw answer text, option arrays, answer metadata details, usernames, tokens, or student PII are stored in shadow keys.

## 11. Enablement steps for a later approved trial

Do not run these steps until the operator explicitly approves the trial.

Approval text required:

```text
approve Phase 6.0 shadow trial for test exam only
```

Pre-enable gates:

```text
Phase 5.7 remains clean after at least 60 minutes
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
Redis rejected_connections=0
Redis evicted_keys=0
test exam ID identified
test session ID identified if using session allowlist
test account identified
rollback path confirmed
```

Recommended env for one test session:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=<test_session_id>
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Alternative env for one test exam:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=<test_exam_id>
```

Avoid initial percentage rollout:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
```

Only after allowlist trial is clean should a separate plan consider a tiny deterministic percentage.

Restart scope if env-based enablement is approved:

```text
app-plane only: api_admin, api_admin2, api, api2-api8
no DB restart
no Redis restart
no PgBouncer restart
no Nginx restart unless separately required
no Celery restart required for shadow-only
```

## 12. Rollback steps

Rollback for shadow trial:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Then app-plane-only rolling restart if env/config based.

Do not restart:

```text
DB
Redis
PgBouncer
```

Redis cleanup:

```text
No cleanup required because shadow keys have TTL.
Optional cleanup of test-only shadow keys is allowed only if exact test session ID is known and operator approves.
Never delete broad Redis patterns during production hours.
```

## 13. Validation commands/checks for approved trial

Health and gates:

```bash
curl -fsS http://127.0.0.1/health
curl -fsS https://man1rokanhulu.cloud/health
```

DB gates:

```sql
select count(*) from exam_sessions where status in ('active','in_progress','started');
select count(*) from exams where is_published = true and coalesce(is_deleted,false) = false and now() between start_time and end_time;
select count(*) from exam_sessions where status in ('submitting','finalizing');
select count(*) from pg_stat_activity where state='active' and now()-query_start > interval '60 seconds' and pid <> pg_backend_pid();
select count(*) from pg_stat_activity where state='idle in transaction';
```

Redis checks:

```bash
redis-cli PING
redis-cli INFO stats | grep -E '^(rejected_connections|evicted_keys):'
redis-cli --scan --pattern 'runtime:answer_shadow:*' | wc -l
redis-cli --scan --pattern 'runtime:session:*:answers' | wc -l
redis-cli --scan --pattern 'runtime:answer_queue:*' | wc -l
```

Endpoint checks using the test account/session only:

```text
answer save returns normal 200 response
final submit returns normal success response
admin monitoring remains healthy
no queue/hybrid evidence in logs
no runtime buffer production keys beyond shadow keys
```

## 14. Consistency checker usage

After test answers are saved and shadow keys exist:

```bash
python scripts/runtime_buffer_consistency_check.py --limit 10
```

Expected output fields:

```json
{
  "checked_sessions": 0,
  "checked_answers": 0,
  "missing_in_redis": 0,
  "extra_in_redis": 0,
  "payload_hash_mismatch": 0,
  "stale_runtime_sessions": 0,
  "redis_errors": 0
}
```

For the approved shadow test, pass criteria should include:

```text
checked_sessions > 0
checked_answers > 0
payload_hash_mismatch = 0
redis_errors = 0
```

The checker is read-only and prints aggregates only. It must not be run with options that expose session IDs unless operator debugging requires it. It never prints raw answers, tokens, usernames, full names, or student PII.

## 15. Pass/fail criteria

Pass if all are true:

```text
health public/local = 200
answer save response unaffected
final submit response unaffected
Redis shadow keys created only for the allowed test session/exam
runtime buffer production keys remain 0
queue keys remain 0
consistency checker payload_hash_mismatch=0
consistency checker redis_errors=0
Redis rejected_connections=0
Redis evicted_keys=0
DB long active queries=0
idle-in-transaction=0
ConnectionDoesNotExistError=0
BrokenPipeError=0
HTTP 500=0
final-submit errors=0
answer save errors=0
queue/hybrid evidence=0
runtime shadow can be disabled and app-plane restarted cleanly
```

Fail/rollback if any are true:

```text
activity/log/admin API regression
answer save 5xx/503/409 burst
final submit error
payload_hash_mismatch > 0
redis_errors > 0
Redis rejected_connections or evicted_keys increases
runtime buffer production keys appear unexpectedly
queue/hybrid evidence appears
DB long active queries or idle-in-transaction appears
ConnectionDoesNotExistError/BrokenPipe cluster returns
```

## 16. Forbidden artifact check

Source check result after patch/tests:

```text
APK/AAB: none
keystore/JKS/key.properties/local.properties: none
.env/.env.*: none
DB dump/backup/sql/sqlite/db: none
session CSV/summary JSON: none
raw token/session/student PII/answer content: none
```

Result:

```text
forbidden artifact check: PASS
```

## 17. Validation of source-only patch

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
compileall: PASS
tests/test_answer_runtime_buffer_shadow.py: 9 passed
tests/test_answer_runtime_buffer_consistency.py: 3 passed
tests/test_production_readiness_defaults.py: 7 passed
tests/test_answer_sync_service_routing.py: 25 passed
runtime_buffer_consistency_check.py py_compile: PASS
runtime_buffer_consistency_check.py --help: PASS
git diff --check: PASS
forbidden artifact check: PASS
```

## 18. Final decision

```text
Phase 6 production: NO
Queue/hybrid: NO
Runtime buffer production source-of-truth: NO
Shadow trial can be planned: YES
Shadow trial can be activated now: NO
```

Activation remains blocked until all are present:

```text
1. source allowlist guard deployed in a separate controlled deploy;
2. operator approval text: approve Phase 6.0 shadow trial for test exam only;
3. exact test exam/account/session identified;
4. pre-enable gates all pass;
5. rollback owner/path confirmed.
```
