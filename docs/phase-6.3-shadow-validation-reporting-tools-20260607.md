# Phase 6.3 Shadow Validation Reporting Tools

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
head reviewed before work: abe3eb700a66865a7b54c10438c44c743bd81f03
message: docs: record phase 6.2e deploy and repeated shadow validation
```

## 2. New commits before work

```text
new commits after abe3eb700a66865a7b54c10438c44c743bd81f03: none
```

Reviewed areas:

```text
answer_runtime_buffer.py: no runtime change
final_submit_service.py: no runtime change
scripts: new read-only reporting tool only
config/env/compose: no changes
queue/hybrid activation: none
Redis source-of-truth changes: none
DB migration/schema: none
APK/AAB/keystore/.env/backup/dump/CSV artifacts: none
raw token/session/PII/raw answer content: none
```

## 3. Why this is read-only/reporting only

The new Phase 6.3 tool only reads:

```text
PostgreSQL exam_sessions/answers for consistency sampling
Redis shadow hashes and metadata
Redis key TTLs and key counts
```

It does not:

```text
delete Redis keys
set/write Redis keys
mutate PostgreSQL
submit/final-submit sessions
enable shadow
enable queue/hybrid
change env or compose
change DB schema
```

## 4. Files changed

```text
scripts/shadow_validation_summary.py
tests/test_shadow_validation_summary.py
docs/phase-6.3-shadow-validation-reporting-tools-20260607.md
```

No production runtime service file was changed in this phase.

## 5. Script usage

Basic usage:

```bash
SECRET_KEY=test-secret-key \
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test \
python scripts/shadow_validation_summary.py
```

Production/container usage example:

```bash
PYTHONPATH=/app python /tmp/shadow_validation_summary.py --limit 10 --fail-on-mismatch
```

Filter examples:

```bash
python scripts/shadow_validation_summary.py --session-id 123 --fail-on-mismatch
python scripts/shadow_validation_summary.py --exam-id 55 --limit 10
python scripts/shadow_validation_summary.py --no-redact
```

Default behavior:

```text
JSON output
redaction enabled
read-only
no fail unless --fail-on-mismatch is passed
```

## 6. Output fields

The JSON summary includes:

```text
checked_sessions
checked_answers
payload_hash_mismatch
redis_errors
missing_in_redis
extra_in_redis
stale_runtime_sessions
runtime_shadow_keys_count
runtime_answer_buffer_keys_count
answer_queue_keys_count
legacy_answer_queue_keys_count
oldest_shadow_key_age_seconds
newest_shadow_key_age_seconds
ttl_min_seconds
ttl_max_seconds
shadow_keys_without_ttl
sessions_with_shadow
shadow_session_ids
post_final_refresh_meta_count
post_final_refresh_missing_count
log_marker_expected_note
filters
sampled_session_ids
read_only
```

## 7. Redaction/safety guarantees

Redaction is enabled by default:

```text
session IDs are masked as ***NN
exam/session filters are masked in output when redaction is enabled
```

The script does not output:

```text
raw answer_text
raw selected option payload
raw answer metadata object
username/full name/email/phone
raw token/session token/access token
raw Redis values beyond aggregate health fields and hashes used internally
```

The tests include source-level read-only checks to prevent Redis write/delete calls and sensitive field output.

## 8. Fail-on-mismatch behavior

When `--fail-on-mismatch` is used, the script exits non-zero if any of these are true:

```text
payload_hash_mismatch > 0
redis_errors > 0
shadow_keys_without_ttl > 0
answer_queue_keys_count > 0
legacy_answer_queue_keys_count > 0
runtime_answer_buffer_keys_count > 0
```

This makes the tool suitable for gated read-only validation after synthetic shadow trials.

## 9. Tests run and results

Environment:

```text
SECRET_KEY=test-secret-key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test
```

Commands and results:

```text
python -m compileall app
PASS

python -m py_compile scripts/runtime_buffer_consistency_check.py
PASS

python -m py_compile scripts/shadow_validation_summary.py
PASS

pytest tests/test_shadow_validation_summary.py -q
8 passed

pytest tests/test_answer_runtime_buffer_shadow.py -q
10 passed

pytest tests/test_answer_runtime_buffer_consistency.py -q
3 passed

pytest tests/test_answer_runtime_buffer_post_final_refresh.py -q
4 passed

pytest tests/test_final_submit_shadow_refresh_logging.py -q
4 passed

pytest tests/test_production_readiness_defaults.py -q
7 passed

SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test python scripts/runtime_buffer_consistency_check.py --help
PASS

SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test python scripts/shadow_validation_summary.py --help
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

## 12. Final decision

```text
reporting tool ready: YES
safe for default-OFF deploy/copy plan: YES
Phase 6 production: NO
queue/hybrid: NO
```

Next step:

```text
Create a controlled copy/deploy plan for scripts/shadow_validation_summary.py as a read-only operations tool. Then run it after a new approved synthetic repeated validation if stronger evidence is required. Do not enable queue/hybrid/runtime-buffer production.
```
