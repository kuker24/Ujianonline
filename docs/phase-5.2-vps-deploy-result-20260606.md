# Phase 5.2 VPS Deploy Result — Direct Hardening + Shadow Default-OFF

Date: 2026-06-06

## Summary

Controlled Phase 5.2 source deployment completed on VPS. This was a source-only/default-off deployment for Phase 5.1 direct hardening and Phase 6 shadow readiness.

No queue/hybrid/runtime-buffer production routing was enabled.

## GitHub source head deployed

```text
bf62a3585e4071611a486c0347fcf57bf051f6a4
docs: add phase 5.2 vps deploy plan for default-off hardening
```

Runtime/source patch included from earlier commits:

```text
5937c3c fix: harden direct answer sync Redis side effects
0d8b279 test: add runtime buffer shadow readiness guards
dbf5632 docs: record phase 5.1 hardening and phase 6 shadow readiness
```

## Operator approval

Operator explicitly approved:

```text
approve deploy Phase 5.2
```

## Preflight result

All hard gates passed before file copy:

| Gate | Result |
|---|---:|
| public/local `/health` | 200 |
| active sessions | 0 |
| running exam windows | 0 |
| final-submit/drain queries | 0 |
| long active DB queries >60s | 0 |
| idle-in-transaction | 0 |
| Redis rejected/evicted | 0 / 0 |
| disk `/` | 52% used |
| load-test process | none |

## Files deployed

Copied only these files to `/root/ujian_online`:

```text
app/config.py
app/services/answer_sync_service.py
app/services/answer_runtime_buffer.py
app/tasks/answer_processor.py
scripts/runtime_buffer_consistency_check.py
```

Not deployed:

```text
docker-compose.production.yml
.env
.env.*
APK/AAB
keystore/key.properties/local.properties
DB dump/sqlite/sql backup
CSV/session/summary artifacts
```

## Backup

Live files were backed up before copy:

```text
/root/ujian_online_backups/phase-5.2-default-off-20260606T145304Z
```

Predeploy live checksums:

```text
a63b8b87df9bf80d0b6eeae7b8f975f49f6a41c62aaade85ad4cb5322828896f  app/config.py
3fd39d4a6041a89d206d78059221ca0514450d6566b21b578370d3f1b29eeabf  app/services/answer_sync_service.py
a78ea6d0f9f7705a0ba25ea18f18f049f96f9a460761ac0f7f175b1d860dd1c4  app/services/answer_runtime_buffer.py
861fef71186d74f0e214da73c481428c2e415a9c977109c6bd3559b02a115702  app/tasks/answer_processor.py
```

`runtime_buffer_consistency_check.py` did not previously exist on the VPS.

## Post-copy checksums

```text
4e0d54702626cc92f316328b93b6b3efe391c3c4af73701c8c4e2f9519796ec5  app/config.py
6a5d17b34233d30aa5a1040cefc907761718eb0892168963130a4d1e15e45f72  app/services/answer_sync_service.py
f4c218c7731b3613fc1ab45a27496e552aa3cb88d27e7a2ada3b57e607fb0b7e  app/services/answer_runtime_buffer.py
944e9266d84429c96c51d942bf63ee09fef8a89921b5932d32f51fa1cd3c728d  app/tasks/answer_processor.py
e31087dbcad9d117ca0f69e16e651631541a2ac9408d282937c492cb4491d4bd  scripts/runtime_buffer_consistency_check.py
```

## Restart scope

Restart performed:

```text
api, api2, api3, api4, api5, api6, api7, api8, api_admin, api_admin2
```

All app-plane containers returned healthy.

Not restarted:

```text
PostgreSQL
PgBouncer
Redis
nginx
celery_worker
celery_beat
host
```

Data services remained up for ~10 hours after app-plane restart validation.

## Runtime defaults after restart

Effective settings inside `ujian_online-api-1`:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=False
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=False
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS=14400
ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT=100
EXAM_PEAK_MODE=True
VIOLATION_ASYNC_ENABLED=True
ADMIN_MONITORING_DETAIL_LEVEL=summary
MOBILE_APK_PRIMARY=True
SEB_DESKTOP_LEGACY_ENABLED=False
SEB_QR_ENABLED=False
SEB_DEBUG_ENDPOINTS_ENABLED=False
APK_BUILD_ENDPOINT_ENABLED=False
TELEGRAM_ALERTING_ENABLED=False
HEAVY_EXPORT_ENABLED=False
```

## Import and checker validation

Source import validation:

```text
imports_ok
hash_len=64
shadow_enabled=False
shadow_for_session=False
```

Consistency checker help works inside an API container.

Read-only checker run with shadow OFF:

```json
{"checked_answers": 0, "checked_sessions": 20, "extra_in_redis": 0, "missing_in_redis": 0, "payload_hash_mismatch": 0, "redis_errors": 0, "stale_runtime_sessions": 0}
```

Redis shadow key count:

```text
runtime:answer_shadow:* = 0
```

## Runtime policy after restart

```json
{"cheating_reporting_mode":"normal","final_submit_priority":true,"mode":"exam_peak","policy_version":"20260606-mobile-runtime-adaptive-v2","resource_mode":"normal"}
```

## Post-deploy DB gates

```json
{"active_sessions":0,"idle_in_transaction":0,"long_active_queries_gt_60s":0,"running_exam_windows":0}
```

## Log validation

Recent app-plane logs had no matching errors for:

```text
ERROR
Traceback
ImportError
ModuleNotFoundError
unexpected 503/409
queue/hybrid routing
runtime shadow activation
```

## Production action performed

| Action | Performed? |
|---|---:|
| Source file copy | Yes |
| API/admin app-plane rolling restart | Yes |
| DB/Redis/PgBouncer restart | No |
| `.env` change | No |
| Compose overwrite | No |
| Migration/schema change | No |
| Production load-test | No |
| APK change | No |
| Queue/hybrid activation | No |
| Runtime buffer source-of-truth | No |

## Decision

Phase 5.2 source deployment: **PASS**.

Queue/hybrid/runtime-buffer production remains **NO**.

Phase 6 shadow remains default OFF. Any activation of shadow mode, queue, hybrid, or runtime buffer source-of-truth still requires separate operator approval and a new preflight.

## Rollback reference

Use the backup directory if rollback is needed:

```text
/root/ujian_online_backups/phase-5.2-default-off-20260606T145304Z
```

Rollback should restore the backed-up files and restart only app-plane API/admin containers, not DB/Redis/PgBouncer.
