# Phase 6.2b Allowlisted Shadow Retry Result

Date: 2026-06-07

## 1. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
head reviewed before trial: 8c913ff1429e8f512f6f46503d1861da3616601c
message: docs: record phase 6.2a hash normalization deploy result
```

## 2. New commits before trial

```text
new commits after 8c913ff1429e8f512f6f46503d1861da3616601c: none
```

Reviewed areas:

```text
answer_runtime_buffer.py: Phase 6.2a numeric normalization deployed on VPS
answer_sync_service.py: no queue/hybrid activation reviewed
final_submit_service.py: no Redis shadow source-of-truth dependency reviewed
config/env/compose: no production queue/hybrid activation before trial
DB migration/schema change: none
APK/AAB/keystore/.env/backup/dump/CSV/raw token/PII artifacts: none
```

## 3. Operator approval text

The task prompt contained the required retry approval text:

```text
approve Phase 6.2 retry shadow trial for test exam only
```

Scope applied:

```text
one synthetic test session only
session allowlist only
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
no percentage rollout
no production load-test
no APK touch
no DB migration
no DB/Redis/PgBouncer restart
```

## 4. Pre-enable gates

Trial timestamp:

```text
PHASE62_TRIAL_TS=20260607T055916Z
```

Backup directory:

```text
/root/ujian_online_backups/phase-6.2-shadow-trial-20260607T055916Z
```

Health:

```text
local_health_http=200
public_health_http=200
all containers=running/healthy
DB=healthy
PgBouncer=healthy
Redis=PONG
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
runtime_shadow_keys=5
runtime_answer_buffer_keys=0
answer_queue_keys=0
legacy_answer_queue_keys=0
```

Old shadow key verification:

```text
PRE_EXISTING_SHADOW_KEYS_TEST_ONLY=PASS count=5 sessions=2
```

Interpretation:

```text
Old runtime shadow keys were known synthetic Phase 6 test TTL keys only.
No broad Redis deletion was performed.
```

Effective env before activation:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false effective
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0 effective
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Data service StartedAt before trial:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

## 5. Synthetic test scope

Synthetic prefixes:

```text
exam prefix: __PHASE6_SHADOW_TEST__
account prefix: __PHASE6_SHADOW_TEST__
```

Sanitized scope:

```text
test user: ***67
test exam: ***02
test session: ***95
questions: 3
```

Safety properties:

```text
exam unpublished / not visible to real students
one synthetic student account
one synthetic test session
no real student PII printed
no raw answer values printed
no raw token/session token printed
```

## 6. Env changes made

Live compose was backed up and temporarily edited in the `x-api-service` environment anchor only.

Compose checksum before activation:

```text
b375cd474fd5e88d0c1ee44d46f59a4dcb2df91ded8f192d9b499e7ecb3e90d4  docker-compose.production.yml
```

Temporary activation values:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=true
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=<exact synthetic test session ID>
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Unchanged safety values:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
```

Activation validation:

```text
answer_write_mode=direct
answer_queue_enabled=False
answer_queue_percentage=0
shadow_enabled=True
shadow_percentage=0
session_allowlist_size=1
exam_allowlist_size=0
expected_session_allowlisted=True
probe_expected=True
ACTIVATION_ENV_VALIDATE=PASS
```

## 7. Restart/recreate scope

App-plane only, one-by-one:

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

Each app-plane recreate returned local `/health=200`.

## 8. Services not restarted

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

Data service StartedAt remained unchanged through final observation:

```text
db        2026-06-06T04:27:40.732547151Z
redis     2026-06-06T04:27:39.367061352Z
pgbouncer 2026-06-06T04:27:38.009982103Z
```

## 9. Answer save results

Controlled synthetic answer writes:

```text
submit_q1_http=200
submit_q2_http=200
modify_q1_http=200
batch_q3_http=200
journal_q2_http=200
```

Included a wrong answer path to validate the previous numeric zero mismatch class.

## 10. Redis shadow key validation

Redis shadow validation after answer writes:

```text
SHADOW_HASH_ONLY=PASS fields=3 ttl_answers=14397 ttl_meta=14397 shadow_key_count=7
runtime_shadow_keys_after_answers=7
runtime_answer_buffer_keys_after_answers=0
answer_queue_keys_after_answers=0
legacy_answer_queue_keys_after_answers=0
```

Confirmed:

```text
Redis shadow values contain only question_id, payload_hash, updated_at.
No raw answer text.
No raw selected option payload fields.
No username/full name.
No token/session token.
TTL present.
No runtime answer buffer production keys.
No answer queue keys.
```

## 11. Consistency checker output

Checker before final submit:

```json
{
  "checked_answers": 3,
  "checked_sessions": 10,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 0,
  "redis_errors": 0,
  "stale_runtime_sessions": 2
}
```

Result before final submit:

```text
CHECKER_BEFORE_VALIDATE=PASS
mismatch before final submit: 0
```

Checker after final submit:

```json
{
  "checked_answers": 3,
  "checked_sessions": 10,
  "extra_in_redis": 0,
  "missing_in_redis": 0,
  "payload_hash_mismatch": 2,
  "redis_errors": 0,
  "stale_runtime_sessions": 2
}
```

Result after final submit:

```text
payload_hash_mismatch=2
checker_exit=2
```

Decision:

```text
Phase 6.2b shadow retry: FAIL
Do not retry blindly.
Do not proceed to Phase 6 production.
```

## 12. Final submit result

Final submit was executed only after checker-before passed with mismatch 0.

```text
final_submit_http=200
final_submit_status=submitted
```

After final submit, checker-after failed with mismatch 2.

Interpretation:

```text
The Phase 6.2a numeric normalization patch fixed the pre-final Decimal/float mismatch class.
A separate post-final staleness mismatch remains: final submit/grading changes the DB answer payload after the Redis shadow hash was recorded.
```

## 13. Sanitized post-final diagnostic

Sanitized diagnostic for the current submitted synthetic session:

```json
{
  "session_mask": "***95",
  "status": "submitted",
  "answer_count": 3,
  "redis_fields": 3,
  "mismatch_count": 2,
  "mismatches": [
    {
      "question_mask": "***12",
      "is_correct": true,
      "points_repr": "Decimal('1.00')",
      "points_type": "Decimal",
      "metadata_keys": [
        "client_event_id",
        "client_local_timestamp_ms",
        "client_sequence",
        "phase",
        "step",
        "sync_source"
      ],
      "selected_option_present": true,
      "selected_option_ids_count": 0,
      "answer_text_present": false,
      "redis_hash_present": true
    },
    {
      "question_mask": "***13",
      "is_correct": true,
      "points_repr": "Decimal('1.00')",
      "points_type": "Decimal",
      "metadata_keys": ["phase", "step"],
      "selected_option_present": true,
      "selected_option_ids_count": 0,
      "answer_text_present": false,
      "redis_hash_present": true
    }
  ]
}
```

No raw answer values, raw tokens, session tokens, usernames, or full names were printed.

## 14. Disable/rollback result

The shell trap restored the pretrial compose backup immediately after checker-after failure.

```text
== cleanup: restore compose and disable shadow ==
```

App-plane was recreated default-OFF:

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

Synthetic session cleanup update:

```text
UPDATE 0
```

Interpretation:

```text
UPDATE 0 is expected because the synthetic session had already been final-submitted successfully and was no longer active/in_progress.
```

Effective env after cleanup/final observation:

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
shadow_probe=False
```

## 15. Post-disable observation

Observation duration:

```text
30 minutes
```

Final observation timestamp:

```text
PHASE62_READINESS_TS=20260607T063431Z
```

Health and container state:

```text
local_health_http=200
public_health_http=200
all containers=running/healthy
DB=healthy
PgBouncer=healthy
Redis=healthy/PONG
```

DB gates after observation:

```text
active_sessions=0
running_exam_windows=0
final_submit_drain=0
long_active_queries_gt60s=0
idle_in_transaction=0
```

Redis gates after observation:

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
runtime_shadow_keys=7 are old/current synthetic Phase 6 test TTL keys.
No broad Redis deletion was performed.
```

## 16. Error/log aggregate counts

Final observation log aggregate since 15 minutes:

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

Result:

```text
PASS
```

No committed/copied artifacts:

```text
APK/AAB
keystore/JKS/key.properties/local.properties
.env/.env.*
DB dump/backup/sql/sqlite/db
CSV/session artifacts
summary JSON artifacts
raw token/session token/student PII/raw answer content
```

Ephemeral files were used only under `/tmp` and VPS backup directories.

## 18. Final decision

```text
Phase 6.2b shadow retry: FAIL
Mismatch = 0: NO after final submit
Mismatch before final submit: YES
Final submit with shadow observed: YES, HTTP 200/submitted
Queue/hybrid: NO
Runtime buffer production: NO
Phase 6 production: NO
```

## 19. Next step

Do not proceed to Phase 6 production.

Recommended next work:

```text
Implement a source-only/default-OFF fix for post-final shadow staleness.
```

Likely fix direction:

```text
After final submit commits DB answer/grading changes, refresh only the hash-only shadow mirror for the allowlisted session from the committed DB answer state, best-effort, without making final submit depend on Redis and without reading Redis for grading.
```

Required constraints for the next fix:

```text
no Redis source-of-truth
no queue/hybrid activation
no percentage rollout
no final submit failure if Redis shadow refresh fails after DB commit
no raw answer content in Redis
```

After a source patch and controlled default-OFF deploy, a future retry needs separate approval.
