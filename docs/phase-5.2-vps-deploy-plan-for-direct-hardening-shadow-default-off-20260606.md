# Phase 5.2 VPS Deploy Plan — Direct Hardening + Phase 6 Shadow Default-OFF

Date: 2026-06-06  
Repository: `kuker24/Ujianonline`  
Branch: `review/sanitized-root-20260531-115153`  
Reviewed source head before this document: `dbf563292e8144fff564f837473b42b5fa07b723`  
Previous review baseline: `298a46848deff03ff54b754b5498d7d8a8190321`

This is a deployment review and operator runbook only. It does not approve queue, hybrid, Redis runtime-buffer production routing, production load testing, APK changes, DB migration, Redis policy change, or unattended production rollout.

---

## 1. Latest GitHub head reviewed

GitHub compare result:

```text
base: dbf563292e8144fff564f837473b42b5fa07b723
head: review/sanitized-root-20260531-115153
status: identical
ahead_by: 0
behind_by: 0
new commits: 0
```

No new source commits existed after `dbf563292e8144fff564f837473b42b5fa07b723` at the time of this review. This document, once committed, will become a docs-only commit and must not be interpreted as runtime activation.

---

## 2. Source patch safety review

### 2.1 Runtime mode and defaults

Reviewed behavior remains default-safe:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS=14400
ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT=100
```

The reviewed source keeps PostgreSQL as the source of record. Redis shadow mode is separate from queue/hybrid routing and is disabled by default. Queue and hybrid routing remain blocked for production.

### 2.2 Direct answer hardening

Phase 5.1 hardening is safe to stage as source-only/default-OFF because:

- Single-answer writes still commit to PostgreSQL on the direct path before non-critical marker/shadow work.
- `_safe_update_session_answers_marker()` converts Redis marker update failures into debug-level best-effort skips after durable DB work.
- Batch autosave and journal post-commit marker updates are best-effort.
- Journal initial idempotency Redis read/open failures return explicit `503` with `Retry-After: 1`; they no longer silently classify unknown event IDs as new.
- Public endpoint response contracts remain unchanged for normal successful direct writes.

### 2.3 Phase 6 shadow readiness

Phase 6 shadow readiness is source-ready only as default-OFF partial readiness:

- Shadow stores deterministic answer payload hashes and metadata counters only.
- Shadow does not store raw answer text as Redis source-of-truth data.
- Shadow failures are best-effort and must not affect student-facing answer responses.
- Final submit remains PostgreSQL-based and must not depend on Redis shadow keys.
- Consistency checker is read-only and emits JSON summary counters only.

### 2.4 Remaining blockers

The following production blockers remain unchanged:

- Redis live policy `allkeys-lru` is unsafe for answer-buffer source-of-truth.
- Celery worker live mode `--pool=solo` / concurrency 1 is not sufficient for answer flush production.
- Final-submit forced-flush behavior is still unproven under production traffic.
- Live VPS source is not guaranteed to match GitHub head; deployment must be checksum/backup based.
- No production load-test is permitted for this phase.

---

## 3. Files reviewed in the source patch

Changed files from `298a46848deff03ff54b754b5498d7d8a8190321` to `dbf563292e8144fff564f837473b42b5fa07b723`:

```text
.env.example
app/config.py
app/services/answer_runtime_buffer.py
app/services/answer_sync_service.py
app/tasks/answer_processor.py
docker-compose.production.yml
docs/phase-5.1-direct-hardening-and-phase-6-shadow-readiness-20260606.md
scripts/runtime_buffer_consistency_check.py
tests/test_answer_runtime_buffer_consistency.py
tests/test_answer_runtime_buffer_shadow.py
tests/test_answer_sync_service_routing.py
tests/test_exam_write_integrity_guards.py
tests/test_production_readiness_defaults.py
```

---

## 4. Exact files to deploy to VPS

VPS is not a normal git checkout. Runtime uses host files bind-mounted into containers, especially:

```text
/root/ujian_online/app -> /app/app
```

Deploy by explicit file copy only, after checksum and backup.

### 4.1 Required runtime source files

Copy these GitHub-head files to the corresponding VPS paths:

```text
app/config.py
app/services/answer_sync_service.py
app/services/answer_runtime_buffer.py
app/tasks/answer_processor.py
```

Target examples:

```text
/root/ujian_online/app/config.py
/root/ujian_online/app/services/answer_sync_service.py
/root/ujian_online/app/services/answer_runtime_buffer.py
/root/ujian_online/app/tasks/answer_processor.py
```

### 4.2 Utility file

Copy this as a utility/read-only validation script:

```text
scripts/runtime_buffer_consistency_check.py
```

Target example:

```text
/root/ujian_online/scripts/runtime_buffer_consistency_check.py
```

Operational note: current production compose mounts `./app` but not necessarily `./scripts`. If the script must run inside an API container without rebuilding the image, either copy it into one API container with `docker cp` for validation only, or run it through an operator-approved host/container method. Do not modify compose just to mount scripts unless separately reviewed.

### 4.3 Compose file handling

`docker-compose.production.yml` was changed upstream to expose safe default environment variables for shadow mode. Because the live VPS compose file is known to differ from GitHub, do not blindly overwrite it.

Default plan:

```text
Do not deploy docker-compose.production.yml in this first Phase 5.2 source hardening deployment.
```

Reason: the code-level defaults already keep shadow OFF. Compose replacement risks unrelated live topology/config drift. Deploy compose only in a separate operator-approved step after a full host-vs-GitHub diff review and `docker compose config` validation.

---

## 5. Files that must NOT be deployed

Do not deploy or copy these to production as part of Phase 5.2:

```text
.env
.env.* with real secrets
.env.example as live runtime config
APK files
AAB files
keystore/JKS/key.properties/local.properties
DB dump / SQL dump / sqlite/db files
backup archives
session CSV / summary JSON / raw export artifacts
raw tokens / full build tokens / session tokens / PII artifacts
tests/*
docs/* except optional operator documentation outside runtime
```

Do not change APK 1.0.8 in this phase.

---

## 6. VPS preflight gates

All gates must pass before copying any file.

### 6.1 Scheduling and traffic gates

Required state:

```text
active exam windows: 0
in-progress/active/paused sessions: 0
final-submit/drain queries: 0
long active DB queries >60s: 0
idle-in-transaction: 0
```

Suggested SQL checks, run read-only through the approved production DB access path:

```sql
-- Active exam windows now
SELECT count(*) AS active_exam_windows
FROM exams
WHERE is_published = true
  AND COALESCE(is_deleted, false) = false
  AND now() BETWEEN start_time AND end_time;

-- Active student sessions
SELECT status, count(*) AS session_count
FROM exam_sessions
WHERE status IN ('in_progress', 'active')
   OR COALESCE(is_paused, false) = true
GROUP BY status
ORDER BY status;

-- Long active DB queries
SELECT count(*) AS long_active_queries
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '60 seconds'
  AND pid <> pg_backend_pid();

-- Idle in transaction
SELECT count(*) AS idle_in_transaction
FROM pg_stat_activity
WHERE state = 'idle in transaction';

-- Final-submit / answer-drain related active queries
SELECT count(*) AS final_submit_or_drain_queries
FROM pg_stat_activity
WHERE state = 'active'
  AND (
    query ILIKE '%final_submit%'
    OR query ILIKE '%submit%'
    OR query ILIKE '%answer_queue%'
    OR query ILIKE '%runtime:answer_queue%'
  )
  AND pid <> pg_backend_pid();
```

Hard block if any gate is non-zero.

### 6.2 Service health gates

Required:

```text
public /health: 200
local /health: 200
PostgreSQL accepting connections
PgBouncer accepting connections
Redis PING: PONG
disk /: acceptable, no sudden pressure
memory: enough headroom for rolling app-plane restart
```

Suggested commands:

```bash
cd /root/ujian_online
curl -fsS http://127.0.0.1:8000/health
curl -fsS "$PUBLIC_BASE_URL/health"
docker compose ps
docker compose exec -T redis redis-cli PING
docker compose exec -T db pg_isready -U examuser -d exam_system
df -h /
free -m
```

Do not restart DB, Redis, or PgBouncer.

---

## 7. Backup and checksum plan

Use a timestamped backup directory and capture checksums before any copy.

```bash
cd /root/ujian_online
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/root/ujian_online_backups/phase-5.2-default-off-$TS"
mkdir -p "$BACKUP_DIR/app/services" "$BACKUP_DIR/app/tasks" "$BACKUP_DIR/scripts"

sha256sum \
  app/config.py \
  app/services/answer_sync_service.py \
  app/services/answer_runtime_buffer.py \
  app/tasks/answer_processor.py \
  2>/dev/null | tee "$BACKUP_DIR/predeploy.sha256"

cp -a app/config.py "$BACKUP_DIR/app/config.py"
cp -a app/services/answer_sync_service.py "$BACKUP_DIR/app/services/answer_sync_service.py"
cp -a app/services/answer_runtime_buffer.py "$BACKUP_DIR/app/services/answer_runtime_buffer.py"
cp -a app/tasks/answer_processor.py "$BACKUP_DIR/app/tasks/answer_processor.py"

if [ -f scripts/runtime_buffer_consistency_check.py ]; then
  sha256sum scripts/runtime_buffer_consistency_check.py | tee -a "$BACKUP_DIR/predeploy.sha256"
  cp -a scripts/runtime_buffer_consistency_check.py "$BACKUP_DIR/scripts/runtime_buffer_consistency_check.py"
fi
```

After copying new files, capture post-copy checksums:

```bash
sha256sum \
  app/config.py \
  app/services/answer_sync_service.py \
  app/services/answer_runtime_buffer.py \
  app/tasks/answer_processor.py \
  scripts/runtime_buffer_consistency_check.py \
  2>/dev/null | tee "$BACKUP_DIR/postcopy.sha256"
```

Keep the backup directory off web-served paths. Do not commit backups to GitHub.

---

## 8. Deployment plan

### 8.1 Operator approval

Proceed only with explicit operator approval and a safe inter-session window. Existing policy still applies:

```text
30-minute gap: warning, not hard block
<5-minute next exam gap: hard block
active sessions >0: hard block
running exam window: hard block
```

### 8.2 Copy only required files

Copy only the files listed in section 4.1 and 4.2. Do not change `.env`.

Required production mode after copy:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
```

Forbidden environment changes:

```text
ANSWER_QUEUE_ENABLED=true
ANSWER_WRITE_MODE=queue
ANSWER_WRITE_MODE=hybrid
ANSWER_QUEUE_PERCENTAGE>0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE>0
```

### 8.3 No migration

No DB schema change is part of this plan. Do not run Alembic migration or any manual DDL.

### 8.4 Restart scope

Because `/root/ujian_online/app` is bind-mounted into `/app/app`, source file replacement still requires app process restart to reload Python modules.

Allowed restart scope:

```text
API/admin app-plane only
```

Forbidden restart scope:

```text
PostgreSQL
PgBouncer
Redis
full host reboot
full stack restart including data services
```

Preferred sequence:

```bash
cd /root/ujian_online

# Restart API replicas gradually. Adjust service names to live compose output.
docker compose restart api
curl -fsS http://127.0.0.1:8000/health

docker compose restart api2
curl -fsS http://127.0.0.1:8000/health

docker compose restart api3
curl -fsS http://127.0.0.1:8000/health

docker compose restart api4
curl -fsS http://127.0.0.1:8000/health

docker compose restart api5
curl -fsS http://127.0.0.1:8000/health

docker compose restart api6
curl -fsS http://127.0.0.1:8000/health

# Include only if these services exist/live and are part of app-plane.
docker compose restart api7 api8 api_admin api_admin2
curl -fsS http://127.0.0.1:8000/health
```

If the live deployment uses an app-plane refresh/restart button, prefer that only if it is known to restart API/admin containers without restarting DB, Redis, or PgBouncer.

---

## 9. Post-deploy validation

### 9.1 Health and process validation

```bash
cd /root/ujian_online
curl -fsS http://127.0.0.1:8000/health
curl -fsS "$PUBLIC_BASE_URL/health"
docker compose ps
```

Expected:

```text
health: 200
API/admin containers: healthy/running
DB/PgBouncer/Redis: not restarted by this deployment
```

### 9.2 Runtime defaults validation

Check the effective app settings inside one API container:

```bash
docker compose exec -T api python - <<'PY'
from app.config import settings
print('ANSWER_WRITE_MODE=', settings.answer_write_mode)
print('ANSWER_QUEUE_ENABLED=', settings.answer_queue_enabled)
print('ANSWER_QUEUE_PERCENTAGE=', settings.answer_queue_percentage)
print('ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=', settings.answer_runtime_buffer_shadow_enabled)
print('ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=', settings.answer_runtime_buffer_shadow_percentage)
print('ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS=', settings.answer_runtime_buffer_shadow_ttl_seconds)
print('ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT=', settings.answer_runtime_buffer_consistency_sample_limit)
PY
```

Expected:

```text
ANSWER_WRITE_MODE= direct
ANSWER_QUEUE_ENABLED= False
ANSWER_QUEUE_PERCENTAGE= 0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED= False
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE= 0
ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS= 14400
ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT= 100
```

### 9.3 Source import validation

```bash
docker compose exec -T api python - <<'PY'
from app.services.answer_sync_service import AnswerSyncService, _safe_update_session_answers_marker
from app.services.answer_runtime_buffer import (
    answer_payload_hash,
    is_runtime_answer_buffer_shadow_enabled,
    is_runtime_answer_buffer_shadow_enabled_for_session,
    record_runtime_answer_shadow,
)
from app.tasks.answer_processor import process_answer_queue_once
print('imports_ok')
print('shadow_enabled=', is_runtime_answer_buffer_shadow_enabled())
print('shadow_for_session=', is_runtime_answer_buffer_shadow_enabled_for_session(1, 1, 1))
PY
```

Expected:

```text
imports_ok
shadow_enabled= False
shadow_for_session= False
```

### 9.4 Consistency checker validation

If the script is available inside the API container:

```bash
docker compose exec -T api python /app/scripts/runtime_buffer_consistency_check.py --help
```

If scripts are not mounted, validate the parser by copying the script into one API container for temporary validation:

```bash
CID="$(docker compose ps -q api | head -n 1)"
docker cp scripts/runtime_buffer_consistency_check.py "$CID:/tmp/runtime_buffer_consistency_check.py"
docker compose exec -T api python /tmp/runtime_buffer_consistency_check.py --help
```

Optional read-only checker run only when there are no active sessions/windows and the operator approves the DB/Redis read:

```bash
docker compose exec -T api python /tmp/runtime_buffer_consistency_check.py --limit 20
```

Expected when shadow is OFF and no shadow keys exist:

```json
{"checked_answers":0,"checked_sessions":0,"extra_in_redis":0,"missing_in_redis":0,"payload_hash_mismatch":0,"redis_errors":0,"stale_runtime_sessions":0}
```

A non-zero `checked_sessions` is acceptable if the sample includes historical submitted/completed sessions. With shadow OFF and no shadow keys, `checked_answers` can remain `0` because the checker skips answer comparison when no mirror exists.

### 9.5 Final-submit safety validation

Do not run production load tests. Use only passive validation or a single controlled non-live test account/session if the operator explicitly approves.

Expected invariants:

```text
final submit reads persisted PostgreSQL answers
final submit does not depend on Redis shadow keys
queue/hybrid remains off
student answer success responses remain direct-mode
```

### 9.6 Log validation

Review recent app logs for the deployment window:

```bash
docker compose logs --since=20m api api2 api3 api4 api5 api6 api_admin api_admin2 2>/dev/null | \
  egrep -i 'ERROR|Traceback|SUBMIT-ANSWER|AUTO-SAVE-BATCH|ANSWER-JOURNAL|ANSWER-SHADOW|runtime shadow|503|409' | tail -n 200
```

Acceptable observations:

```text
No import errors
No startup errors
No unexpected 5xx spike
No queue/hybrid routing logs
No Redis shadow activation logs while shadow flag is false
```

---

## 10. Rollback plan

Rollback is file-based.

```bash
cd /root/ujian_online
# Use the actual BACKUP_DIR created in section 7.
cp -a "$BACKUP_DIR/app/config.py" app/config.py
cp -a "$BACKUP_DIR/app/services/answer_sync_service.py" app/services/answer_sync_service.py
cp -a "$BACKUP_DIR/app/services/answer_runtime_buffer.py" app/services/answer_runtime_buffer.py
cp -a "$BACKUP_DIR/app/tasks/answer_processor.py" app/tasks/answer_processor.py

if [ -f "$BACKUP_DIR/scripts/runtime_buffer_consistency_check.py" ]; then
  cp -a "$BACKUP_DIR/scripts/runtime_buffer_consistency_check.py" scripts/runtime_buffer_consistency_check.py
fi

sha256sum \
  app/config.py \
  app/services/answer_sync_service.py \
  app/services/answer_runtime_buffer.py \
  app/tasks/answer_processor.py \
  scripts/runtime_buffer_consistency_check.py \
  2>/dev/null | tee "$BACKUP_DIR/rollback.sha256"
```

Then restart only app-plane services, using the same rolling sequence as deployment. Validate:

```bash
curl -fsS http://127.0.0.1:8000/health
docker compose ps
```

Do not rollback by changing `.env` unless a separate operator-reviewed env change was mistakenly made.

---

## 11. Risk register

| Risk | Status | Impact | Control |
|---|---:|---|---|
| Live VPS source mismatch vs GitHub | Open | Wrong overwrite can regress live fixes | File-level backup/checksum; copy only approved files; no blind git pull |
| Live compose mismatch vs GitHub | Open | Compose overwrite can change runtime topology/env | Do not deploy compose in first Phase 5.2 pass |
| Redis policy `allkeys-lru` | Open blocker | Unsafe for answer source-of-truth | Do not enable queue/hybrid/runtime-buffer production |
| Worker `--pool=solo` concurrency 1 | Open blocker | Insufficient answer flush capacity | Do not enable queue/hybrid; no production buffer source-of-truth |
| Final-submit forced flush unproven | Open blocker | Scoring risk if async path enabled | Keep final submit PostgreSQL/direct; no queue/hybrid activation |
| Shadow checker script not bind-mounted | Known ops gap | Validation may require temporary `docker cp` | Treat script as utility; no compose change without separate review |
| Journal Redis idempotency 503 behavior | Intended change | Client may retry on Redis read failure | Explicit `Retry-After: 1`; acceptable safer behavior than duplicate ambiguity |

---

## 12. Required checks if code changes again

If any code changes are made after this document, rerun at minimum:

```bash
python -m compileall app
pytest tests/test_production_readiness_defaults.py -q
pytest tests/test_answer_sync_service_routing.py -q
pytest tests/test_answer_runtime_buffer.py -q
pytest tests/test_final_submit_service.py -q
pytest tests/test_exam_write_integrity_guards.py -q
pytest tests/test_answer_runtime_buffer_shadow.py -q
pytest tests/test_answer_runtime_buffer_consistency.py -q
python -m py_compile scripts/runtime_buffer_consistency_check.py
python scripts/runtime_buffer_consistency_check.py --help
git diff --check
```

Forbidden artifact check:

```bash
find . -type f \( \
  -name '*.apk' -o -name '*.aab' -o -name '*.jks' -o -name '*.keystore' -o \
  -name 'key.properties' -o -name 'local.properties' -o -name '.env' -o \
  -name '*.dump' -o -name '*.sql' -o -name '*.sqlite' -o -name '*.db' -o \
  -name '*.csv' -o -name '*summary*.json' \
\) -print
```

Expected output for new tracked artifacts: none.

---

## 13. Final decision

```text
Safe to deploy source hardening: YES, only as controlled default-OFF source deployment after all preflight gates pass.
Safe to deploy immediately without operator approval: NO.
Safe to enable Phase 6 shadow: NO, requires separate approval and post-deploy observation first.
Safe to enable queue/hybrid: NO.
Safe to start Phase 6 production runtime-buffer source-of-truth: NO.
Safe to run production load-test: NO.
Safe to touch APK 1.0.8: NO, not part of this phase.
```

Recommended next step: operator-reviewed file/checksum deployment of Phase 5.1 direct hardening only, preserving production direct safe-mode and leaving all async/Redis production routing disabled.
