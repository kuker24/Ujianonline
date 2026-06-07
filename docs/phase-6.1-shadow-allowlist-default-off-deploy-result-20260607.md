# Phase 6.1 Shadow Allowlist Guard Default-OFF Deploy Result

Date: 2026-06-07

## 1. Approval

Operator approval received:

```text
approve deploy Phase 6.0 shadow allowlist guard default-off
```

Scope approved:

```text
Deploy source guard allowlist only.
Keep shadow default-OFF.
Do not activate shadow trial.
Do not enable queue/hybrid.
Do not change live env.
Do not deploy docker-compose.production.yml.
Do not restart DB/Redis/PgBouncer.
```

## 2. GitHub source confirmed before deploy

```text
expected head: 488c90c3e850e6c78899bb3fcecdf4caf7619759
remote head:   488c90c3e850e6c78899bb3fcecdf4caf7619759
local head:    488c90c3e850e6c78899bb3fcecdf4caf7619759
```

Source checks before deploy:

```text
python -m compileall app: PASS
python -m py_compile scripts/runtime_buffer_consistency_check.py: PASS
git diff --check: PASS
forbidden artifact check: PASS
```

Source checksums deployed:

```text
7a6daf9a297f33e60d0332b22c29ec652771d56df21e847d730c8522720c79cb  app/config.py
6143d9e078ea54c033caae0d1cf0fe7a6b649ec2ce86e55ed402f214db249e37  app/services/answer_runtime_buffer.py
```

## 3. Preflight result

Timestamp:

```text
20260607T042041Z
```

Health:

```text
local /health: 200
public /health: 200
```

Effective live settings before deploy:

```text
ANSWER_WRITE_MODE=direct | settings.answer_write_mode=direct
ANSWER_QUEUE_ENABLED=false | settings.answer_queue_enabled=False
ANSWER_QUEUE_PERCENTAGE=0 | settings.answer_queue_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=UNSET | settings.answer_runtime_buffer_shadow_enabled=False
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=UNSET | settings.answer_runtime_buffer_shadow_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=UNSET | settings.answer_runtime_buffer_shadow_session_ids=MISSING
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=UNSET | settings.answer_runtime_buffer_shadow_exam_ids=MISSING
EXAM_PEAK_MODE=true | settings.exam_peak_mode=True
VIOLATION_ASYNC_ENABLED=true | settings.violation_async_enabled=True
ADMIN_MONITORING_DETAIL_LEVEL=summary | settings.admin_monitoring_detail_level=summary
MOBILE_APK_PRIMARY=true | settings.mobile_apk_primary=True
```

DB gates:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Redis gates:

```text
PONG
used_memory_human=9.92M
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

Celery:

```text
celery_worker: running/healthy
celery_beat: running/healthy
pool implementation: celery.concurrency.solo:TaskPool
max-concurrency: 1
prefetch_count: 4
```

Data service StartedAt before deploy:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

## 4. Files deployed

Runtime files deployed:

```text
app/config.py
app/services/answer_runtime_buffer.py
```

Files explicitly not deployed:

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

No live env was changed.

## 5. Backup and install details

Backup directory:

```text
/root/ujian_online_backups/phase-6.1-shadow-allowlist-default-off-20260607T042302Z
```

Pre-copy live checksums:

```text
4e0d54702626cc92f316328b93b6b3efe391c3c4af73701c8c4e2f9519796ec5  app/config.py
f4c218c7731b3613fc1ab45a27496e552aa3cb88d27e7a2ada3b57e607fb0b7e  app/services/answer_runtime_buffer.py
```

Post-copy live checksums:

```text
7a6daf9a297f33e60d0332b22c29ec652771d56df21e847d730c8522720c79cb  app/config.py
6143d9e078ea54c033caae0d1cf0fe7a6b649ec2ce86e55ed402f214db249e37  app/services/answer_runtime_buffer.py
```

Ownership/mode preserved from live files:

```text
app/config.py owner=root group=root mode=644
app/services/answer_runtime_buffer.py owner=root group=root mode=644
```

Note:

```text
Initial py_compile attempted to write __pycache__ in the container and hit PermissionError.
This was the known container __pycache__ permission issue, not a source syntax error.
No app-plane restart had occurred at that point.
The deploy continued with syntax compile via compile(source, path, 'exec') without writing .pyc.
```

Syntax validation without pycache write:

```text
SYNTAX_COMPILE_PASS=/app/app/config.py
SYNTAX_COMPILE_PASS=/app/app/services/answer_runtime_buffer.py
```

Source marker check:

```text
SOURCE_MARKERS=PASS
```

Markers confirmed:

```text
answer_runtime_buffer_shadow_session_ids
answer_runtime_buffer_shadow_exam_ids
runtime_answer_shadow_session_allowlist
runtime_answer_shadow_exam_allowlist
_parse_positive_int_allowlist
```

## 6. Restart scope

App-plane rolling restart only:

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

Health after each restart:

```text
health_after_api_admin=200
health_after_api_admin2=200
health_after_api=200
health_after_api2=200
health_after_api3=200
health_after_api4=200
health_after_api5=200
health_after_api6=200
health_after_api7=200
health_after_api8=200
```

Not restarted:

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

Data service StartedAt after deploy:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

Result:

```text
DATA_SERVICE_STARTED_AT_UNCHANGED=PASS
```

## 7. Post-deploy validation

Final validation timestamp:

```text
20260607T042653Z
```

Health:

```text
local /health: 200
public /health: 200
all containers: running/healthy
```

Installed live checksums:

```text
7a6daf9a297f33e60d0332b22c29ec652771d56df21e847d730c8522720c79cb  app/config.py
6143d9e078ea54c033caae0d1cf0fe7a6b649ec2ce86e55ed402f214db249e37  app/services/answer_runtime_buffer.py
```

Effective post-deploy settings:

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
answer_runtime_buffer_shadow_enabled=False
answer_runtime_buffer_shadow_percentage=0
answer_runtime_buffer_shadow_session_ids=
answer_runtime_buffer_shadow_exam_ids=
session_allowlist=set()
exam_allowlist=set()
shadow_enabled_for_probe=False
DEFAULT_OFF_VALIDATE=PASS
```

Runtime default-off behavior:

```text
session_allowlist set()
exam_allowlist set()
shadow_session_123 False
RUNTIME_DEFAULT_OFF_BEHAVIOR=PASS
```

Redis/key checks:

```text
rejected_connections=0
evicted_keys=0
runtime_shadow_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

DB gates after deploy:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Log aggregate since deploy window:

```text
traceback=0
connection_does_not_exist=0
broken_pipe=0
http_500=0
http_503_409=0
queue_hybrid_evidence=0
runtime_shadow_evidence=0
answer_save_errors=0
final_submit_errors=0
```

## 8. Production behavior confirmation

Confirmed unchanged:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false/unset effective false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0/unset effective 0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=empty/unset effective empty
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=empty/unset effective empty
EXAM_PEAK_MODE=true
VIOLATION_ASYNC_ENABLED=true
ADMIN_MONITORING_DETAIL_LEVEL=summary
MOBILE_APK_PRIMARY=true
```

No evidence of:

```text
queue activation
hybrid activation
runtime shadow writes
runtime answer buffer production use
Redis source-of-truth
final submit Redis dependency
```

## 9. Remaining warnings and blockers

Redis warning remains:

```text
maxmemory-policy=allkeys-lru
```

Impact:

```text
Redis remains unsafe as answer source-of-truth.
Redis is acceptable only for future hash-only best-effort shadow trial after separate approval.
```

Celery warning remains:

```text
pool=solo
max-concurrency=1
```

Impact:

```text
Not ready for answer queue/hybrid production flush workload.
```

Phase 6 production remains blocked by:

```text
Redis allkeys-lru policy
Celery solo/concurrency=1
No forced flush proof
No 0-mismatch evidence from real allowlisted shadow trial
No operator approval for production queue/hybrid/runtime buffer
```

## 10. Final decision

```text
Phase 6.1 default-OFF source guard deploy: PASS
Shadow trial activated: NO
Queue/hybrid enabled: NO
Runtime buffer production source-of-truth: NO
Phase 6 production: NO
```

Next exact action:

```text
If and only if operator wants a live shadow trial later, request separate approval:
approve Phase 6.0 shadow trial for test exam only
```

That later trial must identify exact test exam/account/session and must keep queue/hybrid OFF.
