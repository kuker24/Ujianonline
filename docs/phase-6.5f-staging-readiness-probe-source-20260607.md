# Phase 6.5f Staging Readiness Probe Source

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
8fd2ef95d1c11b4830d144cf07aef5480523808b
```

Commit reviewed:

```text
docs: add phase 6.5e staging readiness checklist and execution plan
```

## 2. New commits before work

```text
new commits after 8fd2ef95d1c11b4830d144cf07aef5480523808b: none
```

## 3. Purpose

Phase 6.5e documented that staging readiness is still unknown. This Phase 6.5f change adds a source-only readiness probe command to the existing staging harness so operators can inspect declared staging readiness from environment variables without DB/Redis writes.

This does not execute the forced-flush proof.

## 4. Files changed

```text
scripts/staging_forced_flush_proof.py
tests/test_staging_forced_flush_proof_cli.py
docs/phase-6.5f-staging-readiness-probe-source-20260607.md
```

## 5. New CLI command

```bash
python scripts/staging_forced_flush_proof.py inspect-readiness \
  --staging-only \
  --i-understand-this-is-staging-only
```

The command remains guarded by the same production-refusal checks as the rest of the harness:

```text
STAGING_FORCE_FLUSH_PROOF=true required
APP_ENV/ENVIRONMENT/ENV must not be production/prod
DB/Redis hosts must match STAGING_PROOF_ALLOWED_* allowlists
known production domain/IP refused
production-like DB names refused
temporary artifacts must be outside Git tree
```

## 6. What the readiness probe checks

The probe reads only environment declarations and emits sanitized JSON.

Readiness fields include:

```text
staging_flag_enabled
db_host_allowlisted
redis_host_allowlisted
target_not_known_production
database_name_not_production_like
redis_policy_noeviction_declared
redis_aof_enabled_declared
celery_answer_flush_worker_declared
celery_answer_flush_queue_bound_declared
synthetic_data_ready_declared
cleanup_plan_ready_declared
real_execution_paths_present
```

Declaration env vars for future staging readiness review:

```text
STAGING_PROOF_REDIS_MAXMEMORY_POLICY=noeviction
STAGING_PROOF_REDIS_AOF_ENABLED=true
STAGING_PROOF_CELERY_ANSWER_FLUSH_WORKER=true
STAGING_PROOF_CELERY_ANSWER_FLUSH_QUEUE_BOUND=true
STAGING_PROOF_SYNTHETIC_DATA_READY=true
STAGING_PROOF_CLEANUP_PLAN_READY=true
```

## 7. Important limitation

The command intentionally does not connect to staging DB, Redis, or Celery.

It therefore reports:

```text
staging_environment_verified=false
safe_to_execute_harness_now=false
real_execution_paths_present=false
```

Even if all declaration variables are present, the current scenario commands remain:

```text
execution_mode=dry_run_stub
```

So the harness is still safe for source/staging review, but not yet a real forced-flush execution tool.

## 8. Redaction and no-write guarantees

The readiness probe sets:

```text
read_only=true
no_db_writes=true
no_redis_writes=true
cleanup_deletion_executed=false
redacted=true
```

It does not output:

```text
raw answers
tokens
session tokens
usernames/full names/emails/phones
raw metadata objects
DB credentials
Redis credentials
```

DB/Redis hosts are redacted in output.

## 9. Tests run

Commands/results:

```text
python -m py_compile scripts/staging_forced_flush_proof.py: PASS
pytest tests/test_staging_forced_flush_proof_safety.py -q: 10 passed
pytest tests/test_staging_forced_flush_proof_cli.py -q: 11 passed
```

## 10. Forbidden artifact check

Expected result before commit:

```text
FORBIDDEN_ARTIFACT_CHECK=PASS
```

No forbidden artifacts should be present:

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
queue/hybrid activation: NO
runtime buffer production activation: NO
```

## 12. Final decision

```text
staging readiness probe source ready: YES
real staging environment verified: NO
safe to execute harness now: NO
safe for production: NO
Phase 6 production: NO
queue/hybrid production: NO
Redis source-of-truth: NO
```

Next exact step:

```text
Identify/provision isolated staging, set the staging-only declaration env vars, run inspect-readiness there, and only after a clean readiness report decide whether to implement real staging DB/Redis execution paths. Do not run against VPS production.
```
