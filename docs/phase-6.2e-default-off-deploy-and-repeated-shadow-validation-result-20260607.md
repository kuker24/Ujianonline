# Phase 6.2e Default-OFF Deploy and Repeated Shadow Validation Result

Date: 2026-06-07

## 1. GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
head reviewed before deploy/validation: ef0945e28e77bb67cb044d36a77eef9ebb2902d9
message: docs: record phase 6.2e shadow refresh observability fix
new commits before work: none
```

## 2. Operator instruction

Operator requested:

```text
1. Deploy observability fix default-OFF.
2. Jalankan repeated shadow validation 3–5 synthetic sessions.
3. Kalau semua mismatch=0 sebelum/sesudah final submit, baru rancang Phase 6.3 repeated validation report.
4. Tetap belum queue/hybrid production.
```

Scope applied:

```text
source-only default-OFF deploy
3 synthetic sessions
session allowlist only
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
no Phase 6 production activation
no queue/hybrid activation
no DB migration
no APK touch
no DB/Redis/PgBouncer restart
```

## 3. Source validation before deploy

Environment:

```text
SECRET_KEY=test-secret-key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test
```

Results:

```text
python -m compileall app: PASS
pytest tests/test_final_submit_shadow_refresh_logging.py -q: 4 passed
pytest tests/test_final_submit_shadow_refresh_best_effort.py -q: 4 passed
pytest tests/test_answer_runtime_buffer_post_final_refresh.py -q: 4 passed
pytest tests/test_answer_runtime_buffer_shadow.py -q: 10 passed
pytest tests/test_answer_runtime_buffer_consistency.py -q: 3 passed
pytest tests/test_production_readiness_defaults.py -q: 7 passed
pytest tests/test_final_submit_service.py -q: 6 passed
python -m py_compile scripts/runtime_buffer_consistency_check.py: PASS
runtime_buffer_consistency_check.py --help: PASS
git diff --check: PASS
FORBIDDEN_ARTIFACT_CHECK=PASS
```

## 4. VPS preflight before deploy

Timestamp:

```text
PHASE62C_PREFLIGHT_TS=20260607T112116Z
```

Preflight result:

```text
local_health_http=200
public_health_http=200
all app containers=running/healthy
DB=healthy
Redis=PONG/healthy
PgBouncer=healthy
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
rejected_connections=0
evicted_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
EFFECTIVE_DEFAULT_OFF=PASS
PHASE62C_PREFLIGHT_PASS
```

Note:

```text
runtime_shadow_keys=3 from prior synthetic Phase 6.2d TTL keys. No broad Redis deletion was performed.
```

## 5. Phase 6.2e default-OFF deploy

Deploy timestamp:

```text
PHASE62E_DEPLOY_TS=20260607T112205Z
```

Backup directory:

```text
/root/ujian_online_backups/phase-6.2e-shadow-refresh-observability-20260607T112205Z
```

Files deployed:

```text
app/services/answer_runtime_buffer.py
app/services/final_submit_service.py
```

Files not deployed:

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

Checksums:

```text
pre answer_runtime_buffer.py: f9e91955bbd5005cf0a3590ae35ed9394893343eddb2d1492df70550adeb28bd
pre final_submit_service.py: 7199b64458cbe4d969ba558e2db988c1c292e698f3135fa06f064900da5dc37d

source answer_runtime_buffer.py: 04cea58b2378afcbbb8215219f8abea85487c2a530978830cf3fa197515b6d22
source final_submit_service.py: 7d28ef0e2aa26f224b04828d6ea5a5ef1038f9ec019b1b242a4854b2306ad7da

post answer_runtime_buffer.py: 04cea58b2378afcbbb8215219f8abea85487c2a530978830cf3fa197515b6d22
post final_submit_service.py: 7d28ef0e2aa26f224b04828d6ea5a5ef1038f9ec019b1b242a4854b2306ad7da
```

Deploy validation:

```text
post SHA == source SHA: PASS
syntax compile in container: PASS
source marker validation: PASS
DEFAULT_OFF_VALIDATE=PASS
```

Restart scope:

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

Services not restarted:

```text
DB
Redis
PgBouncer
Nginx
Celery worker
Celery beat
host machine
```

Data service StartedAt remained unchanged:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

Deploy note:

```text
The deploy script saw a transient idle_in_transaction=1 immediately after app-plane restart. A follow-up read-only diagnostic at 2026-06-07T112947Z showed idle_in_transaction=0 and all gates clean, so validation continued.
```

Post-deploy default-OFF validation:

```text
PHASE62C_PREFLIGHT_TS=20260607T112957Z
local_health_http=200
public_health_http=200
all containers=running/healthy
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false effective
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0 effective
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
shadow_probe=False
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
rejected_connections=0
evicted_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
traceback=0
http_500=0
http_503_409=0
answer_save_errors=0
final_submit_errors=0
queue_hybrid_evidence=0
PHASE62C_PREFLIGHT_PASS
```

## 6. Repeated shadow validation setup

Validation timestamp:

```text
PHASE62E_REPEATED_TS=20260607T113855Z
```

Backup directory:

```text
/root/ujian_online_backups/phase-6.2e-repeated-shadow-validation-20260607T113855Z
```

Pre-validation gates:

```text
health_pre_local=200
health_pre_public=200
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
Redis PONG
rejected_connections=0
evicted_keys=0
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
PRE_ENV_SOURCE_MARKERS=PASS
```

Synthetic scopes:

```text
scope_1: user=***69 exam=***04 session=***97
scope_2: user=***70 exam=***05 session=***98
scope_3: user=***71 exam=***06 session=***99
```

Activation:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=<three exact synthetic session IDs>
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
session_allowlist_size=3
ACTIVATION_ENV_VALIDATE=PASS
```

## 7. Repeated validation results

### Session 1

Answer writes:

```text
s1_submit_q1_http=200
s1_submit_q2_http=200
s1_modify_q1_http=200
s1_batch_q3_http=200
s1_journal_q2_http=200
SHADOW_HASH_ONLY_SESSION=PASS fields=3 ttl_answers=14397 ttl_meta=14397
runtime_answer_buffer_keys_mid=0
answer_queue_keys_mid=0
legacy_answer_queue_keys_mid=0
```

Checker before final submit:

```json
{"checked_answers":6,"checked_sessions":10,"extra_in_redis":0,"missing_in_redis":0,"payload_hash_mismatch":0,"redis_errors":0,"stale_runtime_sessions":0}
```

Final submit and marker:

```text
s1_final_submit_http=200
session_1_final_submit_status=submitted
session_1_refresh_ok_before=0
session_1_refresh_ok_after=1
session_1_refresh_failed_after=0
```

Checker after final submit:

```json
{"checked_answers":6,"checked_sessions":10,"extra_in_redis":0,"missing_in_redis":0,"payload_hash_mismatch":0,"redis_errors":0,"stale_runtime_sessions":0}
```

### Session 2

Answer writes:

```text
s2_submit_q1_http=200
s2_submit_q2_http=200
s2_modify_q1_http=200
s2_batch_q3_http=200
s2_journal_q2_http=200
SHADOW_HASH_ONLY_SESSION=PASS fields=3 ttl_answers=14397 ttl_meta=14397
runtime_answer_buffer_keys_mid=0
answer_queue_keys_mid=0
legacy_answer_queue_keys_mid=0
```

Checker before final submit:

```json
{"checked_answers":9,"checked_sessions":10,"extra_in_redis":0,"missing_in_redis":0,"payload_hash_mismatch":0,"redis_errors":0,"stale_runtime_sessions":0}
```

Final submit and marker:

```text
s2_final_submit_http=200
session_2_final_submit_status=submitted
session_2_refresh_ok_before=1
session_2_refresh_ok_after=2
session_2_refresh_failed_after=0
```

Checker after final submit:

```json
{"checked_answers":9,"checked_sessions":10,"extra_in_redis":0,"missing_in_redis":0,"payload_hash_mismatch":0,"redis_errors":0,"stale_runtime_sessions":0}
```

### Session 3

Answer writes:

```text
s3_submit_q1_http=200
s3_submit_q2_http=200
s3_modify_q1_http=200
s3_batch_q3_http=200
s3_journal_q2_http=200
SHADOW_HASH_ONLY_SESSION=PASS fields=3 ttl_answers=14397 ttl_meta=14397
runtime_answer_buffer_keys_mid=0
answer_queue_keys_mid=0
legacy_answer_queue_keys_mid=0
```

Checker before final submit:

```json
{"checked_answers":12,"checked_sessions":10,"extra_in_redis":0,"missing_in_redis":0,"payload_hash_mismatch":0,"redis_errors":0,"stale_runtime_sessions":0}
```

Final submit and marker:

```text
s3_final_submit_http=200
session_3_final_submit_status=submitted
session_3_refresh_ok_before=2
session_3_refresh_ok_after=3
session_3_refresh_failed_after=0
```

Checker after final submit:

```json
{"checked_answers":12,"checked_sessions":10,"extra_in_redis":0,"missing_in_redis":0,"payload_hash_mismatch":0,"redis_errors":0,"stale_runtime_sessions":0}
```

## 8. Disable and observation

Disable validation:

```text
DISABLE_ENV_VALIDATE=PASS
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false effective
session/exam allowlists empty
queue/hybrid OFF
```

Post-disable gates:

```text
health_post_disable_local=200
health_post_disable_public=200
rejected_connections=0
evicted_keys=0
runtime_shadow_keys_post_disable=9
runtime_answer_buffer_keys_post_disable=0
answer_queue_keys_post_disable=0
legacy_answer_queue_keys_post_disable=0
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
DATA_SERVICE_STARTED_AT_UNCHANGED=PASS
```

30-minute final observation:

```text
health_final_observe_local=200
health_final_observe_public=200
all containers=running/healthy
rejected_connections=0
evicted_keys=0
runtime_shadow_keys_final=9
runtime_answer_buffer_keys_final=0
answer_queue_keys_final=0
legacy_answer_queue_keys_final=0
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Final log aggregate:

```text
final_observe_traceback=0
final_observe_connection_does_not_exist=0
final_observe_broken_pipe=0
final_observe_http_500=0
final_observe_http_503_409=0
final_observe_queue_hybrid_evidence=0
final_observe_runtime_shadow_evidence=0
final_observe_answer_save_errors=0
final_observe_final_submit_errors=0
final_observe_shadow_refresh_ok=0
final_observe_shadow_refresh_failed=0
```

Note:

```text
runtime_shadow_keys_final=9 are exact synthetic hash-only shadow keys with TTL. No broad Redis deletion was performed.
```

## 9. Forbidden artifact check

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

## 10. Final decision

```text
Phase 6.2e observability default-OFF deploy: PASS
Repeated shadow validation sessions: 3/3 PASS
Checker-before mismatch=0: YES for all 3 sessions
Checker-after mismatch=0: YES for all 3 sessions
Post-final log marker visible: YES, increased 0→1→2→3
Shadow disabled after validation: YES
Queue/hybrid enabled: NO
Runtime buffer production enabled: NO
Phase 6 production: NO
```

Next step:

```text
Draft Phase 6.3 repeated validation report/plan. Do not enable queue/hybrid production. Phase 6 production remains blocked until Redis policy, worker topology, forced flush proof, and a separate approved production canary plan are complete.
```
