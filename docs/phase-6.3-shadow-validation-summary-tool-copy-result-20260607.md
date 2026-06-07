# Phase 6.3 Shadow Validation Summary Tool Copy Result

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
head reviewed before copy/deploy: 5dccb463124715bdde3e609f2f8fa8087689de3c
message: docs: record phase 6.3 shadow validation reporting tools
```

## 2. New commits before work

```text
new commits after 5dccb463124715bdde3e609f2f8fa8087689de3c: none
```

Reviewed areas:

```text
scripts/shadow_validation_summary.py: read-only reporting tool
answer_runtime_buffer.py/final_submit_service.py: no new runtime changes
config/env/compose: no changes
queue/hybrid activation: none
Redis source-of-truth changes: none
DB migration/schema: none
APK/AAB/keystore/.env/backup/dump/CSV/raw token/PII/raw answer artifacts: none
```

## 3. Operator instruction

Operator requested to continue the next step and update GitHub for review.

Applied scope:

```text
copy/deploy read-only ops tool only
no restart
no env change
no migration
no load-test
no APK touch
no DB/Redis/PgBouncer restart
no queue/hybrid/runtime-buffer production activation
```

## 4. VPS preflight before copy

Timestamp:

```text
PHASE62C_PREFLIGHT_TS=20260607T122825Z
```

Result:

```text
local_health_http=200
public_health_http=200
all app containers=running/healthy
DB=healthy
Redis=PONG/healthy
PgBouncer=healthy
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false effective
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0 effective
session/exam allowlists empty
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
traceback=0
http_500=0
http_503_409=0
answer_save_errors=0
final_submit_errors=0
queue_hybrid_evidence=0
PHASE62C_PREFLIGHT_PASS
```

Note:

```text
runtime_shadow_keys=9 were prior synthetic Phase 6.2e hash-only TTL keys. No broad Redis deletion was performed.
```

## 5. File copied

Copied source file:

```text
scripts/shadow_validation_summary.py
```

VPS destination:

```text
/root/ujian_online/scripts/shadow_validation_summary.py
```

No runtime service file was changed.

## 6. Backup directory

```text
/root/ujian_online_backups/phase-6.3-shadow-summary-tool-20260607T122943Z
```

Previous file state:

```text
NO_PREVIOUS_FILE
```

## 7. Checksums

```text
source: 42fefd4ed23acd95c104da8bbeefa29db95907308089631ed6ef56acde3fab1b  /tmp/shadow_validation_summary.py
post:   42fefd4ed23acd95c104da8bbeefa29db95907308089631ed6ef56acde3fab1b  scripts/shadow_validation_summary.py
```

Validation:

```text
source_sha == post_sha: PASS
```

## 8. Runtime validation method

Because production images do not necessarily mount repo `scripts/` into the API container, the tool was copied into the running API container at `/tmp/shadow_validation_summary.py` for validation only.

Commands validated:

```text
PYTHONPATH=/app python -m py_compile /tmp/shadow_validation_summary.py
PYTHONPATH=/app python /tmp/shadow_validation_summary.py --help
PYTHONPATH=/app python /tmp/shadow_validation_summary.py --limit 10 --fail-on-mismatch
```

Result:

```text
TOOL_HELP_VALIDATE=PASS
TOOL_SUMMARY_VALIDATE=PASS
```

## 9. Read-only summary output

Sanitized summary result:

```json
{
  "checked_answers": 12,
  "checked_sessions": 10,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 0,
  "redis_errors": 0,
  "stale_runtime_sessions": 0,
  "runtime_shadow_keys_count": 9,
  "runtime_answer_buffer_keys_count": 0,
  "answer_queue_keys_count": 0,
  "legacy_answer_queue_keys_count": 0,
  "shadow_keys_without_ttl": 0,
  "sessions_with_shadow": 4,
  "post_final_refresh_meta_count": 4,
  "post_final_refresh_missing_count": 0,
  "ttl_min_seconds": 6588,
  "ttl_max_seconds": 11502,
  "read_only": true
}
```

Redacted sampled session IDs were emitted as masked IDs only.

## 10. Default-OFF / queue-off validation after copy

```text
DEFAULT_OFF_STILL_PASS
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false effective
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0 effective
session/exam allowlists empty
```

Redis/DB gates after tool run:

```text
rejected_connections=0
evicted_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

## 11. Services restarted

```text
none
```

Services explicitly not restarted:

```text
DB
Redis
PgBouncer
Nginx
Celery worker
Celery beat
app-plane APIs
host machine
```

## 12. Safety/forbidden artifact check

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

## 13. Rollback

If the ops tool must be removed:

```bash
rm -f /root/ujian_online/scripts/shadow_validation_summary.py
```

No service restart is required because it is not imported by runtime services.

## 14. Final decision

```text
Phase 6.3 read-only tool copy/deploy: PASS
Tool summary run: PASS
payload_hash_mismatch=0: YES
redis_errors=0: YES
queue/hybrid enabled: NO
runtime buffer production enabled: NO
Phase 6 production: NO
```

Next step:

```text
Use scripts/shadow_validation_summary.py as a read-only post-validation gate for future approved synthetic shadow validations. Do not enable queue/hybrid/runtime-buffer production.
```
