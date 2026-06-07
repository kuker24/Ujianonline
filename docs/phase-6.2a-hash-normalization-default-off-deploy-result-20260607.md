# Phase 6.2a Hash Normalization Default-OFF Deploy Result

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
head reviewed before deploy: e04e35077f6cfebf436d13ad6d6906c5475194ea
message: docs: record phase 6.2 shadow trial result
```

## 2. New commits before deploy

```text
new commits after e04e35077f6cfebf436d13ad6d6906c5475194ea: none
```

Reviewed areas:

```text
app/services/answer_runtime_buffer.py: hash normalization patch present
app/services/answer_sync_service.py: no new production activation reviewed
app/services/final_submit_service.py: no Redis shadow dependency added
tests: numeric hash regression present
docs: Phase 6.2 failed trial result present
queue/hybrid activation: none
env/config/compose production activation: none
DB migration/schema change: none
APK/AAB/keystore/.env/backup/dump/CSV/raw token/PII artifacts: none
```

## 3. Operator approval

Approval received exactly:

```text
approve deploy Phase 6.2a hash normalization fix default-off
```

Scope approved:

```text
source-only default-OFF deploy
no shadow trial activation
no retry shadow trial
no queue/hybrid
no DB migration
no APK touch
no DB/Redis/PgBouncer restart
```

## 4. Source review

Reviewed files:

```text
app/services/answer_runtime_buffer.py
tests/test_answer_runtime_buffer_shadow.py
docs/phase-6.2-shadow-trial-result-20260607.md
```

Confirmed:

```text
answer_payload_hash() now uses _canonical_numeric_string() for points_earned.
Decimal('0.00'), Decimal('0.0'), 0.0, and 0 hash equivalently.
Decimal('1.00') and 1.0 hash equivalently.
Decimal('0.50') and 0.5 hash equivalently.
Redis shadow payload remains hash-only.
Shadow remains optional and best-effort.
No final submit Redis dependency was added.
No queue/hybrid path was activated.
Production defaults remain direct/off.
```

## 5. Source tests before deploy

Commands:

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
python -m compileall app: PASS
tests/test_answer_runtime_buffer_shadow.py: 10 passed
tests/test_answer_runtime_buffer_consistency.py: 3 passed
tests/test_production_readiness_defaults.py: 7 passed
tests/test_answer_sync_service_routing.py: 25 passed
runtime_buffer_consistency_check.py py_compile: PASS
runtime_buffer_consistency_check.py --help: PASS
git diff --check: PASS
forbidden artifact check: PASS
```

## 6. VPS preflight

Deploy timestamp:

```text
PHASE62A_DEPLOY_TS=20260607T054136Z
```

Health:

```text
local_health_http=200
public_health_http=200
```

Container health:

```text
api_admin=running/healthy
api_admin2=running/healthy
api=running/healthy
api2=running/healthy
api3=running/healthy
api4=running/healthy
api5=running/healthy
api6=running/healthy
api7=running/healthy
api8=running/healthy
nginx=running/healthy
celery_worker=running/healthy
celery_beat=running/healthy
db=running/healthy
redis=running/healthy
pgbouncer=running/healthy
prometheus=running/healthy
grafana=running/healthy
```

DB/PgBouncer/Redis gates:

```text
DB pg_isready: accepting connections
PgBouncer pg_isready: accepting connections
Redis PING: PONG
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
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

Preflight effective env:

```text
ANSWER_WRITE_MODE=direct | settings.answer_write_mode=direct
ANSWER_QUEUE_ENABLED=false | settings.answer_queue_enabled=False
ANSWER_QUEUE_PERCENTAGE=0 | settings.answer_queue_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=UNSET | settings.answer_runtime_buffer_shadow_enabled=False
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=UNSET | settings.answer_runtime_buffer_shadow_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=UNSET | settings.answer_runtime_buffer_shadow_session_ids=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=UNSET | settings.answer_runtime_buffer_shadow_exam_ids=
shadow_probe_false=True
```

Note:

```text
Two earlier deploy-script invocations stopped during preflight due script parsing/quoting bugs before file copy/restart.
No live file was copied and no app-plane restart was performed in those stopped attempts.
The successful run was 20260607T054136Z.
```

## 7. File deployed

Only this file was deployed:

```text
app/services/answer_runtime_buffer.py
```

## 8. Files explicitly not deployed

Not deployed/touched:

```text
.env / .env.*
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
/root/ujian_online_backups/phase-6.2a-hash-normalization-20260607T054136Z
```

Backup file:

```text
/root/ujian_online_backups/phase-6.2a-hash-normalization-20260607T054136Z/answer_runtime_buffer.py
```

Owner/mode preserved after copy.

## 10. Checksums

Pre/live before copy:

```text
6143d9e078ea54c033caae0d1cf0fe7a6b649ec2ce86e55ed402f214db249e37  /root/ujian_online/app/services/answer_runtime_buffer.py
```

Uploaded source:

```text
46d736003427e477ffd9d29d2dcb2da03daa7b6e3a22005b3ebad1355cba7be0  /tmp/phase62a_answer_runtime_buffer.py
```

Post/live after copy:

```text
46d736003427e477ffd9d29d2dcb2da03daa7b6e3a22005b3ebad1355cba7be0  /root/ujian_online/app/services/answer_runtime_buffer.py
```

Result:

```text
post SHA256 == source SHA256: PASS
```

Syntax check in API container:

```text
SYNTAX_COMPILE=PASS
```

## 11. Restart scope

App-plane only, recreated one-by-one with `docker compose -f docker-compose.production.yml up -d --no-deps --force-recreate`:

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

All restarted containers became healthy and local/public `/health` returned 200 after each service.

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
ANSWER_WRITE_MODE=direct | settings.answer_write_mode=direct
ANSWER_QUEUE_ENABLED=false | settings.answer_queue_enabled=False
ANSWER_QUEUE_PERCENTAGE=0 | settings.answer_queue_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=UNSET | settings.answer_runtime_buffer_shadow_enabled=False
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=UNSET | settings.answer_runtime_buffer_shadow_percentage=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=UNSET | settings.answer_runtime_buffer_shadow_session_ids=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=UNSET | settings.answer_runtime_buffer_shadow_exam_ids=
session_allowlist=set()
exam_allowlist=set()
```

## 14. Default-OFF validation

```text
answer_write_mode_direct=True
answer_queue_enabled_false=True
answer_queue_percentage_zero=True
shadow_enabled_false=True
shadow_percentage_zero=True
session_allowlist_empty=True
exam_allowlist_empty=True
shadow_probe_false=True
queue_probe_false=True
DEFAULT_OFF_VALIDATE=PASS
```

Redis/queue post-deploy gates:

```text
rejected_connections=0
evicted_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

## 15. Numeric hash normalization marker validation

In-container validation with `python -B`:

```text
NUMERIC_HASH_NORMALIZATION=PASS
```

Checks performed:

```text
_canonical_numeric_string(Decimal('0.00')) == '0'
_canonical_numeric_string(Decimal('0.0')) == '0'
_canonical_numeric_string(0.0) == '0'
_canonical_numeric_string(0) == '0'
_canonical_numeric_string(Decimal('1.00')) == '1'
_canonical_numeric_string(1.0) == '1'
_canonical_numeric_string(Decimal('0.50')) == '0.5'
_canonical_numeric_string(0.5) == '0.5'
answer_payload_hash(Decimal('0.00')) == answer_payload_hash(0.0)
answer_payload_hash(Decimal('0.0')) == answer_payload_hash(0)
answer_payload_hash(Decimal('1.00')) == answer_payload_hash(1.0)
answer_payload_hash(Decimal('0.50')) == answer_payload_hash(0.5)
```

## 16. Error/log aggregate

App logs since deploy:

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

## 17. Forbidden artifact check

Result before deploy:

```text
PASS
```

No committed/copied runtime artifacts:

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

If rollback is required:

```bash
cd /root/ujian_online
cp -a /root/ujian_online_backups/phase-6.2a-hash-normalization-20260607T054136Z/answer_runtime_buffer.py \
  /root/ujian_online/app/services/answer_runtime_buffer.py
# preserve original owner/mode if needed from backup metadata
for svc in api_admin api_admin2 api api2 api3 api4 api5 api6 api7 api8; do
  docker compose -f docker-compose.production.yml up -d --no-deps --force-recreate "$svc"
  curl -fsS http://127.0.0.1/health
  curl -fsS https://man1rokanhulu.cloud/health
done
```

Rollback scope remains app-plane only. Do not restart DB/Redis/PgBouncer.

## 19. Final decision

```text
Phase 6.2a default-OFF fix deploy: PASS
Shadow trial activated: NO
Queue/hybrid enabled: NO
Phase 6 production: NO
Ready to request retry shadow trial: YES, gated by separate operator approval
```

Next approval text for a future task only:

```text
approve Phase 6.2 retry shadow trial for test exam only
```

Retry constraints for future task:

```text
one synthetic test session
session allowlist only
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
final submit only after consistency checker reports payload_hash_mismatch=0
```
