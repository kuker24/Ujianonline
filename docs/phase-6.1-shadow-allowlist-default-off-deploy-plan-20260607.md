# Phase 6.1 Shadow Allowlist Guard Default-OFF Deploy Plan

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
base requested: 31d054028bb79bf57e08cb59a9059826f235b81f
reviewed remote head: 31d054028bb79bf57e08cb59a9059826f235b81f
message: docs: add phase 6.0 shadow trial plan
```

New commits after requested base:

```text
none
```

Decision:

```text
No unexpected production activation was found.
No unexpected forbidden artifact was found.
No DB migration/schema change is part of this plan.
```

## 2. Scope of this plan

This is a deploy plan only for the Phase 6.0 runtime answer buffer shadow allowlist source guard.

Allowed by this plan after explicit operator approval:

```text
Deploy the source guard default-OFF.
Keep production behavior unchanged.
Restart only app-plane containers if deploy proceeds.
```

Not allowed by this plan:

```text
Enable shadow trial.
Set ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true.
Set ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS.
Set ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS.
Enable queue.
Enable hybrid.
Set ANSWER_WRITE_MODE=queue or hybrid.
Set ANSWER_QUEUE_PERCENTAGE > 0.
Make Redis source-of-truth.
Make final submit depend on Redis.
Run production load-test.
Touch APK/AAB/keystore.
Run DB migration/schema change.
Restart DB, Redis, PgBouncer, or Nginx.
Blindly overwrite live docker-compose.production.yml.
```

Required approval text for this source-only deploy:

```text
approve deploy Phase 6.0 shadow allowlist guard default-off
```

## 3. Source review summary

Reviewed files:

```text
app/config.py
app/services/answer_runtime_buffer.py
app/services/answer_sync_service.py
app/services/final_submit_service.py
docker-compose.production.yml
.env.example
tests/test_answer_runtime_buffer_shadow.py
tests/test_answer_runtime_buffer_consistency.py
tests/test_production_readiness_defaults.py
tests/test_answer_sync_service_routing.py
docs/phase-6.0-shadow-trial-plan-20260607.md
```

### 3.1 Config defaults

`app/config.py` defines:

```text
answer_runtime_buffer_shadow_enabled: default false
answer_runtime_buffer_shadow_percentage: default 0
answer_runtime_buffer_shadow_session_ids: default empty string
answer_runtime_buffer_shadow_exam_ids: default empty string
answer_runtime_buffer_shadow_ttl_seconds: default 14400
```

Expected default behavior:

```text
Shadow remains OFF.
Empty allowlist means no scoped shadow write.
Percentage 0 means no percentage-based shadow write.
```

### 3.2 Runtime buffer allowlist guard

`app/services/answer_runtime_buffer.py` confirms:

```text
_parse_positive_int_allowlist(): parses comma-separated IDs safely.
Invalid values are ignored.
Empty values produce an empty set.
Negative and zero values are ignored.
runtime_answer_shadow_session_allowlist(): returns parsed session IDs.
runtime_answer_shadow_exam_allowlist(): returns parsed exam IDs.
```

Shadow selection confirms:

```text
Master flag false => no shadow.
Master flag true + empty allowlists + percentage 0 => no shadow.
Master flag true + session allowlist match => shadow may run.
Master flag true + exam allowlist match => shadow may run.
Master flag true + percentage gate match => shadow may run.
```

Hash-only behavior confirms:

```text
Shadow value stores payload_hash only, not raw answer content.
Shadow meta stores session_id, exam_id, answer_count, updated_at.
No raw answer text is stored in Redis shadow keys.
Shadow write failure is best-effort and returns 0.
Shadow write failure does not raise to the answer path.
```

### 3.3 Answer sync path

`app/services/answer_sync_service.py` confirms:

```text
Direct database write remains source-of-truth.
Direct write/commit remains in the normal answer path.
record_runtime_answer_shadow() is called only after normal write flow.
Shadow is optional/best-effort.
No new queue/hybrid activation is introduced by the allowlist guard patch.
```

The code still contains existing guarded queue/hybrid branches, but the production defaults and live env keep them OFF:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
```

### 3.4 Final submit path

`app/services/final_submit_service.py` confirms:

```text
No reference to runtime:answer_shadow.
No reference to shadow_session_answers_key.
No reference to record_runtime_answer_shadow.
No use of answer_payload_hash.
```

Final submit remains PostgreSQL/direct-based and must not depend on Redis shadow.

### 3.5 Compose source review

`docker-compose.production.yml` in GitHub source includes placeholders:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=${ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED:-false}
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=${ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE:-0}
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=${ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS:-}
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=${ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS:-}
```

Important:

```text
This plan must not deploy docker-compose.production.yml blindly.
The VPS live compose has known drift from GitHub.
Any compose/env change requires a separate diff review and explicit operator approval.
```

For this default-OFF guard deploy, compose/env changes are not required.

## 4. Source tests

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
compileall app: PASS
tests/test_answer_runtime_buffer_shadow.py: 9 passed
tests/test_answer_runtime_buffer_consistency.py: 3 passed
tests/test_production_readiness_defaults.py: 7 passed
tests/test_answer_sync_service_routing.py: 25 passed
runtime_buffer_consistency_check.py py_compile: PASS
runtime_buffer_consistency_check.py --help: PASS
git diff --check: PASS
```

## 5. VPS read-only readiness status

Read-only check timestamp:

```text
20260607T035616Z
```

Health:

```text
local /health: 200
public /health: 200
DB: accepting connections
PgBouncer: accepting connections
Redis: PONG
```

Effective env/settings inside current live `api` container:

```text
ANSWER_WRITE_MODE=direct | settings.answer_write_mode=direct
ANSWER_QUEUE_ENABLED=false | settings.answer_queue_enabled=False
ANSWER_QUEUE_PERCENTAGE=0 | settings.answer_queue_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=<unset> | settings.answer_runtime_buffer_shadow_enabled=False
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=<unset> | settings.answer_runtime_buffer_shadow_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=<unset> | settings.answer_runtime_buffer_shadow_session_ids=<missing>
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=<unset> | settings.answer_runtime_buffer_shadow_exam_ids=<missing>
EXAM_PEAK_MODE=true | settings.exam_peak_mode=True
VIOLATION_ASYNC_ENABLED=true | settings.violation_async_enabled=True
ADMIN_MONITORING_DETAIL_LEVEL=summary | settings.admin_monitoring_detail_level=summary
MOBILE_APK_PRIMARY=true | settings.mobile_apk_primary=True
```

Interpretation:

```text
Direct safe-mode is active.
Queue/hybrid is OFF.
Shadow is OFF.
Live source has not yet received the new session/exam allowlist settings, which is expected before Phase 6.1 source guard deploy.
Unset allowlist env means default empty after source guard deploy.
```

DB gates:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Redis status:

```text
used_memory_human=10.05M
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

Celery status:

```text
celery_worker: running/healthy
celery_beat: running/healthy
pool implementation: celery.concurrency.solo:TaskPool
max-concurrency: 1
prefetch_count: 4
```

## 6. Files proposed for default-OFF deploy

Runtime source files proposed:

```text
app/config.py
app/services/answer_runtime_buffer.py
```

Rationale:

```text
app/config.py adds default-empty settings for allowlist guards.
app/services/answer_runtime_buffer.py adds safe parsing and allowlist gating.
Both are required before any later allowlisted shadow trial can be scoped safely.
Both remain inactive while ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED is false/unset.
```

Optional file for later validation only, not required by this deploy because it is unchanged from the already deployed/default-off Phase 5.2 source set:

```text
scripts/runtime_buffer_consistency_check.py
```

Do not include unless an operator wants the VPS checker script refreshed in the same maintenance window and checksum proves source drift requires it.

Files not required because unchanged for this guard deploy:

```text
app/services/answer_sync_service.py
app/services/final_submit_service.py
```

## 7. Files explicitly not to deploy

Do not deploy:

```text
docker-compose.production.yml
.env.example
tests/
docs/
APK/AAB files
keystore/JKS/key.properties/local.properties
.env or .env.*
DB dump/backup/sqlite/sql artifacts
CSV/session artifacts
summary JSON artifacts
```

Reason:

```text
This is a runtime source guard deploy only.
Tests/docs/env templates are GitHub documentation/verification artifacts, not production runtime files.
Compose has known drift and must not be overwritten blindly.
```

## 8. Why docker-compose.production.yml must not be blindly deployed

Known condition:

```text
VPS live docker-compose.production.yml differs from GitHub source.
The live topology/env may contain production-specific adjustments.
```

Risk of blind overwrite:

```text
Could change service topology.
Could change resource limits or worker command.
Could accidentally alter published ports or health checks.
Could change queue/shadow/runtime env wiring.
Could restart/recreate services beyond intended app-plane scope.
```

Plan decision:

```text
Do not copy docker-compose.production.yml for Phase 6.1.
Do not change live .env for Phase 6.1.
Allowlist env remains unset/empty.
Guard code remains default-OFF.
```

## 9. Backup and checksum plan for later approved deploy

Before copying any runtime file:

```bash
TS=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR=/root/ujian_online_backups/phase-6.1-shadow-allowlist-default-off-$TS
mkdir -p "$BACKUP_DIR/app/config" "$BACKUP_DIR/app/services"
cp -a /root/ujian_online/app/config.py "$BACKUP_DIR/app/config.py"
cp -a /root/ujian_online/app/services/answer_runtime_buffer.py "$BACKUP_DIR/app/services/answer_runtime_buffer.py"
sha256sum /root/ujian_online/app/config.py /root/ujian_online/app/services/answer_runtime_buffer.py > "$BACKUP_DIR/pre.sha256"
```

Upload new files to `/tmp` first, then verify source checksums before install:

```bash
sha256sum /tmp/config.py /tmp/answer_runtime_buffer.py
```

Install with ownership/mode preservation target:

```bash
install -o ubuntu -g ubuntu -m 0644 /tmp/config.py /root/ujian_online/app/config.py
install -o ubuntu -g ubuntu -m 0644 /tmp/answer_runtime_buffer.py /root/ujian_online/app/services/answer_runtime_buffer.py
```

Post-copy checksum:

```bash
sha256sum /root/ujian_online/app/config.py /root/ujian_online/app/services/answer_runtime_buffer.py
```

Compile in container:

```bash
docker compose -f docker-compose.production.yml exec -T api python - <<'PY'
import py_compile
py_compile.compile('/app/app/config.py', doraise=True)
py_compile.compile('/app/app/services/answer_runtime_buffer.py', doraise=True)
print('PY_COMPILE=PASS')
PY
```

Rollback if needed:

```bash
cp -a "$BACKUP_DIR/app/config.py" /root/ujian_online/app/config.py
cp -a "$BACKUP_DIR/app/services/answer_runtime_buffer.py" /root/ujian_online/app/services/answer_runtime_buffer.py
```

Then app-plane-only rolling restart.

## 10. Preflight gates for later approved deploy

Required before deploy:

```text
operator approval text present
local /health=200
public /health=200
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
DB healthy
PgBouncer healthy
Redis PING=PONG
Redis rejected_connections=0
Redis evicted_keys=0
runtime_shadow_keys=0
answer_queue_keys=0
```

If any gate fails:

```text
Do not deploy.
Investigate first.
```

## 11. App-plane-only restart plan

Restart only application containers, one at a time:

```text
api_admin
api_admin2
api
api2
api3
api4
api5
api6
api7
api8
```

For each container:

```bash
docker compose -f docker-compose.production.yml restart <container_service>
docker compose -f docker-compose.production.yml ps <container_service>
curl -fsS http://127.0.0.1/health
```

Do not restart:

```text
db
redis
pgbouncer
nginx
celery_worker
celery_beat
prometheus
grafana
```

Celery restart is not required because this guard affects answer request runtime source and does not activate queue/hybrid/shadow processing.

## 12. Post-deploy validation

Immediately after deploy/restart:

```text
local /health=200
public /health=200
all app-plane containers healthy
DB/PgBouncer/Redis stayed up
DB/PgBouncer/Redis StartedAt unchanged
```

Effective env/settings expected after source guard deploy:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=<unset or false>
settings.answer_runtime_buffer_shadow_enabled=False
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=<unset or 0>
settings.answer_runtime_buffer_shadow_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=<unset or empty>
settings.answer_runtime_buffer_shadow_session_ids=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=<unset or empty>
settings.answer_runtime_buffer_shadow_exam_ids=
```

Redis/key checks expected:

```text
runtime_shadow_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
rejected_connections=0
evicted_keys=0
```

Behavior checks:

```text
Normal answer save unaffected.
Final submit unaffected.
No queue/hybrid evidence.
No runtime shadow evidence because shadow remains disabled.
No HTTP 500/503 burst.
No ConnectionDoesNotExistError/BrokenPipe cluster.
```

Optional code marker checks from container:

```text
settings has answer_runtime_buffer_shadow_session_ids
settings has answer_runtime_buffer_shadow_exam_ids
runtime buffer has runtime_answer_shadow_session_allowlist
runtime buffer has runtime_answer_shadow_exam_allowlist
runtime buffer has _parse_positive_int_allowlist
final_submit_service has no runtime:answer_shadow reference
```

## 13. Shadow activation separation

Deploying this guard source default-OFF and activating shadow trial are separate operations.

### 13.1 Guard source default-OFF deploy

Allowed after approval:

```text
Deploy app/config.py.
Deploy app/services/answer_runtime_buffer.py.
Keep env unchanged.
Keep shadow disabled.
Keep queue/hybrid disabled.
```

This should produce no production behavior change.

### 13.2 Shadow trial activation

Not part of this task.

Requires separate approval:

```text
approve Phase 6.0 shadow trial for test exam only
```

Also requires:

```text
exact test exam ID
exact test account
exact test session ID if using session allowlist
separate env update
app-plane-only restart
pre-enable gates all PASS
rollback owner/path confirmed
```

Activation must use allowlist, not percentage rollout:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=<test_session_id>
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

or:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=<test_exam_id>
```

Still forbidden during activation:

```text
ANSWER_WRITE_MODE=queue/hybrid
ANSWER_QUEUE_ENABLED=true
ANSWER_QUEUE_PERCENTAGE > 0
Redis source-of-truth
Final submit reads Redis shadow
Production load-test
```

## 14. Phase 6 production remains blocked

Phase 6 production/canary remains blocked by:

```text
Redis maxmemory-policy=allkeys-lru.
Celery worker pool=solo and max-concurrency=1.
No forced flush proof under staging/shadow/canary.
No 0-mismatch evidence from real allowlisted shadow trial.
No operator approval for production queue/hybrid/runtime buffer.
```

Current decision:

```text
Phase 6 production: NO
Queue/hybrid: NO
Runtime buffer production source-of-truth: NO
```

## 15. Redis allkeys-lru warning

Current VPS Redis:

```text
maxmemory-policy=allkeys-lru
rejected_connections=0
evicted_keys=0
```

Impact:

```text
Redis is acceptable only for hash-only, best-effort shadow mirrors.
Redis is not safe as answer source-of-truth while allkeys-lru can evict keys.
Do not use Redis runtime buffer as final submit source.
Do not use Redis as the only answer persistence layer.
```

## 16. Celery solo-pool warning

Current worker:

```text
implementation=celery.concurrency.solo:TaskPool
max-concurrency=1
prefetch_count=4
```

Impact:

```text
Not ready for answer queue/hybrid production flush workload.
No queue/hybrid production until a dedicated answer flush worker design is deployed and proven.
```

## 17. Forbidden artifact check

Working tree check before writing this doc:

```text
forbidden artifact check: PASS
```

No new:

```text
APK/AAB
keystore/JKS/key.properties/local.properties
.env/.env.*
DB dump/backup/sql/sqlite/db
CSV/session artifacts
summary JSON artifacts
raw token/session/student PII/answer content
```

Note:

```text
Existing tracked .env.example and historical SQL files are repository artifacts, not new deploy artifacts for this plan.
They are not proposed for VPS deployment.
```

## 18. Final decision

```text
safe to deploy allowlist guard default-OFF: YES, after explicit operator approval and PASS preflight gates
safe to activate shadow now: NO
safe to start queue/hybrid: NO
safe to start Phase 6 production: NO
```

Next exact action:

```text
Wait for operator approval:
approve deploy Phase 6.0 shadow allowlist guard default-off
```

If approved, deploy only:

```text
app/config.py
app/services/answer_runtime_buffer.py
```

Then perform app-plane-only rolling restart and post-deploy validation. Shadow trial activation remains a separate later request.
