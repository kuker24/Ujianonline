# Phase 6.5e Staging Readiness Checklist and Execution Plan

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
c131a421a71637e0700e65a4887503efd8e6674e
```

Commit reviewed:

```text
docs: record phase 6.5d staging forced flush harness
```

## 2. New commits before work

```text
new commits after c131a421a71637e0700e65a4887503efd8e6674e: none
```

Reviewed risk areas before work:

```text
scripts/staging_forced_flush_proof.py: existing guarded dry-run/stub harness
scripts/shadow_validation_summary.py: no new changes
scripts/runtime_buffer_consistency_check.py: no new changes
answer_runtime_buffer.py: no new changes
final_submit_service.py: no new changes
answer_sync_service.py: no new changes
answer_processor.py: no new changes
config/env/compose: no new changes
queue/hybrid activation: none
Redis source-of-truth changes: none
DB migration/schema: none
APK/AAB/keystore/.env/backup/dump/CSV artifacts: none
raw token/session/PII/raw answer content: none
```

## 3. Current Phase 6.5d harness status

Current harness:

```text
path: scripts/staging_forced_flush_proof.py
status: source ready
scenario execution mode: dry_run_stub
production refusal guards: implemented
default output: sanitized JSON
preflight/summarize/cleanup-plan: no DB/Redis writes
scenario commands: modeled only, not real DB/Redis execution yet
```

Guard review:

```text
requires STAGING_FORCE_FLUSH_PROOF=true
refuses APP_ENV/ENVIRONMENT/ENV production or prod
requires --i-understand-this-is-staging-only
requires synthetic prefix containing PHASE6_FORCE_FLUSH_TEST for scenario commands
requires STAGING_PROOF_ALLOWED_DB_HOSTS
requires STAGING_PROOF_ALLOWED_REDIS_HOSTS
requires DATABASE_URL/DB_HOST host to match staging DB allowlist
requires REDIS_URL/REDIS_HOST host to match staging Redis allowlist
refuses known production domain/IP patterns
refuses production-like DB names
requires temporary artifacts outside Git tree
cleanup-plan does not delete by default
```

Known production refusal patterns:

```text
man1rokanhulu.cloud
103.175.218.56
adminujian
production-like DB names: exam_system, ujian_online, ujianonline
```

## 4. Whether staging environment exists

Current known status:

```text
isolated staging environment: UNKNOWN / NOT VERIFIED
staging DB host: UNKNOWN / NOT VERIFIED
staging Redis host: UNKNOWN / NOT VERIFIED
redis_answers noeviction topology: UNKNOWN / NOT VERIFIED
celery_worker_answer_flush topology: UNKNOWN / NOT VERIFIED
ability to create synthetic staging sessions: UNKNOWN / NOT VERIFIED
```

Decision:

```text
Do not execute the harness yet.
Do not run it against VPS production.
Do not create synthetic sessions yet.
Do not change env/runtime yet.
```

## 5. Staging readiness checklist

### 5.1 Environment identity gates

All must be true before execution:

```text
[ ] APP_ENV is not production/prod
[ ] ENVIRONMENT is not production/prod
[ ] ENV is not production/prod, if set
[ ] public domain is not production domain
[ ] target IP is not production IP
[ ] DB host is not production host
[ ] Redis host is not production host
[ ] no production IP/domain appears in staging env/config
[ ] STAGING_FORCE_FLUSH_PROOF=true is set only in staging
[ ] STAGING_PROOF_TARGET_BASE_URL, if used, points to staging only
```

Explicitly forbidden targets:

```text
[ ] man1rokanhulu.cloud absent
[ ] 103.175.218.56 absent
[ ] adminujian absent
```

### 5.2 Required allowlists

All must be true:

```text
[ ] STAGING_PROOF_ALLOWED_DB_HOSTS is defined
[ ] STAGING_PROOF_ALLOWED_REDIS_HOSTS is defined
[ ] DATABASE_URL host matches STAGING_PROOF_ALLOWED_DB_HOSTS
[ ] DB_HOST, if used, matches STAGING_PROOF_ALLOWED_DB_HOSTS
[ ] REDIS_URL host matches STAGING_PROOF_ALLOWED_REDIS_HOSTS
[ ] REDIS_HOST, if used, matches STAGING_PROOF_ALLOWED_REDIS_HOSTS
[ ] staging DB name is not exam_system, ujian_online, or ujianonline
[ ] STAGING_PROOF_ARTIFACT_DIR points outside Git tree
```

### 5.3 Redis staging requirements

All must be true before forced-flush proof execution:

```text
[ ] separate redis_answers or equivalent isolated answer-critical Redis exists
[ ] redis_answers is not production Redis
[ ] maxmemory-policy=noeviction
[ ] AOF enabled
[ ] appendfsync documented
[ ] aof_last_bgrewrite_status=ok
[ ] rdb_last_bgsave_status=ok
[ ] rejected_connections=0
[ ] evicted_keys=0
[ ] runtime_answer_buffer_keys_count=0 before proof
[ ] answer_queue_keys_count=0 before proof
[ ] legacy_answer_queue_keys_count=0 before proof
[ ] answer-critical namespace scan clean before proof
[ ] no raw token/PII/raw answer key patterns
```

Blocker if:

```text
redis_answers is missing
redis_answers points to production Redis
answer-critical Redis policy is allkeys-lru
rejected_connections > 0
evicted_keys > 0
AOF unhealthy
```

### 5.4 Celery staging requirements

All must be true before proof execution:

```text
[ ] dedicated celery_worker_answer_flush exists
[ ] answer_flush queue binding exists
[ ] maintenance/default tasks do not consume answer_flush
[ ] answer_flush worker does not consume maintenance/default queues
[ ] worker pool is explicitly configured
[ ] concurrency explicit, preferably >=2 for staging proof
[ ] prefetch_multiplier=1 or equivalent controlled prefetch
[ ] queue pending metric visible
[ ] queue processing metric visible
[ ] queue deadletter metric visible
[ ] worker online/offline status visible
[ ] worker restart can be performed in staging only
[ ] worker restart does not affect production
```

Blocker if:

```text
only production Celery worker exists
answer_flush topology is not isolated
worker remains solo/concurrency=1 for answer_flush proof target
maintenance/default tasks can starve answer_flush
worker restart cannot be performed safely in staging
```

### 5.5 Database and synthetic data requirements

All must be true before proof execution:

```text
[ ] staging DB has production-like schema
[ ] staging DB is not production DB
[ ] no real student data is used
[ ] no real exam data is used
[ ] synthetic prefix is PHASE6_FORCE_FLUSH_TEST
[ ] synthetic account/exam/session creation path reviewed
[ ] cleanup path for synthetic rows documented
[ ] cleanup is staging-only
[ ] no DB migration/schema change is needed
[ ] rollback path documented before execution
```

Synthetic identity rule:

```text
exam/account prefix: __PHASE6_FORCE_FLUSH_TEST__
output: redacted IDs only
no raw answers/tokens/user PII printed
```

### 5.6 Tooling requirements

All must be true:

```text
[ ] scripts/staging_forced_flush_proof.py present
[ ] scripts/shadow_validation_summary.py present
[ ] scripts/runtime_buffer_consistency_check.py present
[ ] tools run with redaction default
[ ] output artifacts stored outside Git tree
[ ] no raw JSON artifacts committed
[ ] no CSV/session artifacts committed
[ ] no DB dumps committed
[ ] no secrets/tokens printed or committed
```

Current harness status:

```text
preflight: implemented as guarded read-only/stub
summarize: implemented as guarded read-only/stub
cleanup-plan: implemented as guarded non-destructive plan
scenario commands: dry_run_stub only; real staging DB/Redis operations are not implemented yet
```

## 6. Execution plan

Required approval text before any execution:

```text
approve Phase 6.5e run staging forced-flush proof on isolated staging only
```

If approval is missing:

```text
readiness checklist only
do not run harness against any environment
do not change env
do not restart services
do not create synthetic sessions
do not create Redis keys
do not run worker restart
```

Approval alone is not enough if staging readiness gates are not satisfied.

### Phase 1: staging preflight

Command:

```bash
python scripts/staging_forced_flush_proof.py preflight \
  --staging-only \
  --i-understand-this-is-staging-only
```

Required env before command:

```text
STAGING_FORCE_FLUSH_PROOF=true
APP_ENV=staging or equivalent non-production value
ENVIRONMENT=staging or equivalent non-production value
DATABASE_URL=<staging DB only>
REDIS_URL=<staging Redis only>
STAGING_PROOF_ALLOWED_DB_HOSTS=<staging DB host list>
STAGING_PROOF_ALLOWED_REDIS_HOSTS=<staging Redis host list>
STAGING_PROOF_ARTIFACT_DIR=/tmp/... outside Git tree
```

Pass output:

```text
staging_guard_passed=true
read_only=true
no_db_writes=true
no_redis_writes=true
safe_to_continue=true
redacted=true
```

### Phase 2: direct baseline

Command:

```bash
python scripts/staging_forced_flush_proof.py run-direct-baseline \
  --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ \
  --redact \
  --i-understand-this-is-staging-only
```

Expected future real execution behavior:

```text
direct PostgreSQL save only
queue/hybrid off
final submit direct
checker mismatch=0
```

Current harness note:

```text
currently dry_run_stub; does not create sessions or write DB/Redis
```

### Phase 3: shadow baseline

Command:

```bash
python scripts/staging_forced_flush_proof.py run-shadow-baseline \
  --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ \
  --redact \
  --i-understand-this-is-staging-only
```

Expected future real execution behavior:

```text
direct mode
session allowlist only
shadow hash-only
checker-before mismatch=0
checker-after mismatch=0
SHADOW_POST_FINAL_REFRESH_OK visible
```

Current harness note:

```text
currently dry_run_stub; does not enable shadow or write Redis
```

### Phase 4: buffer drain

Command:

```bash
python scripts/staging_forced_flush_proof.py run-buffer-drain \
  --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ \
  --redact \
  --i-understand-this-is-staging-only
```

Expected future real execution behavior:

```text
staging-only runtime buffer mode
redis_answers noeviction
answer_flush worker online
pending/processing/deadletter visible
queue drains to zero
checker mismatch=0
```

Current harness note:

```text
currently dry_run_stub; real buffer writes/drain not implemented
```

### Phase 5: worker restart during backlog

Command:

```bash
python scripts/staging_forced_flush_proof.py run-worker-restart \
  --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ \
  --redact \
  --i-understand-this-is-staging-only
```

Expected future real execution behavior:

```text
staging-only controlled backlog
restart only staging celery_worker_answer_flush
pending/processing drain to 0
no duplicate rows
latest answer state preserved
```

Current harness note:

```text
currently dry_run_stub; no worker is restarted
```

### Phase 6: final submit with pending buffer

Command:

```bash
python scripts/staging_forced_flush_proof.py run-final-submit-pending \
  --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ \
  --redact \
  --i-understand-this-is-staging-only
```

Expected future real execution behavior:

```text
pending buffer exists
final submit forces/verifies durable DB state before grading
HTTP 200 only when durable state verified
controlled 503 Retry-After acceptable if durable state cannot be verified
checker-after mismatch=0
```

Current harness note:

```text
currently dry_run_stub; no final submit is executed
```

### Phase 7: summary gate

Command:

```bash
python scripts/staging_forced_flush_proof.py summarize \
  --fail-on-mismatch \
  --redact \
  --i-understand-this-is-staging-only
```

Expected pass:

```text
payload_hash_mismatch=0
redis_errors=0
missing_in_redis=0
extra_in_redis=0
answer_queue_deadletter=0
final_submit_fail_count=0
safe_to_continue=true
```

### Phase 8: cleanup plan

Command:

```bash
python scripts/staging_forced_flush_proof.py cleanup-plan \
  --redact \
  --i-understand-this-is-staging-only
```

Expected behavior:

```text
cleanup_plan_only=true
cleanup_deletion_executed=false
cleanup_requires_separate_approval=true
no broad Redis deletion
exact synthetic keys/rows only after review
```

## 7. Required approval text

Exact approval needed before any staging execution:

```text
approve Phase 6.5e run staging forced-flush proof on isolated staging only
```

Reject execution if:

```text
approval missing
typo/incomplete approval
staging environment not proven isolated
production domain/IP/DB/Redis appears anywhere
```

## 8. Pass/fail criteria

PASS only if checklist proves:

```text
isolated staging exists
production hosts/domains are not targeted
production DB/Redis are not targeted
Redis answer-critical topology is noeviction
AOF healthy
rejected_connections=0
evicted_keys=0
Celery answer_flush topology is separated from maintenance/default
answer_flush concurrency explicit and suitable for proof
queue pending/processing/deadletter metrics visible
synthetic-only data guaranteed
cleanup path documented
harness refusal guards remain intact
```

FAIL/BLOCKED if:

```text
no staging environment exists
staging uses production DB
staging uses production Redis
staging uses production domain/IP
Redis remains allkeys-lru for answer-critical proof
Celery remains solo/concurrency=1 for answer_flush proof
synthetic-only data cannot be guaranteed
any secret/token/raw answer/real student data would be printed or committed
operator approval is missing
```

Current result:

```text
staging readiness documented: YES
safe to execute harness now: NO / BLOCKED until isolated staging is verified
```

## 9. Risks

Key risks before staging execution:

```text
accidentally pointing harness to production target
staging using copied production DB with real student data
Redis answer-critical policy not noeviction
Celery answer_flush not isolated from maintenance/default tasks
scenario commands are currently dry_run_stub and do not prove real flush yet
future real execution code may need stronger integration tests
cleanup accidentally deleting broad Redis keys or non-synthetic rows
```

Mitigations:

```text
hard production refusal guards
staging allowlist env vars
synthetic prefix requirement
redaction default
artifacts outside Git tree
cleanup-plan non-destructive by default
separate approval text before execution
```

## 10. Rollback and cleanup plan

Rollback first action for any future staging execution:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Then:

```text
recreate staging app-plane only if app/env changed
confirm staging health 200
confirm queue/hybrid OFF
confirm summary/checker gates clean
preserve sanitized diagnostics
```

Cleanup rules:

```text
no broad Redis deletion
exact synthetic Redis keys only after separate approval
synthetic DB row cleanup only in staging and only after review
no cleanup against production
no CSV/session artifact commit
no raw JSON artifact commit
```

Data-service rollback:

```text
Redis/Celery topology rollback in staging requires staging maintenance plan
production DB/Redis/PgBouncer must not be touched
```

## 11. Forbidden artifact check

Required before commit:

```text
git status --short | grep -E "(\.apk|\.aab|\.jks|\.keystore|key\.properties|local\.properties|\.env|apk_builds|static/apk|flutter_client_code/build|backup|dump|\.sql|\.sqlite|\.db|sessions.*\.csv|summary.*\.json)" && echo "BLOCKED: forbidden/sensitive file detected"
```

Expected result:

```text
FORBIDDEN_ARTIFACT_CHECK=PASS
```

## 12. Production action

```text
deploy: NO
restart: NO
env change: NO
migration: NO
load-test: NO
APK touch: NO
queue/hybrid activation: NO
runtime buffer production activation: NO
```

## 13. Remaining blockers

```text
Redis answer-critical topology not deployed
Redis production policy still allkeys-lru
Celery answer_flush topology not deployed
Current Celery production worker remains solo/concurrency=1
Forced-flush proof not executed in staging yet
Harness scenario commands are still dry_run_stub
Production canary not approved
Queue/hybrid production approval does not exist
```

## 14. Final decision

```text
staging readiness documented: YES
safe to execute harness now: NO / BLOCKED until isolated staging is verified and approval is given
safe for production: NO
Phase 6 production: NO
queue/hybrid production: NO
Redis source-of-truth: NO
```

Next exact step:

```text
Provision or identify a truly isolated staging environment, verify Redis noeviction answer-critical topology and dedicated Celery answer_flush topology, then request exact approval before any harness execution. If no staging exists, implement real harness execution paths only against a mocked/local staging target with production-refusal tests expanded.
```
