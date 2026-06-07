# Phase 6.5h Staging Availability and Provisioning Audit

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
a6ce71a97dbc35e6d5078aba85380448922d11f6
```

Commit reviewed:

```text
docs: add phase 6.5g isolated staging provisioning spec
```

## 2. New commits before work

Branch fetched:

```text
review/sanitized-root-20260531-115153
```

Comparison:

```text
base: a6ce71a97dbc35e6d5078aba85380448922d11f6
head: a6ce71a97dbc35e6d5078aba85380448922d11f6
```

Result:

```text
new commits after Phase 6.5g: none
```

Because no new commits existed, there were no changed files to review. The staging audit still reviewed the relevant current files and categories:

```text
scripts/staging_forced_flush_proof.py
tests/test_staging_forced_flush_proof_cli.py
tests/test_staging_forced_flush_proof_safety.py
scripts/shadow_validation_summary.py
scripts/runtime_buffer_consistency_check.py
app/services/answer_runtime_buffer.py
app/services/final_submit_service.py
app/services/answer_sync_service.py
app/tasks/answer_processor.py
docker-compose.production.yml
docs/phase-6.5e-staging-readiness-checklist-and-execution-plan-20260607.md
docs/phase-6.5f-staging-readiness-probe-source-20260607.md
docs/phase-6.5g-isolated-staging-provisioning-spec-20260607.md
older isolated staging docs from Phase 4.3.2B/4.3.2D
```

No unexpected production activation was found in the reviewed source state.

## 3. Audit scope and method

This was a read-only source/docs audit. It did not connect to production DB, production Redis, production Celery, production containers, or external staging infrastructure.

Searched safe repo/operator-visible sources for:

```text
staging
redis_answers
celery_worker_answer_flush
answer_flush
STAGING_FORCE_FLUSH_PROOF
STAGING_PROOF_ALLOWED_DB_HOSTS
STAGING_PROOF_ALLOWED_REDIS_HOSTS
STAGING_PROOF_REDIS_MAXMEMORY_POLICY
STAGING_PROOF_CELERY_ANSWER_FLUSH_WORKER
STAGING_PROOF_CELERY_ANSWER_FLUSH_QUEUE_BOUND
```

Sources checked:

```text
docker-compose*.yml
deployment docs
docs/phase-6.5g-isolated-staging-provisioning-spec-20260607.md
docs/phase-6.5e-staging-readiness-checklist-and-execution-plan-20260607.md
CI/CD configs, if present
scripts directory
README/deployment docs
```

Secrets were not inspected or exposed. `.env` files were excluded.

## 4. Existing staging evidence found

### 4.1 Files that mention Phase 6.5 staging concepts

Source/docs references exist in these files:

```text
docs/phase-6.5-infrastructure-readiness-plan-redis-celery-20260607.md
docs/phase-6.5a-redis-answer-critical-design-20260607.md
docs/phase-6.5b-celery-answer-flush-topology-design-20260607.md
docs/phase-6.5c-staging-forced-flush-proof-plan-20260607.md
docs/phase-6.5d-staging-forced-flush-proof-harness-20260607.md
docs/phase-6.5e-staging-readiness-checklist-and-execution-plan-20260607.md
docs/phase-6.5f-staging-readiness-probe-source-20260607.md
docs/phase-6.5g-isolated-staging-provisioning-spec-20260607.md
scripts/staging_forced_flush_proof.py
tests/test_staging_forced_flush_proof_cli.py
tests/test_staging_forced_flush_proof_safety.py
```

Interpretation:

```text
These are design/spec/harness/test references, not evidence that a real isolated staging environment currently exists.
```

### 4.2 Compose/service evidence

Repo contains only:

```text
docker-compose.production.yml
```

No staging compose/service names were found in compose:

```text
staging_api: not found
staging_db: not found
staging_redis_cache: not found
staging_redis_answers: not found
staging_celery_worker_answer_flush: not found
ujian_staging compose project: not found
redis_answers service: not found
celery_worker_answer_flush service: not found
```

Production compose still shows safe/off answer defaults in source:

```text
ANSWER_WRITE_MODE=${ANSWER_WRITE_MODE:-direct}
ANSWER_QUEUE_ENABLED=${ANSWER_QUEUE_ENABLED:-false}
ANSWER_QUEUE_PERCENTAGE=${ANSWER_QUEUE_PERCENTAGE:-0}
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=${ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED:-false}
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=${ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE:-0}
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=${ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS:-}
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=${ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS:-}
```

Production compose also still shows known blockers:

```text
Redis maxmemory-policy allkeys-lru
Celery worker --pool=solo
```

### 4.3 Historical staging status evidence

Earlier staging docs already recorded that staging was not found/provisioned:

```text
docs/phase-4.3.2b-isolated-staging-target-plan-20260604.md:
  Production live stack only + staging is provisionable only with explicit approval.
  No separate staging API service/port, staging DB/schema, or staging Redis policy was verified.

docs/phase-4.3.2d-approved-isolated-staging-provisioning-20260604.md:
  production live stack only; isolated staging target does not exist.
  Separate staging VM/VPS not approved/provisioned.
  Same-VPS ujian_staging compose not approved/provisioned.
  Staging API/DB/Redis not available.
```

Phase 6.5e/6.5g carried that forward:

```text
isolated staging environment: UNKNOWN / NOT VERIFIED
staging DB host: UNKNOWN / NOT VERIFIED
staging Redis host: UNKNOWN / NOT VERIFIED
redis_answers noeviction topology: UNKNOWN / NOT VERIFIED
celery_worker_answer_flush topology: UNKNOWN / NOT VERIFIED
ability to create synthetic staging sessions: UNKNOWN / NOT VERIFIED
```

## 5. Does isolated staging exist?

Audit answer:

```text
isolated staging exists: UNKNOWN / NOT VERIFIED
repo evidence of provisioned staging: NO
safe proof that staging is separated from production domain/IP/DB/Redis/Celery/secrets: NO
```

Conservative operational decision:

```text
Treat isolated staging as not available until an operator provides/verifies sanitized staging identifiers and inspect-readiness can be run against staging-only configuration.
```

## 6. Readiness classification

Classification:

```text
BLOCKED
```

Reason:

```text
No real isolated staging environment was proven by source/docs audit.
No staging DB/Redis/Celery identifiers were verified.
No redis_answers noeviction service exists in compose/source.
No dedicated celery_worker_answer_flush service exists in compose/source.
Synthetic data creation path is planned but not implemented/proven.
Cleanup path is planned but exact-scope execution is not implemented/proven.
Harness scenario commands still use dry_run_stub.
```

Why not `READY_FOR_INSPECT_READINESS`:

```text
Cannot prove isolated staging exists.
Cannot prove staging DB/Redis/Celery are separate from production.
Cannot prove staging secrets are separate.
Cannot prove redis_answers noeviction topology exists.
Cannot prove dedicated answer_flush worker exists.
Cannot prove synthetic-only data path exists.
```

Why not `PARTIAL`:

```text
There are source docs and a guarded readiness probe, but no real staging component was verified. Without an identifiable staging target, even inspect-readiness has no safe target yet.
```

## 7. Missing components

Required but missing/unverified:

```text
isolated staging domain/base URL or localhost-only endpoint
staging_api
staging_api_admin, if admin paths are needed
staging_db with production-like schema and staging-only credentials
staging_pgbouncer, if production-like pooling is required
staging_redis_cache, optional if cache/broker separation is used
staging_redis_answers with noeviction
staging_celery_worker_maintenance
staging_celery_worker_answer_flush bound only to answer_flush
staging_celery_beat, optional
staging-only secrets outside Git
staging-only artifact directory outside Git tree
synthetic exam/account/session creation implementation
exact-scope synthetic cleanup implementation
real forced-flush execution paths in harness
operator-provided sanitized staging identifiers
operator approval for staging execution
```

## 8. Concrete provisioning runbook

### 8.1 Preferred path: separate staging VM/VPS

Use a separate host when available.

Required properties:

```text
no production domain/IP
no production DB/Redis/Celery containers
no production secrets
no production data required
staging-only network
staging-only env file outside Git
synthetic-only dataset
```

Minimum services:

```text
staging_api
staging_api_admin, optional if admin paths are required
staging_db
staging_pgbouncer, if production-like pooling is required
staging_redis_cache, optional
staging_redis_answers
staging_celery_worker_maintenance
staging_celery_worker_answer_flush
staging_celery_beat, optional
```

### 8.2 Acceptable fallback: same-VPS isolated compose only with explicit approval

Allowed only if operator explicitly approves and confirms no active exam/load risk.

Isolation requirements:

```text
compose project: ujian_staging or equivalent
API bound to localhost-only, e.g. 127.0.0.1:18080
no public Nginx route by default
separate staging Docker network
separate staging DB container/database
separate staging Redis answer-critical container
separate staging Celery workers
staging-only env outside Git
no production DB write
no production Redis write
cleanup touches only staging resources
```

This fallback is not approved by this audit. It remains an option for operator approval.

### 8.3 Redis answer-critical config

Required for `staging_redis_answers`:

```text
maxmemory-policy=noeviction
AOF enabled
appendfsync documented
rejected_connections=0 before proof
evicted_keys=0 before proof
namespace scan clean before proof
answer-critical namespace contains no raw token/PII/raw answer key patterns
```

Suggested pre-proof observations, staging only:

```text
redis_answers responds to PING
CONFIG GET maxmemory-policy returns noeviction
INFO persistence indicates AOF health acceptable
INFO stats rejected_connections=0
INFO stats evicted_keys=0
SCAN answer-critical namespaces returns only expected synthetic/pre-proof keys or zero keys
```

### 8.4 Celery answer_flush config

Required for `staging_celery_worker_answer_flush`:

```text
queue binding: answer_flush only
maintenance/default queues excluded
explicit concurrency, preferably >=2 for proof
prefetch_multiplier=1 or controlled equivalent
queue pending/processing/deadletter metrics visible
worker restart permitted in staging only
worker restart cannot affect production
```

Maintenance/default worker requirements:

```text
staging_celery_worker_maintenance must not consume answer_flush
maintenance/export/analytics tasks must not starve answer_flush
answer_flush queue tasks must be idempotent before real proof
```

### 8.5 Staging data policy

Synthetic-only:

```text
synthetic prefix: __PHASE6_FORCE_FLUSH_TEST__
no real student names/usernames/emails/phones
no real exam content needed
no raw answer content printed
no production token/session token reuse
redacted IDs only in logs/reports
```

Schema/data options:

```text
Option A: create schema from migrations/setup into empty staging DB.
Option B: import anonymized production-like schema/data only if anonymization is independently proven before import.
Option C: minimal synthetic schema/data sufficient for answer-save/final-submit proof.
```

Forbidden:

```text
committing DB dumps
committing CSV/session artifacts
committing raw JSON summaries
using real student data in proof
using production tokens or APK build secrets
```

## 9. Required staging env declarations

These must be configured only in staging/operator-local env, not committed to Git:

```text
STAGING_FORCE_FLUSH_PROOF=true
APP_ENV=staging
ENVIRONMENT=staging
DATABASE_URL=<staging DB URL only>
REDIS_URL=<staging Redis URL only>
STAGING_PROOF_ALLOWED_DB_HOSTS=<staging DB hosts>
STAGING_PROOF_ALLOWED_REDIS_HOSTS=<staging Redis hosts>
STAGING_PROOF_ARTIFACT_DIR=/tmp/ujianonline-staging-proof
STAGING_PROOF_REDIS_MAXMEMORY_POLICY=noeviction
STAGING_PROOF_REDIS_AOF_ENABLED=true
STAGING_PROOF_CELERY_ANSWER_FLUSH_WORKER=true
STAGING_PROOF_CELERY_ANSWER_FLUSH_QUEUE_BOUND=true
STAGING_PROOF_SYNTHETIC_DATA_READY=true
STAGING_PROOF_CLEANUP_PLAN_READY=true
```

Do not include production domain/IP in any staging target/env:

```text
man1rokanhulu.cloud
103.175.218.56
adminujian
```

Do not use production-like DB names:

```text
exam_system
ujian_online
ujianonline
```

## 10. Inspect-readiness command plan

Only after an isolated staging target is proven, run this command on staging/local operator shell with staging-only env:

```bash
python scripts/staging_forced_flush_proof.py inspect-readiness \
  --staging-only \
  --i-understand-this-is-staging-only
```

Expected safe output fields:

```text
staging_guard_passed=true
read_only=true
no_db_writes=true
no_redis_writes=true
redacted=true
safe_to_execute_harness_now=false
redis_policy_noeviction_declared=true
redis_aof_enabled_declared=true
celery_answer_flush_worker_declared=true
celery_answer_flush_queue_bound_declared=true
synthetic_data_ready_declared=true
cleanup_plan_ready_declared=true
```

Why `safe_to_execute_harness_now=false` is still expected:

```text
scenario commands remain dry_run_stub
real staging DB/Redis execution paths are not implemented
real synthetic data/cleanup flows are not implemented
```

Do not run this command against VPS production.

## 11. Harness status and source gap analysis

Current harness status:

```text
path: scripts/staging_forced_flush_proof.py
preflight: guarded read-only/stub
inspect-readiness: guarded read-only declaration probe
summarize: guarded read-only/stub
cleanup-plan: guarded non-destructive plan
scenario commands: dry_run_stub
real execution mode: not implemented
```

Current source evidence:

```text
SCENARIO_COMMANDS include:
  run-direct-baseline
  run-shadow-baseline
  run-buffer-drain
  run-worker-restart
  run-final-submit-pending

execution_mode is dry_run_stub
real_execution_paths_present is false
real_execution_note says real staging DB/Redis execution is not implemented
```

Still missing real execution paths:

```text
synthetic exam/account/session creation in staging
direct baseline real API/DB interaction
shadow baseline real allowlist/env handling
buffer drain real Redis/runtime buffer operations
worker restart control for staging answer_flush worker
final submit pending-buffer proof
summary/checker integration with real staging state
cleanup exact-scope execution
sanitized proof artifact generation outside Git
integration tests against a fake/local staging adapter
operator approval gate for any write/restart staging command
```

Do not implement these real paths until explicitly requested and after staging is proven isolated.

## 12. Risks

Key risks:

```text
accidentally targeting VPS production with staging env
same-VPS staging causing CPU/RAM/I/O contention during exam hours
staging DB accidentally using production data or production credentials
staging Redis accidentally using production Redis or allkeys-lru policy
answer_flush worker not isolated and being starved by maintenance tasks
real execution implementation printing raw answer/token/PII data
cleanup deleting broad Redis keys or non-synthetic DB rows
operator mistaking inspect-readiness declaration pass for real forced-flush proof
```

Mitigations:

```text
keep production refusal guards
require staging DB/Redis host allowlists
require explicit staging confirmation flag
require synthetic prefix
redact output by default
store artifacts outside Git tree
cleanup-plan remains non-destructive by default
run inspect-readiness before any real execution
require separate exact approval before staging execution
```

## 13. Rollback and cleanup requirements

First rollback action for any future staging execution:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Cleanup rules:

```text
cleanup staging resources only
no production DB/Redis/PgBouncer restart
no broad Redis deletion
exact synthetic Redis keys only after approval
synthetic DB rows only by prefix and only in staging
preserve sanitized diagnostics before cleanup
no raw JSON/CSV/session artifacts committed
no secrets/tokens/PII/raw answers printed or committed
```

If same-VPS staging is used:

```text
stop only staging compose project
remove only staging containers/network/volumes after preserving sanitized aggregates
remove staging env file from non-Git path
leave production app/db/redis/pgbouncer untouched
```

## 14. Forbidden artifact check

Before commit, run:

```bash
git status --short | grep -E "(.apk|.aab|.jks|.keystore|key.properties|local.properties|.env|apk_builds|static/apk|flutter_client_code/build|backup|dump|.sql|.sqlite|.db|sessions.*.csv|summary.*.json)" && echo "BLOCKED: forbidden/sensitive file detected"
```

Expected result:

```text
FORBIDDEN_ARTIFACT_CHECK=PASS
```

This audit document must not include:

```text
APK/AAB
keystore/JKS/key.properties/local.properties
.env/.env.*
DB dump/backup/sql/sqlite/db
CSV/session artifacts
summary JSON artifacts
full tokens/session tokens
raw PII
raw answer content
```

## 15. Production action

```text
deploy: NO
restart: NO
env change: NO
migration: NO
load-test: NO
APK touch: NO
queue enablement: NO
hybrid enablement: NO
runtime buffer production activation: NO
Redis source-of-truth: NO
```

Production defaults must remain:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

## 16. Remaining blockers before production canary

```text
isolated staging not verified
inspect-readiness not run on a proven staging target
redis_answers noeviction topology not provisioned/proven
celery_worker_answer_flush topology not provisioned/proven
real harness execution paths not implemented
forced-flush proof not executed in staging
summary/checker real staging integration missing
cleanup exact-scope execution missing
production canary plan not approved
queue/hybrid production approval missing
production Redis still allkeys-lru
production Celery still solo/concurrency=1
```

## 17. Final decision

```text
staging availability audited: YES
staging exists: UNKNOWN / NOT VERIFIED
readiness classification: BLOCKED
safe to run inspect-readiness now: NO, unless operator first provides a proven isolated staging target and staging-only env
safe to run forced-flush proof now: NO
Phase 6 production: NO
queue/hybrid production: NO
Redis source-of-truth: NO
production action: NO
```

Next exact recommendation:

```text
1. Operator provisions or identifies isolated staging with separate DB, Redis answers noeviction, and dedicated answer_flush worker.
2. Operator provides sanitized staging identifiers only: host class/name, DB host alias, Redis host alias, Celery worker names; no secrets.
3. Run inspect-readiness only against staging-only env outside Git.
4. If inspect-readiness is clean, request source work to implement real staging execution paths in the harness, still default-off and production-refusing.
5. Only after real staging forced-flush proof passes, draft a separate production canary proposal. Do not proceed to production Phase 6 now.
```
