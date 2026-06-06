# Phase 5.3 Post-Deploy Observation Result

Date: 2026-06-06
Observation window: 2026-06-06T15:22:54Z to 2026-06-06T15:23:34Z

## 1. Summary

Phase 5.3 read-only post-deploy observation was completed after the Phase 5.2 controlled VPS source deployment.

Result: **PASS**.

No rollback trigger fired.

No production action was performed beyond read-only observation commands:

```text
no deploy
no runtime source copy
no restart
no .env change
no docker-compose.production.yml change
no DB migration or DDL
no Redis/PostgreSQL/PgBouncer restart
no queue/hybrid enablement
no runtime buffer shadow enablement
no production load-test
no APK/AAB action
```

## 2. GitHub state before observation

Compared base and branch head:

```text
base: 0fc86da84d35af509c6fb56d1d025bd51b510b95
head: 0fc86da84d35af509c6fb56d1d025bd51b510b95
commits base..head: 0
```

There were no new commits to review before the observation.

## 3. Health checks

```text
http://127.0.0.1/health       200
https://127.0.0.1/health      200
https://man1rokanhulu.cloud/health 200
```

Tail recheck after the observation also returned 200 for all three health endpoints.

## 4. Container state

API/admin app-plane containers were healthy:

```text
api          healthy, up ~28 minutes
api2         healthy, up ~28 minutes
api3         healthy, up ~28 minutes
api4         healthy, up ~28 minutes
api5         healthy, up ~28 minutes
api6         healthy, up ~28 minutes
api7         healthy, up ~28 minutes
api8         healthy, up ~28 minutes
api_admin    healthy, up ~28 minutes
api_admin2   healthy, up ~28 minutes
```

Data services were healthy and were not restarted by this observation:

```text
db          healthy, up ~11 hours
pgbouncer   healthy, up ~11 hours
redis       healthy, up ~11 hours
```

## 5. Disk and memory

```text
/ disk usage: 52%
memory total: 15986 MB
memory available: 12168 MB
swap used: 5 MB
```

No resource-pressure concern was observed.

## 6. Source checksum verification

Live VPS source checksums still matched the Phase 5.2 post-copy checksums:

```text
4e0d54702626cc92f316328b93b6b3efe391c3c4af73701c8c4e2f9519796ec5  app/config.py
6a5d17b34233d30aa5a1040cefc907761718eb0892168963130a4d1e15e45f72  app/services/answer_sync_service.py
f4c218c7731b3613fc1ab45a27496e552aa3cb88d27e7a2ada3b57e607fb0b7e  app/services/answer_runtime_buffer.py
944e9266d84429c96c51d942bf63ee09fef8a89921b5932d32f51fa1cd3c728d  app/tasks/answer_processor.py
e31087dbcad9d117ca0f69e16e651631541a2ac9408d282937c492cb4491d4bd  scripts/runtime_buffer_consistency_check.py
```

No runtime source drift was detected.

## 7. Effective production settings

The effective app settings inside `ujian_online-api-1` remained safe:

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
answer_runtime_buffer_shadow_enabled=False
answer_runtime_buffer_shadow_percentage=0
answer_runtime_buffer_shadow_ttl_seconds=14400
answer_runtime_buffer_consistency_sample_limit=100
exam_peak_mode=True
violation_async_enabled=True
mobile_apk_primary=True
```

Direct safe-mode remains active.

Queue, hybrid, and runtime buffer shadow remain OFF.

## 8. Import and shadow helper validation

```text
imports_ok
hash_len=64
shadow_enabled=False
shadow_for_session=False
```

The deployed Phase 5.2 source imported successfully.

## 9. Database safety gates

Aggregate-only DB gates were clean:

```json
{"active_sessions":0,"final_submit_or_drain_queries":0,"idle_in_transaction":0,"long_active_queries_gt_60s":0,"running_exam_windows":0}
```

No active exam/session/drain blocker was observed during the read-only check.

## 10. Redis safety gates

```text
PING=PONG
rejected_connections=0
evicted_keys=0
runtime_answer_shadow_keys=0
runtime_answer_queue_keys=0
```

No shadow keys appeared while shadow is disabled.

No runtime answer queue keys were observed.

## 11. Runtime buffer consistency checker

The consistency checker was run read-only via container stdin to avoid copying files into the API container during observation.

Result:

```json
{"checked_answers":0,"checked_sessions":20,"extra_in_redis":0,"missing_in_redis":0,"payload_hash_mismatch":0,"redis_errors":0,"stale_runtime_sessions":0}
```

Interpretation:

```text
shadow is OFF
no Redis shadow mirrors are expected
checked_answers=0 is acceptable
mismatch/error fields are all zero
```

## 12. Runtime policy

```json
{"cheating_reporting_mode":"normal","final_submit_priority":true,"mode":"exam_peak","policy_version":"20260606-mobile-runtime-adaptive-v2","resource_mode":"normal"}
```

Final submit remains explicitly prioritized.

## 13. Log aggregate checks

30-minute app-plane aggregate log scan:

```json
{"answer_shadow":0,"error":0,"http_503_409":0,"import_error":0,"queue_hybrid":0,"traceback":0}
```

Tail recheck produced the same zero counts.

No raw logs, tokens, session values, or PII were recorded.

## 14. Load-test process check

```text
none
```

No production load-test process was observed.

## 15. Observation note

The initial observation wrapper produced all important metrics but exited non-zero after the log aggregate section before printing its final marker. A short tail check was then run read-only and confirmed:

```text
health endpoints remained 200
load-test process check = none
log aggregate counts remained zero
```

No production service or runtime configuration was changed.

## 16. Acceptance criteria

| Criterion | Result |
|---|---:|
| health endpoints remain 200 | PASS |
| API/admin app-plane healthy | PASS |
| DB/PgBouncer/Redis healthy | PASS |
| DB/PgBouncer/Redis not restarted by observation | PASS |
| direct/queue-off/shadow-off defaults preserved | PASS |
| source checksums match Phase 5.2 post-copy | PASS |
| imports_ok | PASS |
| runtime shadow key count is 0 | PASS |
| consistency checker mismatch/error fields are 0 | PASS |
| no import/startup errors in aggregate logs | PASS |
| no queue/hybrid/runtime-buffer routing evidence | PASS |
| no final-submit regression evidence in aggregate checks | PASS |
| no production load-test | PASS |

## 17. Decision

Phase 5.3 read-only observation: **PASS**.

No rollback is recommended.

Continue production in direct safe-mode:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
```

Phase 6 shadow remains **OFF** and requires separate explicit approval before any live trial.

Queue/hybrid/runtime-buffer production remains **NO-GO**.

## 18. Recommended next step

Recommended next safe step is continued passive monitoring until the next quiet window or next real exam checkpoint.

If further source work is desired, prefer source-only improvements that do not change production state:

```text
add a reusable read-only observation helper script
improve tests proving final submit ignores Redis shadow
improve aggregate metrics for retryable direct-mode 503 cases
prepare rollback drill documentation
```
