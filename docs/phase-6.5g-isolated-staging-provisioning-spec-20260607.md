# Phase 6.5g Isolated Staging Provisioning Spec

Date: 2026-06-07

## 1. Purpose

Define the minimum isolated staging environment required before running the Phase 6.5d/6.5f forced-flush harness beyond dry-run/stub mode.

This is a source-only planning document. It does not provision infrastructure, deploy to VPS production, run the harness, change runtime config, or approve queue/hybrid production.

## 2. Current status

Latest known branch head before this document:

```text
f671fac9f71c7bde13c8c8075471a69edd1167b2
```

Known status:

```text
Phase 6.4 five-session shadow validation: PASS
Phase 6.5/6.5a/6.5b/6.5c design docs: created
Phase 6.5d staging forced-flush proof harness: source ready
Phase 6.5f inspect-readiness probe: source ready
real isolated staging environment: not verified
real forced-flush execution paths: not implemented
production canary: not approved
```

Production remains:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

## 3. Non-goals

This spec does not authorize:

```text
production deploy
production restart
production .env change
production docker-compose runtime change
queue/hybrid activation
runtime buffer production activation
Redis source-of-truth
production load-test
DB migration/schema change
APK touch
copying production DB dumps into Git
committing credentials, tokens, PII, raw answers, CSV/session artifacts, or JSON result artifacts
```

## 4. Isolation requirements

A valid staging environment must be isolated in all of these dimensions:

```text
separate domain/base URL from production
separate DB host from production
separate Redis host from production
separate Celery worker containers from production
separate app containers from production
separate secrets from production
separate artifact directory outside Git tree
no production IP/domain in staging env/config
no real student data required for proof
```

Explicit production targets that must not appear:

```text
man1rokanhulu.cloud
103.175.218.56
adminujian
```

Staging DB name must not be production-like:

```text
exam_system
ujian_online
ujianonline
```

## 5. Minimum service topology

Required services:

```text
staging_api
staging_api_admin, optional if admin endpoints are used
staging_db
staging_pgbouncer, if production-like DB pooling is part of proof
staging_redis_cache, optional for cache/broker separation
staging_redis_answers
staging_celery_worker_maintenance
staging_celery_worker_answer_flush
staging_celery_beat, optional if scheduled proof tasks are needed
```

Redis answer-critical topology:

```text
service: staging_redis_answers
maxmemory-policy=noeviction
AOF enabled
appendfsync documented
rejected_connections=0 before proof
evicted_keys=0 before proof
namespace scan clean before proof
```

Celery answer flush topology:

```text
service: staging_celery_worker_answer_flush
queue binding: answer_flush only
maintenance/default queues excluded
concurrency: explicit, initial proof preferably >=2
prefetch_multiplier=1 or equivalent controlled prefetch
worker restart permitted in staging only
queue pending/processing/deadletter metrics visible
```

## 6. Required staging environment variables

The harness readiness probe requires these declarations:

```text
STAGING_FORCE_FLUSH_PROOF=true
APP_ENV=staging
ENVIRONMENT=staging
DATABASE_URL=<staging DB URL only>
REDIS_URL=<staging Redis URL only>
STAGING_PROOF_ALLOWED_DB_HOSTS=<comma-separated staging DB hosts>
STAGING_PROOF_ALLOWED_REDIS_HOSTS=<comma-separated staging Redis hosts>
STAGING_PROOF_ARTIFACT_DIR=/tmp/ujianonline-staging-proof
STAGING_PROOF_REDIS_MAXMEMORY_POLICY=noeviction
STAGING_PROOF_REDIS_AOF_ENABLED=true
STAGING_PROOF_CELERY_ANSWER_FLUSH_WORKER=true
STAGING_PROOF_CELERY_ANSWER_FLUSH_QUEUE_BOUND=true
STAGING_PROOF_SYNTHETIC_DATA_READY=true
STAGING_PROOF_CLEANUP_PLAN_READY=true
```

Do not store these values in a committed `.env` file. Keep operator-local/staging-only configuration outside Git.

## 7. Data policy

Synthetic-only rules:

```text
exam/account prefix: __PHASE6_FORCE_FLUSH_TEST__
no real student data
no real exam data
no production token/session token
no raw answer output
no PII output
redaction default
```

If staging needs a schema/data seed:

```text
schema must be created through approved staging setup only
production DB dumps must not be committed
if production-like anonymized data is used, anonymization must be proven before import
synthetic test rows must be cleanly identifiable by prefix
cleanup must be exact-scope and staging-only
```

## 8. Pre-provisioning checklist

Before provisioning or identifying staging:

```text
[ ] operator confirms this is not VPS production
[ ] staging hostname/IP selected and documented
[ ] staging DB host selected and documented
[ ] staging Redis hosts selected and documented
[ ] production secrets are not reused
[ ] artifact path outside Git selected
[ ] rollback owner identified
[ ] cleanup owner identified
[ ] no real students/exams needed
```

## 9. Post-provisioning readiness checks

After staging exists, run only readiness inspection first:

```bash
python scripts/staging_forced_flush_proof.py inspect-readiness \
  --staging-only \
  --i-understand-this-is-staging-only
```

Expected current result:

```text
staging_guard_passed=true
read_only=true
no_db_writes=true
no_redis_writes=true
redacted=true
safe_to_execute_harness_now=false
```

Important: `safe_to_execute_harness_now=false` remains expected until real execution paths are implemented and reviewed.

Readiness declaration should at least show:

```text
redis_policy_noeviction_declared=true
redis_aof_enabled_declared=true
celery_answer_flush_worker_declared=true
celery_answer_flush_queue_bound_declared=true
synthetic_data_ready_declared=true
cleanup_plan_ready_declared=true
```

## 10. Real execution path prerequisites

Before replacing dry-run/stub scenario behavior with real staging DB/Redis operations:

```text
staging target verified isolated
inspect-readiness output reviewed
real execution design reviewed
production refusal tests expanded
DB/Redis write operations scoped to synthetic prefix
cleanup path tested in staging only
summary/checker gates integrated
failure/rollback behavior tested in unit/integration tests
```

Real execution code must keep these hard refusals:

```text
refuse production APP_ENV/ENVIRONMENT/ENV
refuse known production host/domain/IP
refuse production-like DB names
require staging DB/Redis allowlists
require synthetic prefix
redact by default
write artifacts outside Git tree
```

## 11. Approval required before any staging run

Exact approval text before real staging execution:

```text
approve Phase 6.5e run staging forced-flush proof on isolated staging only
```

Approval is invalid if:

```text
staging isolation is not verified
Redis answer-critical topology is missing/noeviction not declared
Celery answer_flush topology is missing
synthetic-only data cannot be guaranteed
cleanup plan is missing
```

## 12. Rollback and cleanup requirements

First rollback action in staging:

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
no broad Redis deletion
exact synthetic Redis keys only after approval
synthetic DB rows only by prefix and only in staging
preserve sanitized diagnostics before cleanup
no raw JSON/CSV/session artifacts committed
```

## 13. Pass/fail decision for provisioning

Provisioning is ready only if:

```text
isolated staging services exist
production hosts/domains absent
DB/Redis allowlists point only to staging
redis_answers noeviction declared and verified
AOF healthy
celery_worker_answer_flush exists and is isolated
synthetic data creation path reviewed
cleanup path reviewed
inspect-readiness PASS for guard checks
```

Blocked if:

```text
no staging exists
staging points to production DB/Redis/domain
Redis answer-critical policy is allkeys-lru
Celery answer_flush worker is absent or not isolated
scenario commands remain dry_run_stub and operator expects real proof
approval is missing
```

## 14. Final decision

```text
isolated staging provisioning spec: READY
production action: NO
harness execution: NO
real staging proof: BLOCKED until staging is provisioned/verified and real execution paths are reviewed
Phase 6 production: NO
queue/hybrid production: NO
Redis source-of-truth: NO
```

Next exact step:

```text
Operator should identify or provision isolated staging, then run inspect-readiness there. After a clean readiness review, implement real staging execution paths in the harness; do not run anything against VPS production.
```
