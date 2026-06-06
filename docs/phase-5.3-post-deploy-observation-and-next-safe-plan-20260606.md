# Phase 5.3 Post-Deploy Observation and Next Safe Plan

Date: 2026-06-06

## 1. Scope

This document continues work after the Phase 5.2 controlled VPS source deployment.

Phase 5.3 is **observation and planning only** unless the operator explicitly approves a specific production action.

Allowed in this phase by default:

```text
GitHub review
source/doc review
docs-only planning
preparation of read-only observation commands
```

Not allowed without a separate explicit operator approval:

```text
production deploy or file copy
service restart
.env change
docker-compose.production.yml change
DB migration or manual DDL
Redis/PgBouncer/PostgreSQL restart
queue/hybrid enablement
runtime buffer production routing
runtime buffer shadow enablement
production load-test
APK/AAB build or rollout change
```

## 2. GitHub review result

Compared base and branch head:

```text
base: 91b5599b493166e8bb8ba79a15ce26435b3494ec
head: 91b5599b493166e8bb8ba79a15ce26435b3494ec
commits base..head: 0
```

Result: **no new commits** after the Phase 5.2 deploy result documentation.

Therefore there were no new changed files to review for runtime behavior, production defaults, queue/hybrid activation risk, runtime buffer production dependency, DB migration, APK/AAB artifacts, secrets, tests, docs, or CI workflow changes.

## 3. Phase 5.2 state reviewed

Reviewed:

```text
docs/phase-5.2-vps-deploy-result-20260606.md
```

Important confirmed state from Phase 5.2:

```text
Phase 5.2 source deployment: PASS
source-only/default-OFF deployment completed
no compose overwrite
no .env change
no DB/schema migration
no APK change
no production load-test
API/admin app-plane only was restarted
PostgreSQL/PgBouncer/Redis were not restarted
```

Deployed runtime files:

```text
app/config.py
app/services/answer_sync_service.py
app/services/answer_runtime_buffer.py
app/tasks/answer_processor.py
scripts/runtime_buffer_consistency_check.py
```

Backup reference:

```text
/root/ujian_online_backups/phase-5.2-default-off-20260606T145304Z
```

## 4. Non-negotiable production invariants

Production must remain in direct safe-mode:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
```

Forbidden state:

```text
ANSWER_QUEUE_ENABLED=true
ANSWER_WRITE_MODE=queue
ANSWER_WRITE_MODE=hybrid
ANSWER_QUEUE_PERCENTAGE>0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE>0
Redis runtime buffer as answer source-of-truth
```

Answer/final-submit invariants:

```text
PostgreSQL remains source of record
final submit reads persisted PostgreSQL answers
final submit must not depend on Redis shadow keys
post-commit Redis markers remain best-effort
journal idempotency Redis read failure must fail explicitly with retryable 503
```

Security invariants:

```text
token_validation_bypass=false
APK token/signature validation is not weakened
critical APK/security/final-submit protections stay ON
no raw token/session/PII artifacts are written to Git
```

## 5. Phase 5.3 observation goal

Phase 5.3 should answer these questions with read-only evidence:

1. Are health endpoints stable after Phase 5.2?
2. Are API/admin containers healthy after the app-plane restart?
3. Did direct-write defaults remain unchanged?
4. Are there any startup/import errors from the deployed files?
5. Are answer sync and final submit paths free from new 5xx/409/503 spikes?
6. Are Redis shadow keys still absent while shadow is disabled?
7. Are DB safety gates still clean: no active sessions during observation, no long queries, no idle-in-transaction?
8. Are Redis rejected/evicted counters still zero?
9. Is there any evidence of queue/hybrid/runtime-buffer production routing?
10. Is rollback unnecessary?

## 6. Approval gate for live observation

The commands below are intended to be read-only. Still, because they touch the live VPS, run them only after the operator explicitly approves a Phase 5.3 read-only observation window.

Suggested approval phrase:

```text
approve Phase 5.3 read-only observation
```

Do not restart services as part of observation.

## 7. Observation windows

Recommended windows:

| Window | Purpose | Required action |
|---|---|---|
| T+same day after deploy | confirm no immediate regression | read-only health/config/log aggregate checks |
| T+next quiet window | confirm no delayed startup/log issue | repeat read-only checks |
| before next real exam | confirm safe direct-mode state | run full read-only pre-exam gate |
| after next real exam | verify final-submit/direct-write stability | aggregate-only final-submit and answer-sync review |

Hard block observation expansion if there are live active exam sessions and the command is not purely health/config/log-count read-only.

## 8. Read-only observation checklist

### 8.1 Health and container state

Use explicit compose file path. Do not use a plain `docker compose` command without `-f docker-compose.production.yml`.

```bash
cd /root/ujian_online

curl -fsS http://127.0.0.1/health
curl -k -fsS https://127.0.0.1/health
curl -k -fsS "$PUBLIC_BASE_URL/health"

docker compose -f docker-compose.production.yml ps api api2 api3 api4 api5 api6 api7 api8 api_admin api_admin2

docker compose -f docker-compose.production.yml ps db pgbouncer redis
```

Expected:

```text
health = 200
API/admin app-plane = healthy
DB/PgBouncer/Redis = healthy, no restart requested
```

### 8.2 Effective direct-mode settings

```bash
docker exec -i ujian_online-api-1 python - <<'PY'
from app.config import settings
fields = [
    'answer_write_mode',
    'answer_queue_enabled',
    'answer_queue_percentage',
    'answer_runtime_buffer_shadow_enabled',
    'answer_runtime_buffer_shadow_percentage',
    'answer_runtime_buffer_shadow_ttl_seconds',
    'answer_runtime_buffer_consistency_sample_limit',
    'exam_peak_mode',
    'violation_async_enabled',
    'mobile_apk_primary',
]
for name in fields:
    print(f'{name}={getattr(settings, name)}')
assert settings.answer_write_mode == 'direct'
assert settings.answer_queue_enabled is False
assert int(settings.answer_queue_percentage) == 0
assert settings.answer_runtime_buffer_shadow_enabled is False
assert int(settings.answer_runtime_buffer_shadow_percentage) == 0
PY
```

Expected:

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
answer_runtime_buffer_shadow_enabled=False
answer_runtime_buffer_shadow_percentage=0
```

### 8.3 Source checksum drift check

```bash
cd /root/ujian_online
sha256sum \
  app/config.py \
  app/services/answer_sync_service.py \
  app/services/answer_runtime_buffer.py \
  app/tasks/answer_processor.py \
  scripts/runtime_buffer_consistency_check.py
```

Expected checksums from Phase 5.2:

```text
4e0d54702626cc92f316328b93b6b3efe391c3c4af73701c8c4e2f9519796ec5  app/config.py
6a5d17b34233d30aa5a1040cefc907761718eb0892168963130a4d1e15e45f72  app/services/answer_sync_service.py
f4c218c7731b3613fc1ab45a27496e552aa3cb88d27e7a2ada3b57e607fb0b7e  app/services/answer_runtime_buffer.py
944e9266d84429c96c51d942bf63ee09fef8a89921b5932d32f51fa1cd3c728d  app/tasks/answer_processor.py
e31087dbcad9d117ca0f69e16e651631541a2ac9408d282937c492cb4491d4bd  scripts/runtime_buffer_consistency_check.py
```

Mismatch means source drift and requires investigation before any next phase.

### 8.4 Import and shadow helper validation

```bash
docker exec -i ujian_online-api-1 python - <<'PY'
from app.services.answer_sync_service import AnswerSyncService, _safe_update_session_answers_marker
from app.services.answer_runtime_buffer import (
    answer_payload_hash,
    is_runtime_answer_buffer_shadow_enabled,
    is_runtime_answer_buffer_shadow_enabled_for_session,
    record_runtime_answer_shadow,
)
from app.tasks.answer_processor import process_answer_queue_once
print('imports_ok')
print('hash_len=', len(answer_payload_hash({'question_id': 1, 'answer_text': 'hidden'})))
print('shadow_enabled=', is_runtime_answer_buffer_shadow_enabled())
print('shadow_for_session=', is_runtime_answer_buffer_shadow_enabled_for_session(1, 1, 1))
assert is_runtime_answer_buffer_shadow_enabled() is False
assert is_runtime_answer_buffer_shadow_enabled_for_session(1, 1, 1) is False
PY
```

Expected:

```text
imports_ok
hash_len=64
shadow_enabled=False
shadow_for_session=False
```

### 8.5 DB safety gates, aggregate only

Do not print raw answers, tokens, student names, or PII.

```bash
docker exec -i ujian_online-api-1 python - <<'PY'
import asyncio, json
from datetime import datetime, timezone
from sqlalchemy import select, func, text
from app.database import async_session_read
from app.models.session import ExamSession
from app.models.exam import Exam

async def main():
    now = datetime.now(timezone.utc)
    async with async_session_read() as db:
        out = {
            'active_sessions': (await db.execute(
                select(func.count()).select_from(ExamSession).where(
                    (ExamSession.status.in_(['in_progress', 'active', 'paused']))
                    | (ExamSession.is_paused == True)
                )
            )).scalar_one(),
            'running_exam_windows': (await db.execute(
                select(func.count()).select_from(Exam).where(
                    Exam.is_published == True,
                    Exam.start_time <= now,
                    Exam.end_time >= now,
                )
            )).scalar_one(),
            'long_active_queries_gt_60s': (await db.execute(text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE state='active'
                  AND now()-query_start > interval '60 seconds'
                  AND pid <> pg_backend_pid()
            """))).scalar_one(),
            'idle_in_transaction': (await db.execute(text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE state='idle in transaction'
            """))).scalar_one(),
            'final_submit_or_drain_queries': (await db.execute(text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE state='active'
                  AND (
                    query ILIKE '%final_submit%'
                    OR query ILIKE '%submit%'
                    OR query ILIKE '%answer_queue%'
                    OR query ILIKE '%runtime:answer_queue%'
                  )
                  AND pid <> pg_backend_pid()
            """))).scalar_one(),
        }
    print(json.dumps(out, sort_keys=True))

asyncio.run(main())
PY
```

Expected during quiet observation:

```json
{"active_sessions":0,"final_submit_or_drain_queries":0,"idle_in_transaction":0,"long_active_queries_gt_60s":0,"running_exam_windows":0}
```

If an observation is intentionally run during a real exam, do not require `active_sessions=0`; instead treat it as passive monitoring only and do not run any disruptive command.

### 8.6 Redis safety gates

```bash
docker exec ujian_online-redis-1 redis-cli PING

docker exec ujian_online-redis-1 redis-cli INFO stats | \
  grep -E '^(rejected_connections|evicted_keys):'

docker exec ujian_online-redis-1 redis-cli --scan --pattern 'runtime:answer_shadow:*' | wc -l

docker exec ujian_online-redis-1 redis-cli --scan --pattern 'runtime:answer_queue:*' | wc -l
```

Expected:

```text
PONG
rejected_connections:0
evicted_keys:0
runtime:answer_shadow:* count = 0 while shadow is disabled
runtime:answer_queue:* should not indicate active production routing
```

Do not delete keys during observation.

### 8.7 Runtime buffer consistency checker

With shadow disabled, the checker should not find mismatch. It may show historical sampled sessions but `checked_answers` can be `0` if there are no shadow mirrors.

```bash
docker exec ujian_online-api-1 python /app/scripts/runtime_buffer_consistency_check.py --limit 20
```

Expected with shadow OFF:

```json
{"checked_answers":0,"extra_in_redis":0,"missing_in_redis":0,"payload_hash_mismatch":0,"redis_errors":0,"stale_runtime_sessions":0}
```

Do not use `--include-session-ids` unless an operator explicitly needs numeric session IDs for debugging.

### 8.8 Log aggregate checks

Use aggregate counts first to avoid exposing raw tokens/session data.

```bash
cd /root/ujian_online

docker compose -f docker-compose.production.yml logs --since=30m \
  api api2 api3 api4 api5 api6 api7 api8 api_admin api_admin2 2>/dev/null | \
  egrep -ic 'ERROR|Traceback|ImportError|ModuleNotFoundError|ANSWER-SHADOW|runtime shadow|ANSWER_QUEUE|queue routing|hybrid routing| 503 | 409 '
```

Expected:

```text
0 or known-benign count after manual review
```

If count is non-zero, inspect only a small redacted sample and do not paste raw tokens/session/PII into Git.

### 8.9 Final submit and answer-sync passive indicators

Preferred: aggregate-only logs/metrics and DB counters. Avoid synthetic production load.

Look for:

```text
new final submit 5xx spike
new answer sync 5xx spike
unexpected 409/503 increase
students stuck in in_progress after expected finish
final score/submitted records missing after completed sessions
```

Do not create synthetic sessions or submit test answers on production without explicit operator approval.

## 9. Acceptance criteria for Phase 5.3 observation

Phase 5.3 can be marked PASS if all are true:

```text
health endpoints remain 200
API/admin app-plane remains healthy
DB/PgBouncer/Redis remain healthy and were not restarted
production defaults remain direct/queue-off/shadow-off
source checksums match Phase 5.2 post-copy checksums
imports_ok remains true
runtime shadow key count remains 0 while shadow is disabled
consistency checker has zero mismatch/error fields
no new import/startup errors
no queue/hybrid/runtime-buffer production routing evidence
no final-submit regression evidence
no answer-sync 5xx/409/503 spike attributable to Phase 5.2
no rollback trigger fires
```

## 10. Rollback triggers

Rollback should be considered only with operator approval if any of these occur and are attributable to Phase 5.2:

```text
health endpoint failures persist across repeated checks
API/admin containers cannot stay healthy
import/startup errors from deployed files
queue/hybrid/shadow unexpectedly enabled
Redis shadow keys appear while shadow flag is false
answer-sync direct path shows sustained new 5xx spike
final-submit failures increase or final submit cannot read persisted answers
DB long active queries or idle-in-transaction persist and correlate with deployed code
consistency checker reports redis_errors or hash mismatch while shadow is expected to be off/clean
```

Rollback scope must remain file-based and app-plane only:

```text
restore files from /root/ujian_online_backups/phase-5.2-default-off-20260606T145304Z
restart only API/admin app-plane
no DB/Redis/PgBouncer restart
no migration
no compose overwrite
```

## 11. Next safe development plan

### 11.1 Phase 5.3A — read-only observation

Status: ready for operator approval.

Action:

```text
Run the read-only checklist in a quiet window.
Capture aggregate-only results.
Do not change production state.
```

Deliverable:

```text
docs/phase-5.3-post-deploy-observation-result-YYYYMMDD.md
```

### 11.2 Phase 5.3B — source-only observability helper, optional

Only if repeated manual checks are error-prone, add a source-only read-only helper script that prints aggregate checks without raw tokens/PII.

Constraints:

```text
script must be read-only
script must not mutate Redis/DB
script must not include secrets
script must default to no session IDs
script must not run automatically in production
script deployment requires separate approval
```

### 11.3 Phase 5.4 — direct-mode hardening backlog

Possible source-only improvements, not production activation:

```text
improve aggregate metrics for answer-sync retryable 503
add safer log tags for direct-mode writes without answer content
add tests for post-commit Redis marker best-effort behavior
add tests proving final submit ignores Redis shadow data
add documentation for rollback drill and exam-day observation
```

### 11.4 Phase 6 shadow readiness, still blocked for live activation

Do not enable shadow on production yet.

Before even a small shadow trial:

```text
explicit operator approval
quiet window
active sessions = 0 unless the approval says otherwise
ANSWER_WRITE_MODE remains direct
ANSWER_QUEUE_ENABLED remains false
ANSWER_QUEUE_PERCENTAGE remains 0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED may only be true for the approved trial
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE must be tightly bounded
checker must show 0 mismatch
rollback to shadow-off must be tested
```

### 11.5 Phase 6 queue/hybrid/runtime-buffer production, still NO-GO

Production queue/hybrid/runtime-buffer source-of-truth remains blocked until all are solved:

```text
Redis maxmemory-policy allkeys-lru replaced with a safe policy for answer durability
separate answer flush worker/concurrency strategy proven outside production
deadletter and age metrics exist
forced final-submit flush proven under staging/shadow/canary
runtime buffer consistency checker has 0-mismatch evidence
rollback to direct mode is documented and tested
operator explicitly approves canary
```

## 12. Current decision

Phase 5.3 planning: **READY**.

No production action has been performed in this Phase 5.3 planning step.

Recommended next operator decision:

```text
approve Phase 5.3 read-only observation
```

Until then:

```text
keep direct safe-mode
keep queue/hybrid OFF
keep runtime buffer shadow OFF
keep APK flow unchanged
```
