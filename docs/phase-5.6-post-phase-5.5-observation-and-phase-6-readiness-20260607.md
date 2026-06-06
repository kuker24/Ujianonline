# Phase 5.6 Post Phase 5.5 Observation and Phase 6 Readiness

Date: 2026-06-07

## 1. Latest GitHub head reviewed

Observation started after fetching:

```text
branch: review/sanitized-root-20260531-115153
base requested: 508b3b9b49419b83587aeeee3425f4a19dc8b067
head reviewed: 0afa171fe9f0a80b80830753b07a0da071d3df21
```

New commits after the requested base were docs-only Phase 5.5 records:

```text
0afa171 docs: record phase 5.5 vps deploy result for auth and frontend sync
ac6c64f docs: add phase 5.5 vps deploy plan for auth and frontend sync
```

Changed files after base:

```text
docs/phase-5.5-vps-deploy-plan-auth-lightweight-and-frontend-sync-20260607.md
docs/phase-5.5-vps-deploy-result-auth-lightweight-and-frontend-sync-20260607.md
```

No backend/runtime/static/env/compose/schema/APK changes were present after the known Phase 5.4 source baseline.

Forbidden scans:

```text
forbidden artifact scan: PASS
queue/hybrid/shadow activation scan: PASS
```

## 2. Production action performed

This was a read-only observation/checkpoint.

```text
deploy: NO
restart: NO
.env change: NO
migration/schema change: NO
production load-test: NO
APK action: NO
queue/hybrid activation: NO
Phase 6 shadow activation: NO
DB/Redis/PgBouncer restart: NO
```

Temporary shell scripts were written under `/tmp` only to run aggregate checks; no production config/source was edited.

## 3. VPS health status

Observation timestamp:

```text
2026-06-06T23:24:18Z
hostname: adminujian
```

Health checks:

```text
local /health: 200
public /health: 200
Docker app-plane containers: healthy
DB: healthy
PgBouncer: healthy
Redis: PONG / healthy
Nginx: healthy
Celery worker/beat: healthy
```

App-plane uptime after Phase 5.5 deploy was approximately 3 hours at observation time.

## 4. Effective env status

Effective env inside API container remained direct safe-mode:

```json
{"ADMIN_MONITORING_DETAIL_LEVEL":"summary","ANSWER_QUEUE_ENABLED":false,"ANSWER_QUEUE_PERCENTAGE":0,"ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED":false,"ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE":0,"ANSWER_WRITE_MODE":"direct","EXAM_PEAK_MODE":true,"MOBILE_APK_PRIMARY":true,"VIOLATION_ASYNC_ENABLED":true}
```

## 5. Active sessions/running exams/final-submit drain status

Read-only DB gates:

```text
active_sessions: 0
running_exam_windows: 0
final_submit_or_drain: 0
long_active_queries >60s: 0
idle_in_transaction: 0
postgres_connections: 65
next_exam_start: 2026-06-08 00:30:00+00:00
load-test processes: none
```

## 6. Resource status

Host resources:

```text
disk /: 52% used
memory: ~15 GiB total, ~11 GiB available
swap: ~178 MiB used / 2.0 GiB
```

Notable container memory:

```text
api replicas: ~24–26% of 960 MiB each
api_admin: ~99.58% of 768 MiB
api_admin2: ~13.98% of 768 MiB
Postgres: ~462 MiB / 5.5 GiB
Redis: ~15 MiB / 1.75 GiB
```

`api_admin` memory should be watched, but no OOM/restart was observed in this checkpoint.

## 7. Backend functional checks

A short-lived in-memory admin token was generated inside the API container for internal functional checks. The token was not printed or stored.

Results and approximate response times:

```json
{
  "/health": {"status": 200, "ms": 20.7},
  "/api/monitoring/system/ops-summary": {"status": 200, "ms": 157.73},
  "/api/stats/dashboard": {"status": 200, "ms": 50.1},
  "/api/users/advanced-search?per_page=1": {"status": 200, "ms": 27.49},
  "/api/users/1": {"status": 200, "ms": 21.69},
  "/api/grading/stats": {"status": 200, "ms": 249.97},
  "/api/activity/logs?per_page=1": {
    "status": "SKIPPED_READ_ONLY_OBSERVATION",
    "reason": "GET endpoint can run opportunistic auto-prune writes"
  }
}
```

`/api/activity/logs` was intentionally not called by the functional checker to preserve read-only observation because the endpoint can still perform opportunistic pruning writes.

## 8. Frontend/static checks

Static assets returned 200:

```text
/static/js/admin/monitoring.js: 200 text/javascript, 197689 bytes
/static/js/api.js: 200 text/javascript, 62522 bytes
/static/js/auth.js: 200 text/javascript, 9614 bytes
/static/js/exam-system.js: 200 text/javascript, 119307 bytes
```

## 9. Restart-safe UI status

Served `static/js/admin/monitoring.js` still includes the required safe behavior:

```text
dry-run/preflight before restart: present
includeDataServices=false: present
DB/Redis/PgBouncer restart display: present
app-plane restart message: present
unsafe include_data_services coupling to fullRestartAvailable: absent
```

Result:

```text
restart_safe_ui=OK
```

## 10. Deployed file checksum/drift status

Key live checksums matched the Phase 5.5 deployed source checksums:

```text
efcf0f63d59d5412511ac0573076d1442b280191b5fbc2af1f1ec6cde05a6c72  app/core/security.py
95578ac41753c5dacc249396175c86c5bbfedbd969450b25dc11fa23248da40a  app/api/auth.py
5fa5c5cd9596b20954d72c3a330b72bc01c8ffcc9dc0779b86e27a919266ef98  app/api/users.py
740437a828cbb1fc99c21e95f39c8aefdae3d503d5e7268b26a13adfdf25dbcd  app/api/grading.py
df734121e45463a2f11227e68a6a0bd0341c1f71f64c0c91596c04794bdf3f43  static/js/admin/monitoring.js
233b8aeb172af217b12d2511d9a878a845b1d5b520682c959482f069fc85d010  static/js/api.js
6837a390033fa3c1880d16a15061c6dc086533ce0d1bc4710d0d02dbd0334c4a  static/js/auth.js
ab5bb7aecf18c3dc0553c27b75a500e903be9e0645e49f9940e6284b5d7a142e  static/js/exam-system.js
```

Phase 5.5 remains live.

## 11. Nginx/API log aggregate counts

Window counts were collected as aggregate counts only; no raw token/session/PII/answer content was recorded.

### 60 minutes

```text
API tracebacks: 68
ImportError/ModuleNotFoundError: 0
asyncpg InternalClientError: 0
ConnectionDoesNotExistError: 22
BrokenPipeError: 6
HTTP 500 marker in API logs: 0
HTTP 503/409 marker in API logs: 0
queue/hybrid evidence: 0
runtime shadow activation evidence: 0
final-submit errors: 0
answer save errors: 0
nginx 500: 0
nginx 499: 7
static 404: 0
static 5xx: 0
```

### 120 minutes

```text
API tracebacks: 68
ConnectionDoesNotExistError: 22
BrokenPipeError: 6
nginx 500: 0
nginx 499: 7
static 404: 0
static 5xx: 0
```

### 240 minutes

```text
API tracebacks: 68
ConnectionDoesNotExistError: 22
BrokenPipeError: 6
nginx 500: 0
nginx 499: 9
static 404: 0
static 5xx: 0
```

Container attribution:

```text
api/api2/api3/api4/api5/api6/api7/api8/api_admin2: 0 connection-error markers
api_admin: 46 connection-error/traceback markers
```

Sanitized context showed the remaining error cluster is tied to:

```text
GET /api/activity/logs took ~74015.94ms
ConnectionDoesNotExistError: connection was closed in the middle of operation
BrokenPipeError: [Errno 32] Broken pipe
```

## 12. Admin API noise status after Phase 5.5

Assessment:

```text
Auth/user endpoints: improved / healthy in functional checks.
Advanced-search: 200 in ~27 ms.
User detail: 200 in ~22 ms.
Dashboard stats: 200 in ~50 ms.
Ops summary: 200 in ~158 ms.
Grading stats: 200 in ~250 ms.
Static assets: healthy.
Remaining admin API noise: persists on /api/activity/logs.
```

Compared to the pre-Phase 5.4 audit:

```text
nginx 500: improved/gone in observed window (0)
admin endpoint 499: reduced but still present (7 in 60/120m, 9 in 240m)
asyncpg InternalClientError: gone in observed window (0)
ConnectionDoesNotExistError/BrokenPipeError: persists, isolated to api_admin and activity logs
```

Conclusion:

```text
Phase 5.4 fixed the auth/user eager-load hot path, but admin API noise is not fully clean because /api/activity/logs remains slow and can still close DB connections mid-operation.
```

## 13. Redis status

Redis status:

```text
PING: PONG
used_memory_human: 11.40M
used_memory_peak_human: 12.81M
maxmemory_human: 1.37G
maxmemory_policy: allkeys-lru
mem_fragmentation_ratio: 1.78
rejected_connections: 0
evicted_keys: 0
runtime shadow keys: 0
runtime answer buffer keys: 0
answer queue keys: 0
celery keys: 0
```

Readiness note:

```text
Redis remains unsafe as answer source-of-truth because maxmemory-policy is still allkeys-lru.
```

## 14. Worker status

Celery worker:

```text
container: healthy
command: celery -A app.tasks.scheduler worker --loglevel=warning --pool=solo --max-tasks-per-child=200
pool/concurrency: solo / effectively concurrency 1
recent celery error count: 0
queue backlog keys observed: 0
```

Readiness note:

```text
Worker remains unsuitable for answer flush production due to solo pool/concurrency and unproven answer flush/final-submit behavior.
```

## 15. Final-submit status

Observed log aggregates:

```text
final-submit errors: 0
answer save errors: 0
```

Current decision remains:

```text
Final submit remains direct/PostgreSQL source-of-truth.
No Redis shadow dependency was observed.
```

## 16. Answer path status

Observed answer path and env:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
runtime shadow keys: 0
runtime answer buffer keys: 0
answer queue keys: 0
queue/hybrid evidence in logs: 0
runtime shadow activation evidence in logs: 0
```

## 17. Phase 6 readiness decision

Conservative decision:

```text
Phase 6 production: NO
Queue/hybrid: NO
Phase 6 shadow trial: NOT YET / PARTIAL readiness only
```

Reason:

```text
Although direct answer mode is healthy and Phase 5.5 auth/user fixes are live, admin/API noise persists via /api/activity/logs with 74s slow request and DB connection-closed errors. Per safety criteria, fix Phase 5.6 admin API noise before planning or requesting a Phase 6 shadow trial.
```

Phase 6 blockers still present:

```text
Redis maxmemory-policy=allkeys-lru
Celery worker --pool=solo / concurrency 1
No live 0-mismatch shadow evidence because shadow remains OFF
Final-submit forced flush/Redis-shadow independence not proven under shadow
Admin API noise not fully clean due to /api/activity/logs
```

## 18. Recommended next action

Recommended option: **Option 2 — Phase 5.6 remaining admin/API noise fix**.

Scope for Phase 5.6 source-only plan:

```text
1. Split /api/activity/logs read endpoint from opportunistic auto-prune writes.
2. Move activity log listing to get_db_read after pruning is removed/split.
3. Replace selectinload(UserActivityLog.user) with lightweight projection/join for user_name/user_role.
4. Add date/index-friendly query shape and smaller bounded defaults if needed.
5. Add tests proving /api/activity/logs does not instantiate User ORM rows or trigger relationship cascades.
6. Re-observe for 60–240 minutes; require 0 ConnectionDoesNotExist/BrokenPipe cluster before Phase 6 shadow planning.
```

Do not activate Phase 6 shadow until after Phase 5.6 observation is clean or a separate operator approval explicitly accepts this residual admin-noise risk.

## 19. Rollback note

Rollback is not recommended from this observation because health, direct answer mode, static assets, auth/user endpoints, and dashboard checks are healthy.

If rollback becomes necessary, Phase 5.5 backup path remains:

```text
/root/ujian_online_backups/phase-5.4-auth-frontend-20260606T203324Z
```

Rollback must be app-plane-only and only after confirming no active sessions/running exam/final-submit drain.

## 20. Forbidden artifact check

No forbidden files were produced or committed:

```text
APK/AAB: none
keystore/JKS/key.properties/local.properties: none
.env/.env.*: none
DB dump/backup/sql/sqlite/db: none
session CSV/summary JSON: none
raw token/session/student PII/answer content: none in this report
```

## 21. Final decision

```text
Phase 5.5 deploy remains healthy: YES
Backend auth eager-load fix remains live: YES
Frontend bundle source sync remains live: YES
Restart-safe UI remains safe: YES
Direct safe-mode remains active: YES
Admin API noise fully clean: NO
Phase 6 production may start: NO
Queue/hybrid may start: NO
Phase 6 shadow trial can be planned now: NO / PARTIAL readiness only
Next exact action: Phase 5.6 source-only fix plan for /api/activity/logs read/prune split and lightweight query path
```
