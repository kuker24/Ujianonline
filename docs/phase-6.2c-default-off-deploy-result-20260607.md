# Phase 6.2c Default-OFF Deploy Result

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
head reviewed before deploy: d757de7f0687b97672a019aa0a2d3e9b208b1d3c
message: docs: record phase 6.2c post-final shadow refresh fix
```

## 2. New commits before deploy

```text
new commits after d757de7f0687b97672a019aa0a2d3e9b208b1d3c: none
```

Reviewed before deploy:

```text
answer_runtime_buffer.py: Phase 6.2c post-final hash-only refresh present, default gated
final_submit_service.py: best-effort post-commit refresh hook present
answer_sync_service.py: no queue/hybrid activation
config/env/compose: no production activation changes deployed
DB migration/schema: none
APK/AAB/keystore/.env/backup/dump/CSV/raw token/PII/raw answer artifacts: none
```

## 3. Operator approval text

The task prompt contained the required deploy approval text:

```text
approve deploy Phase 6.2c post-final shadow refresh fix default-off
```

Scope approved:

```text
source-only default-OFF deploy
no shadow trial activation
no queue/hybrid/runtime-buffer production activation
app-plane restart only
no DB/Redis/PgBouncer restart
```

## 4. Source review

Confirmed in source before deploy:

```text
refresh_runtime_answer_shadow_from_db exists
no-op when shadow disabled
no-op when session/exam not allowlisted/selected
reads committed PostgreSQL answers for one session only
writes only question_id, payload_hash, updated_at in Redis answer hash
writes safe meta only
maintains TTL
catches helper/DB/Redis exceptions and returns sanitized failure status
```

Final submit review:

```text
PostgreSQL commit happens first in _finalize_and_commit()
_after_submit_best_effort() runs after commit
post-submit shadow refresh is wrapped best-effort
Redis refresh failure cannot fail final submit
final submit does not read Redis shadow keys
Redis shadow is not source-of-truth
```

No raw content is stored by the post-final shadow refresh:

```text
no raw answer text
no selected option raw payload
no raw metadata object
no username/full name/email/phone
no token/session token
```

## 5. Source tests

Environment:

```text
SECRET_KEY=test-secret-key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test
```

Results:

```text
python -m compileall app
PASS

pytest tests/test_answer_runtime_buffer_shadow.py -q
10 passed

pytest tests/test_answer_runtime_buffer_consistency.py -q
3 passed

pytest tests/test_answer_runtime_buffer_post_final_refresh.py -q
4 passed

pytest tests/test_final_submit_shadow_refresh_best_effort.py -q
4 passed

pytest tests/test_production_readiness_defaults.py -q
7 passed

pytest tests/test_answer_sync_service_routing.py -q
25 passed

pytest tests/test_final_submit_service.py -q
6 passed

python -m py_compile scripts/runtime_buffer_consistency_check.py
PASS

SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test python scripts/runtime_buffer_consistency_check.py --help
PASS

git diff --check
PASS
```

Forbidden artifact check before deploy:

```text
FORBIDDEN_ARTIFACT_CHECK=PASS
```

## 6. VPS preflight

Preflight timestamp:

```text
PHASE62C_PREFLIGHT_TS=20260607T084732Z
```

Health:

```text
local_health_http=200
public_health_http=200
all app containers=running/healthy
DB=running/healthy
PgBouncer=running/healthy
Redis=running/healthy/PONG
Nginx=running/healthy
Celery worker/beat=running/healthy
```

Effective settings before deploy:

```text
ANSWER_WRITE_MODE_effective=direct
ANSWER_QUEUE_ENABLED_effective=False
ANSWER_QUEUE_PERCENTAGE_effective=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED_effective=False
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE_effective=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS_effective=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS_effective=
session_allowlist=set()
exam_allowlist=set()
shadow_probe=False
EFFECTIVE_DEFAULT_OFF=PASS
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
rejected_connections=0
evicted_keys=0
runtime_shadow_keys=7
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

Note:

```text
runtime_shadow_keys=7 are old synthetic Phase 6 test TTL keys. No broad Redis deletion was performed.
```

Log aggregate before deploy:

```text
traceback=0
http_500=0
http_503_409=0
answer_save_errors=0
final_submit_errors=0
queue_hybrid_evidence=0
```

Preflight result:

```text
PHASE62C_PREFLIGHT_PASS
```

## 7. Files deployed

Only these runtime source files were deployed:

```text
app/services/answer_runtime_buffer.py
app/services/final_submit_service.py
```

## 8. Files explicitly not deployed

```text
.env
.env.*
docker-compose.production.yml
tests
docs as runtime files
APK/AAB
keystore/JKS/key.properties/local.properties
DB dump/backup/sql/sqlite/db
CSV/session artifacts
raw token/secret files
```

## 9. Backup directory

```text
/root/ujian_online_backups/phase-6.2c-post-final-shadow-refresh-20260607T084932Z
```

## 10. Pre/source/post checksums

Pre-deploy live checksums:

```text
46d736003427e477ffd9d29d2dcb2da03daa7b6e3a22005b3ebad1355cba7be0  app/services/answer_runtime_buffer.py
d2eb6754cccae2a5c5d7b582af49196fb9c75fad3b1a161da24a15df202f3ddb  app/services/final_submit_service.py
```

Source checksums uploaded to VPS:

```text
f9e91955bbd5005cf0a3590ae35ed9394893343eddb2d1492df70550adeb28bd  /tmp/phase62c_answer_runtime_buffer.py
7199b64458cbe4d969ba558e2db988c1c292e698f3135fa06f064900da5dc37d  /tmp/phase62c_final_submit_service.py
```

Post-deploy live checksums:

```text
f9e91955bbd5005cf0a3590ae35ed9394893343eddb2d1492df70550adeb28bd  app/services/answer_runtime_buffer.py
7199b64458cbe4d969ba558e2db988c1c292e698f3135fa06f064900da5dc37d  app/services/final_submit_service.py
```

Checksum validation:

```text
source_answer_sha == post_answer_sha: PASS
source_final_sha == post_final_sha: PASS
```

Owner/mode preserved:

```text
app/services/answer_runtime_buffer.py pre owner=root:root mode=644
app/services/final_submit_service.py pre owner=ubuntu:ubuntu mode=644
```

Syntax validation in container:

```text
COMPILE_OK /app/app/services/answer_runtime_buffer.py
COMPILE_OK /app/app/services/final_submit_service.py
```

## 11. Restart scope

Restarted/recreated app-plane only, one by one:

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

Each app-plane service returned:

```text
service state=running
health=healthy
local /health=200
public /health=200
```

## 12. Services not restarted

Not restarted/recreated:

```text
DB
Redis
PgBouncer
Nginx
Celery worker
Celery beat
Prometheus
Grafana
host machine
```

Data service StartedAt stayed unchanged:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

## 13. Effective env after restart

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
shadow_probe=False
DEFAULT_OFF_VALIDATE=PASS
```

## 14. Default-OFF validation

Default-OFF remained intact:

```text
shadow trial activated: NO
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true set: NO
session/exam allowlist set: NO
percentage rollout: NO
queue/hybrid enabled: NO
Redis runtime buffer production keys: 0
answer queue keys: 0
```

Redis after deploy:

```text
PONG
rejected_connections=0
evicted_keys=0
runtime_shadow_keys=7
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

## 15. Source marker validation

Live source markers after deploy:

```text
marker_refresh_runtime_answer_shadow_from_db=True
marker_SHADOW_POST_FINAL_REFRESH_SKIPPED=True
marker_SHADOW_POST_FINAL_REFRESH_OK=True
marker_SHADOW_POST_FINAL_REFRESH_FAILED=True
SOURCE_MARKER_VALIDATE=PASS
```

Final submit forbidden Redis shadow read markers:

```text
final_submit_forbidden_shadow_session_answers_key=False
final_submit_forbidden_runtime:answer_shadow=False
final_submit_forbidden_.hgetall(=False
final_submit_forbidden_.hget(=False
final_submit_forbidden_.smembers(=False
```

Commit/best-effort sequence marker:

```text
await self.db.commit(): present
await self._after_submit_best_effort(session, finalize_result.percentage): present
```

## 16. Error/log aggregate

Post-deploy log aggregate since 10 minutes:

```text
traceback=0
connection_does_not_exist=0
broken_pipe=0
http_500=0
http_503_409=0
answer_save_errors=0
final_submit_errors=0
queue_hybrid_evidence=0
runtime_shadow_evidence=0
```

Post-deploy DB gates:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

## 17. Forbidden artifact check

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

## 18. Rollback path

Rollback files are available in:

```text
/root/ujian_online_backups/phase-6.2c-post-final-shadow-refresh-20260607T084932Z/app/services/answer_runtime_buffer.py
/root/ujian_online_backups/phase-6.2c-post-final-shadow-refresh-20260607T084932Z/app/services/final_submit_service.py
```

Rollback action if needed:

```text
copy both backup files back to /root/ujian_online/app/services/
restore owner/mode
recreate app-plane only: api_admin, api_admin2, api, api2, api3, api4, api5, api6, api7, api8
keep DB/Redis/PgBouncer untouched
keep shadow disabled
```

## 19. Final decision

```text
Phase 6.2c default-OFF fix deploy: PASS
Shadow trial activated: NO
Queue/hybrid enabled: NO
Phase 6 production: NO
Ready to request retry shadow trial: YES
```

Next step:

```text
Request separate explicit approval before any retry:
approve Phase 6.2c retry shadow trial for test exam only
```

The future retry must remain one synthetic session, session allowlist only, direct mode, queue disabled, shadow percentage 0, with checker-before and checker-after both requiring payload_hash_mismatch=0.
