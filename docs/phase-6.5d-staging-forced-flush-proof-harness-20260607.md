# Phase 6.5d Staging Forced-Flush Proof Harness

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
5cd5e2bf90b020299df75b753218aeb82f6b3b3d
```

Commit reviewed:

```text
docs: add phase 6.5c staging forced flush proof plan
```

## 2. New commits before work

```text
new commits after 5cd5e2bf90b020299df75b753218aeb82f6b3b3d: none
```

Reviewed risk areas before work:

```text
scripts/staging_forced_flush_proof.py: did not exist yet
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

## 3. Why this is source-only/staging-only

This work adds a guarded harness skeleton for future staging proof. It does not execute against VPS production and does not change any runtime setting.

Production defaults remain unchanged:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Not performed:

```text
VPS deploy
service restart
.env change
docker-compose runtime change
queue/hybrid activation
runtime buffer production activation
DB migration/schema change
production load-test
APK touch
```

## 4. Files changed

```text
scripts/staging_forced_flush_proof.py
tests/test_staging_forced_flush_proof_safety.py
tests/test_staging_forced_flush_proof_cli.py
docs/phase-6.5d-staging-forced-flush-proof-harness-20260607.md
```

## 5. Harness CLI commands

Implemented CLI subcommands:

```text
python scripts/staging_forced_flush_proof.py preflight --staging-only --i-understand-this-is-staging-only
python scripts/staging_forced_flush_proof.py run-direct-baseline --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ --redact --i-understand-this-is-staging-only
python scripts/staging_forced_flush_proof.py run-shadow-baseline --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ --redact --i-understand-this-is-staging-only
python scripts/staging_forced_flush_proof.py run-buffer-drain --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ --redact --i-understand-this-is-staging-only
python scripts/staging_forced_flush_proof.py run-worker-restart --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ --redact --i-understand-this-is-staging-only
python scripts/staging_forced_flush_proof.py run-final-submit-pending --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ --redact --i-understand-this-is-staging-only
python scripts/staging_forced_flush_proof.py summarize --fail-on-mismatch --redact --i-understand-this-is-staging-only
python scripts/staging_forced_flush_proof.py cleanup-plan --redact --i-understand-this-is-staging-only
```

The current harness is intentionally `dry_run_stub` for scenario commands. It models output and guard behavior without touching DB/Redis.

## 6. Production refusal guards

The harness refuses to run unless:

```text
STAGING_FORCE_FLUSH_PROOF=true
APP_ENV/ENVIRONMENT/ENV are not production/prod
--i-understand-this-is-staging-only is provided
scenario commands include synthetic prefix containing PHASE6_FORCE_FLUSH_TEST
DATABASE_URL/DB_HOST host is in STAGING_PROOF_ALLOWED_DB_HOSTS
REDIS_URL/REDIS_HOST host is in STAGING_PROOF_ALLOWED_REDIS_HOSTS
temporary artifact directory is outside Git tree
```

It refuses known production target indicators:

```text
man1rokanhulu.cloud
103.175.218.56
adminujian
production-like DB names: exam_system, ujian_online, ujianonline
```

It also refuses missing staging allowlists:

```text
STAGING_PROOF_ALLOWED_DB_HOSTS
STAGING_PROOF_ALLOWED_REDIS_HOSTS
```

## 7. Redaction/safety guarantees

Default output is sanitized JSON with `redacted=true`.

The harness does not print:

```text
raw answer values
tokens
session tokens
usernames
full names
emails
phones
raw metadata objects
DB credentials
Redis credentials
```

`preflight`, `summarize`, and `cleanup-plan` are read-only/stubbed and report:

```text
no_db_writes=true
no_redis_writes=true
cleanup_deletion_executed=false
```

`cleanup-plan` never deletes by default and only prints the reviewed cleanup scope.

## 8. Scenario coverage

Modeled scenario commands:

```text
run-direct-baseline
run-shadow-baseline
run-buffer-drain
run-worker-restart
run-final-submit-pending
summarize
cleanup-plan
```

Current scope:

```text
safe harness structure
hard production-refusal guards
sanitized JSON shape
dry-run/stubbed execution only
no staging/prod execution yet
```

Future work can replace stubs with staging execution only after staging credentials/topology are approved.

## 9. Tests run and results

Environment:

```text
virtualenv: /tmp/ujianonline-phase65d-venv
```

Commands/results:

```text
python -m py_compile scripts/staging_forced_flush_proof.py: PASS
pytest tests/test_staging_forced_flush_proof_safety.py -q: 10 passed
pytest tests/test_staging_forced_flush_proof_cli.py -q: 9 passed
python -m compileall app: PASS
python -m py_compile scripts/runtime_buffer_consistency_check.py: PASS
python -m py_compile scripts/shadow_validation_summary.py: PASS
python -m py_compile scripts/staging_forced_flush_proof.py: PASS
pytest tests/test_shadow_validation_summary.py -q: 8 passed
pytest tests/test_answer_runtime_buffer_shadow.py -q: 10 passed
pytest tests/test_answer_runtime_buffer_consistency.py -q: 3 passed
pytest tests/test_answer_runtime_buffer_post_final_refresh.py -q: 4 passed
pytest tests/test_final_submit_shadow_refresh_logging.py -q: 4 passed
pytest tests/test_production_readiness_defaults.py -q: 7 passed
scripts/staging_forced_flush_proof.py --help: PASS
scripts/staging_forced_flush_proof.py preflight --help: PASS
scripts/staging_forced_flush_proof.py summarize --help: PASS
```

## 10. Forbidden artifact check

Result:

```text
FORBIDDEN_ARTIFACT_CHECK=PASS
```

No forbidden artifacts were added:

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

## 12. Remaining blockers

```text
Redis answer-critical topology not deployed
Redis production policy still allkeys-lru
Celery answer_flush topology not deployed
Current Celery production worker remains solo/concurrency=1
Forced-flush proof not executed in staging yet
Production canary not approved
Queue/hybrid production approval does not exist
```

## 13. Final decision

```text
harness source ready: YES
safe for staging review: YES
safe for production: NO
queue/hybrid production: NO
Phase 6 production: NO
```

Next step:

```text
Review the harness source. If approved, prepare a staging environment readiness checklist and only then execute the harness against staging with explicit approval. Do not run it against VPS production.
```
