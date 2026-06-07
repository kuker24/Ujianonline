# Phase 5.7 VPS Deploy Result — Activity Logs Read Path

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
reviewed head: ac40dac86b161dacfaee035a1f27f2751e070603
message: docs: record phase 5.6 activity logs read path fix
```

## 2. New commits before deploy

```text
new commits after ac40dac86b161dacfaee035a1f27f2751e070603: none
```

Pre-deploy source confirmation:

```text
GET /api/activity/logs uses get_db_read: PASS
GET /api/activity/logs has no prune/delete/truncate/smart prune: PASS
GET /api/activity/logs uses projection + outer join: PASS
GET /api/activity/logs does not use selectinload: PASS
GET /api/activity/logs does not instantiate full UserActivityLog ORM rows: PASS
response shape compatibility: PASS
per_page max 200: PASS
DELETE /api/activity/logs/reset protected and write-only: PASS
```

Pre-deploy validation:

```text
compileall: PASS
targeted pytest: 61 passed
git diff --check: PASS
forbidden artifact check: PASS
```

## 3. Operator approval

Operator approval text captured from deployment instruction:

```text
approve deploy Phase 5.6 activity logs fix
```

## 4. VPS preflight result

VPS preflight timestamp:

```text
20260607T021456Z
```

Health and services:

```text
local /health: 200
public /health: 200
app containers api, api2-api8, api_admin, api_admin2: running/healthy
DB: accepting connections
PgBouncer: accepting connections
Redis: PONG
Redis rejected_connections: 0
Redis evicted_keys: 0
disk /: 52% used
memory: acceptable
load-test processes: none
```

DB gates:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Effective source settings before deploy:

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
answer_runtime_buffer_shadow_enabled=False
answer_runtime_buffer_shadow_percentage=0
exam_peak_mode=True
violation_async_enabled=True
admin_monitoring_detail_level=summary
mobile_apk_primary=True
```

Hard gate result:

```text
preflight: PASS
```

## 5. File deployed

Only one runtime file was deployed:

```text
app/api/activity.py
```

Remote path:

```text
/root/ujian_online/app/api/activity.py
```

## 6. Files explicitly not deployed

```text
tests: not deployed
docs: not deployed as runtime files
.env/.env.*: not deployed
docker-compose.production.yml: not deployed
APK/AAB: not deployed
flutter build output: not deployed
keystore/JKS/key.properties/local.properties: not deployed
DB dump/backup/sql/sqlite/db: not deployed
session CSV/summary JSON: not deployed
raw token/secret files: not deployed
```

## 7. Backup directory

```text
/root/ujian_online_backups/phase-5.6-activity-logs-20260607T021532Z
```

Backup file:

```text
/root/ujian_online_backups/phase-5.6-activity-logs-20260607T021532Z/activity.py
```

## 8. Pre/post/source checksums

```text
pre_sha256:    c9be34627d05c7c19659c532701334e255492b8fbbffdee22f0b79371d0fb337  /root/ujian_online/app/api/activity.py
source_sha256: 5e033657537abe9959436d438e4ec66665c38158e72d599a19601885f9991915  /tmp/phase57_activity.py
post_sha256:   5e033657537abe9959436d438e4ec66665c38158e72d599a19601885f9991915  /root/ujian_online/app/api/activity.py
live_sha256:   5e033657537abe9959436d438e4ec66665c38158e72d599a19601885f9991915  /root/ujian_online/app/api/activity.py
```

Checksum decision:

```text
post_sha256 == source_sha256: PASS
live_sha256 == source_sha256: PASS
```

Ownership and permissions preserved:

```text
pre_owner=ubuntu:ubuntu pre_mode=644
post_owner=ubuntu:ubuntu post_mode=644
```

Syntax validation note:

```text
host python unavailable: python command not found
container syntax compile: PASS
```

## 9. Restart scope

App-plane rolling restart performed:

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

Health after each restart group:

```text
local /health: 200
public /health: 200
all restarted app-plane containers: healthy
```

## 10. Services not restarted

The following services were not restarted. StartedAt values stayed unchanged before/after app-plane restart:

```text
db StartedAt=2026-06-06T04:27:40.732547151Z
pgbouncer StartedAt=2026-06-06T04:27:38.009982103Z
redis StartedAt=2026-06-06T04:27:39.367061352Z
nginx StartedAt=2026-06-06T04:27:36.397189495Z
celery_worker StartedAt=2026-06-06T04:27:32.472684811Z
celery_beat StartedAt=2026-06-06T04:27:34.769220224Z
```

## 11. Effective env after restart

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
answer_runtime_buffer_shadow_enabled=False
answer_runtime_buffer_shadow_percentage=0
exam_peak_mode=True
violation_async_enabled=True
admin_monitoring_detail_level=summary
mobile_apk_primary=True
```

Decision:

```text
direct safe-mode remains active: YES
queue/hybrid remains OFF: YES
runtime-buffer shadow remains OFF: YES
```

## 12. Functional endpoint checks

Immediate post-deploy authenticated endpoint checks used an internal short-lived token generated in-container without printing the token.

```text
GET /api/activity/logs?per_page=1: 200, shape PASS, 4402.3 ms initial sample
GET /api/activity/stats: 200, 174.5 ms
GET /api/activity/event-types: 200, 31.9 ms
GET /api/activity/my-logs?limit=1: 200, 39.5 ms
GET /api/monitoring/system/ops-summary: 200, 2678.8 ms
GET /api/stats/dashboard: 200, 304.1 ms
GET /api/users/advanced-search?per_page=1: 200, 120.6 ms
GET /api/grading/stats: 200, 544.1 ms
```

DB long-query checks immediately after endpoint validation:

```text
long_active_queries_gt60s=0
activity_logs_long_active_gt10s=0
```

Note: an earlier local validation helper attempted a full ORM `User` query to generate an admin token and was replaced with projection-only token generation. It did not affect service health or app service logs; final validation and observation used projection-only token generation.

## 13. Activity logs read-only validation

Deployed file marker check from running container:

```text
get_db_read=PASS
no_write_dep=PASS
no_prune=PASS
no_delete_truncate=PASS
outerjoin_projection=PASS
no_selectinload=PASS
no_orm_scalars=PASS
per_page_cap_200=PASS
```

Read-only decision:

```text
GET /api/activity/logs no longer calls reset/prune/delete/truncate: YES
GET /api/activity/logs uses read DB dependency: YES
GET /api/activity/logs avoids User selectin eager loading: YES
GET /api/activity/logs avoids full UserActivityLog ORM list rows: YES
```

## 14. Observation window result

Observation window:

```text
start: 2026-06-07T02:33:21Z
end:   2026-06-07T03:38:54Z
length: about 65 minutes
```

Activity logs response samples:

```text
t0:   status=200 time_ms=87.3 bytes=269 shape=PASS
t30m: status=200 time_ms=58.1 bytes=278 shape=PASS
t60m: status=200 time_ms=31.1 bytes=277 shape=PASS
```

No long activity-log query during samples:

```text
long_active_queries_gt60s=0
activity_logs_long_active_gt10s=0
```

Final health:

```text
local /health: 200
public /health: 200
all containers: running/healthy
```

Final DB gates:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
activity_logs_long_active_gt10s=0
```

## 15. Error/log aggregate counts

Final aggregate since observation start:

```text
api_traceback=0
connection_does_not_exist=0
broken_pipe=0
asyncpg_internal_client_error=0
http_500=0
http_503_409=0
final_submit_errors=0
answer_save_errors=0
queue_hybrid_evidence=0
runtime_shadow_evidence=0
nginx_500=0
nginx_499=0
static_404_5xx=0
activity_logs_slow_10s_lines=0
```

Decision:

```text
ConnectionDoesNotExist/BrokenPipe cluster disappeared during observation: YES
~74s /api/activity/logs behavior reproduced: NO
500 remained zero: YES
answer/final-submit errors observed: NO
```

## 16. Forbidden artifact check

Local source/deploy artifact check:

```text
APK/AAB: none
keystore/JKS/key.properties/local.properties: none
.env/.env.*: none
DB dump/backup/sql/sqlite/db: none
session CSV/summary JSON: none
raw token/session/student PII/answer content: none
```

Result:

```text
forbidden artifact check: PASS
```

## 17. Rollback path

If rollback is required:

```bash
# 1. Confirm gates are zero first.
# active_sessions=0, running_exam_windows=0, final_submit_drain=0

cp -a \
  /root/ujian_online_backups/phase-5.6-activity-logs-20260607T021532Z/activity.py \
  /root/ujian_online/app/api/activity.py

cd /root/ujian_online
docker compose -f docker-compose.production.yml restart api_admin
curl -fsS http://127.0.0.1/health
docker compose -f docker-compose.production.yml restart api_admin2
curl -fsS http://127.0.0.1/health

for svc in api api2 api3 api4 api5 api6 api7 api8; do
  docker compose -f docker-compose.production.yml restart "$svc"
  curl -fsS http://127.0.0.1/health
done
```

Do not restart DB/Redis/PgBouncer unless separately approved.

## 18. Final decision

```text
Phase 5.6 deploy: PASS
Activity logs read path live: YES
Admin API noise clean: YES for 65-minute observation window
Phase 6 production may start: NO
Queue/hybrid may start: NO
Phase 6 shadow trial can be planned next: PARTIAL
```

Phase 6 shadow planning note:

```text
The activity logs blocker is cleared for the observed window. Phase 6 shadow is still not approved or enabled. A separate Phase 6.0 shadow plan, operator approval, and default-off/hash-only safeguards are still required before any live shadow trial.
```
