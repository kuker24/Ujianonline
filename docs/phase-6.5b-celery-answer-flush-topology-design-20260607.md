# Phase 6.5b Celery `answer_flush` Topology Design

Date: 2026-06-07

## 1. Purpose and non-goals

### Purpose

Define a safe future Celery topology for answer flush experiments after:

```text
Phase 6.4 five-session shadow validation: PASS
Phase 6.5 infrastructure readiness plan: created
Phase 6.5a Redis answer-critical design: created
```

This design focuses on isolating answer-critical flush work from maintenance/background work before any staging forced-flush proof or production canary is discussed.

Design goals:

```text
protect final submit priority
avoid answer flush starvation by maintenance jobs
keep PostgreSQL as source-of-record
make answer flush tasks idempotent and retry-safe
define worker queues, concurrency, DB budget, and observability
define staging proof gates before any canary proposal
```

### Non-goals

```text
no production activation
no queue activation
no hybrid activation
no runtime buffer production activation
no Celery runtime deployment
no VPS runtime change
no docker-compose runtime change
no .env change
no service restart
no production load-test
no APK change
no DB migration/schema change
```

Production must remain:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

## 2. Current Celery baseline

### 2.1 Current source topology

`docker-compose.production.yml` currently defines one Celery worker service:

```text
service: celery_worker
command: celery -A app.tasks.scheduler worker --loglevel=warning --pool=solo --max-tasks-per-child=200
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=4
DB_READ_POOL_SIZE=2
DB_READ_MAX_OVERFLOW=4
memory limit=512M
broker/backend: Redis DB 1 via settings.redis_url.replace('/0', '/1')
```

`app/tasks/scheduler.py` includes these task modules:

```text
app.tasks.answer_processor
app.tasks.views_refresher
app.tasks.partition_maintenance
app.tasks.dr_drill
```

Current beat schedule includes:

```text
process-answer-queue-rapid every 5 seconds
refresh-analytics-views every 300 seconds
close-expired-sessions every 30 seconds
maintain-exam-log-partitions daily
run-disaster-recovery-drill weekly
scheduled publication checks every 60 seconds
```

### 2.2 Current live audit from Phase 6.4

```text
pool implementation=celery.concurrency.solo:TaskPool
max-concurrency=1
prefetch_count=4
runtime_answer_queue_keys=0
legacy_answer_queue_keys=0
celery_keys=0
kombu_keys=0
```

### 2.3 Current answer-related code paths

Legacy queue worker:

```text
app/tasks/answer_processor.py
PENDING_QUEUE_KEY=answer_queue:pending
PROCESSING_QUEUE_KEY=answer_queue:processing
PROCESS_LOCK_KEY=answer_queue:processing:lock
```

The legacy worker has an explicit production guard comment stating it must not be enabled for student traffic until it is proven to match current `AnswerSyncService` semantics.

Runtime buffer flush path:

```text
app/services/answer_runtime_buffer.py
PENDING_QUEUE_KEY=runtime:answer_queue:pending
PROCESSING_QUEUE_KEY=runtime:answer_queue:processing
flush_runtime_answer_buffer_for_session(...)
flush_runtime_answer_buffer_once(...)
answer_runtime_buffer_drain_loop(...)
```

Final submit pre-flush hook:

```text
app/services/final_submit_service.py
legacy queue pre-flush only when ANSWER_WRITE_MODE=queue and ANSWER_QUEUE_FLUSH_ON_SUBMIT=true
runtime buffer pre-flush only when is_runtime_answer_buffer_enabled()
runtime buffer pre-flush failure returns controlled 503 Retry-After
```

Current production remains direct mode, so these paths are guarded/off.

## 3. Why current `solo` worker blocks answer flush production

`pool=solo` and `max-concurrency=1` are intentionally simple but insufficient for answer-critical flushing.

Blockers:

```text
one task at a time for all Celery workloads
answer flush can be blocked by scheduled publications, analytics refresh, partition maintenance, DR drill, or close-expired-sessions
no dedicated answer queue capacity
no answer-specific prefetch/backpressure tuning
no separate health/readiness signal for answer flush
no production-like forced-flush proof under backlog/restart/reconnect conditions
```

Production decision:

```text
Current Celery topology is not ready for queue/hybrid answer writes.
Queue/hybrid production remains NO.
```

## 4. Preferred target topology

Preferred future topology splits Celery workers by responsibility.

### 4.1 `celery_worker_maintenance`

Purpose:

```text
scheduled publication tasks
close expired sessions
analytics view refresh
daily partition maintenance
DR drill
other non-answer background jobs
```

Characteristics:

```text
can retain conservative pool if stable
must not consume answer_flush queue
can have lower priority than answer-critical work
can be restarted without affecting answer flush capacity
```

Suggested queue binding:

```text
queues: maintenance, default
```

### 4.2 `celery_worker_answer_flush`

Purpose:

```text
answer runtime buffer flush only
answer forced-flush support only
answer queue backlog drain in staging/canary only if approved
```

Characteristics:

```text
dedicated queue: answer_flush
must not run heavy export/analytics/maintenance tasks
concurrency explicitly set and measured
prefetch_multiplier=1
bounded DB pool coordinated with PgBouncer
sanitized logging only
strict health and backlog metrics
```

Initial staging candidate:

```text
pool=prefork or threads after compatibility test
concurrency=2 for first staging proof
prefetch_multiplier=1
max_tasks_per_child bounded, e.g. 100-500
soft/hard task time limits defined after measurement
```

Production candidate is not approved; staging must prove values before any production proposal.

### 4.3 `celery_beat`

Purpose:

```text
schedule periodic tasks only
```

Rules:

```text
beat must route answer flush periodic tasks to answer_flush queue only
maintenance schedules must route to maintenance/default queue only
beat must not perform heavy work itself
```

## 5. Queue routing design

Future routing should be explicit, not implicit.

Proposed logical queues:

```text
answer_flush      answer-critical flush tasks only
maintenance       scheduled publications, close-expired-sessions, partition maintenance, DR drill
default           low-risk fallback only; should not receive answer-critical tasks
```

Proposed task-to-queue mapping:

| Task family | Queue | Worker |
| --- | --- | --- |
| runtime answer buffer flush | `answer_flush` | `celery_worker_answer_flush` |
| final-submit forced async helper, if ever added | `answer_flush` | `celery_worker_answer_flush` |
| legacy `process_answer_queue`, if retained for staging only | `answer_flush` after semantic proof | `celery_worker_answer_flush` |
| scheduled publications | `maintenance` | `celery_worker_maintenance` |
| close expired sessions | `maintenance` | `celery_worker_maintenance` |
| analytics view refresh | `maintenance` | `celery_worker_maintenance` |
| partition maintenance | `maintenance` | `celery_worker_maintenance` |
| DR drill | `maintenance` | `celery_worker_maintenance` |

Routing acceptance gate:

```text
No task in answer_flush queue may perform heavy maintenance/export/analytics work.
No answer-critical task may rely on default queue routing.
```

## 6. Redis and broker considerations

Current Celery broker/backend uses Redis DB 1 derived from `REDIS_URL`.

Future design must decide whether Celery broker remains on cache Redis or moves to a broker aligned with answer-critical isolation.

Rules:

```text
Celery broker availability must not be confused with answer durability
Redis broker message presence is not answer source-of-truth
answer-critical Redis from Phase 6.5a must use noeviction if it stores answer-critical coordination state
PostgreSQL/durable journal remains required for acknowledged answer safety
```

Preferred split:

```text
redis_cache or celery broker Redis: Celery broker/cache workload
redis_answers: answer runtime buffer/flush coordination and metrics only
PostgreSQL: answer source-of-record / durable journal if future queue ack semantics require it
```

Do not treat Celery broker messages as durable student answer state without separate proof and design approval.

## 7. DB and PgBouncer budget

Current worker DB environment:

```text
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=4
DB_READ_POOL_SIZE=2
DB_READ_MAX_OVERFLOW=4
DB_POOL_TIMEOUT=20
```

Answer flush workers must be sized against PgBouncer and DB capacity.

Initial staging budget proposal:

```text
answer_flush concurrency=2
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=2
prefetch_multiplier=1
one session-scoped flush transaction per active task
```

Do not increase concurrency until these remain clean:

```text
DB long active queries=0
idle_in_transaction=0
PgBouncer wait not elevated
final submit latency acceptable
answer checker mismatch=0
queue drains to zero
```

Production canary, if ever proposed, must include an explicit DB connection budget across:

```text
api replicas
api_admin replicas
celery_worker_maintenance
celery_worker_answer_flush
celery_beat
PgBouncer max client/default pool/reserve pool limits
PostgreSQL max_connections
```

## 8. Answer flush task contract

Any future `answer_flush` task must satisfy this contract before staging proof:

```text
session-scoped or bounded batch scope
idempotent by session_id + question_id + answer version/update timestamp where possible
latest valid answer wins
partial batch failure rolls back DB transaction
processing item is restored or safely deadlettered on failure
raw answers/tokens/PII are not logged
DB commit is the only completed durable answer state
flush can be retried without duplicate answer rows or incorrect grading
```

For runtime buffer flush:

```text
claim session from runtime:answer_queue:pending to runtime:answer_queue:processing
load dirty question IDs
load buffered payloads
acquire DB session write lock
upsert/update PostgreSQL answers
commit
remove flushed dirty question IDs
ack session only when dirty set is empty
restore session to pending if dirty remains or task fails before completion
```

Deadletter criteria must be explicit:

```text
poison payload cannot parse
session does not exist and cannot recover
session is no longer eligible and policy says drop/ack
repeated DB failure exceeds bounded retry limit
```

Deadletter content must be sanitized and should avoid raw answer values.

## 9. Final submit priority design

Final submit remains highest priority.

Rules:

```text
final submit must not wait behind general Celery backlog
final submit must not grade from volatile Redis-only state
final submit must force/verify durable answer state before grading
if durable state cannot be verified, return controlled 503 Retry-After
```

Current code already has guarded pre-flush hooks:

```text
legacy queue pre-flush only in queue mode with ANSWER_QUEUE_FLUSH_ON_SUBMIT
runtime buffer pre-flush only when runtime buffer is enabled
runtime buffer pre-flush failure raises 503 Retry-After
```

Future design preference:

```text
final submit session-scoped flush should remain in-process/direct-priority when needed
background answer_flush worker is for normal draining, not for blocking final-submit behind backlog
```

If final submit delegates any work to Celery in the future, it must have:

```text
priority queue
short timeout
strict fallback/fail-safe behavior
proof that it cannot starve behind background tasks
```

## 10. Observability

Required Celery metrics:

```text
worker online/offline by worker name
pool implementation
concurrency
prefetch_count
queue depth per queue
oldest pending age per queue
processing count
processing oldest age
retry count
failure count by class
deadletter count
task runtime p50/p95/p99
worker memory
worker restarts
```

Required answer-specific metrics:

```text
answer_flush pending sessions
answer_flush processing sessions
answer_flush deadletter count
answer_flush rows flushed
answer_flush sessions flushed
answer_flush no-op rows
answer_flush DB rollback count
answer_flush Redis restore count
answer_flush latency p50/p95/p99
final submit forced flush duration
final submit forced flush failures
```

Required safety checker metrics:

```text
payload_hash_mismatch
redis_errors
missing_in_redis
extra_in_redis
runtime_answer_buffer_keys_count
answer_queue_keys_count
legacy_answer_queue_keys_count
shadow_keys_without_ttl
post_final_refresh_missing_count
shadow_validation_summary.py output
runtime_buffer_consistency_check.py output
```

Critical alert examples:

```text
answer_flush queue oldest age above SLA
answer_flush deadletter count > 0
answer_flush worker offline during approved staging/canary
payload_hash_mismatch > 0
redis_errors > 0
DB long active queries > 0 after flush window
idle_in_transaction > 0 after flush window
final submit forced flush failure > 0
```

## 11. Failure behavior

| Failure | Expected behavior | Student safety rule |
| --- | --- | --- |
| answer_flush worker offline | direct mode unaffected; staging/canary queue mode must disable or fail safely | no fake saved |
| worker restart during backlog | processing items restored or retried idempotently | no duplicate DB answer rows |
| task timeout | rollback DB transaction; restore pending or deadletter after bounded retries | no partial durable state |
| DB pressure | backoff/503 for answer-critical path; do not keep increasing concurrency | final submit priority preserved |
| Redis unavailable | direct fallback if allowed; otherwise controlled 503 Retry-After | PostgreSQL safety first |
| Redis noeviction OOM | explicit write failure; no saved response unless DB/durable journal accepted | no silent data loss |
| malformed payload | sanitized deadletter; no raw answer logs | diagnosis without leakage |
| stale processing queue | rescue/retry bounded by age/lock policy | no permanent stuck session |
| final submit with pending buffer | session-scoped forced flush/verify durable state before grading | no grading from volatile state |

## 12. Staging proof sequence

All steps must use synthetic data only and must not target production load.

### Step 1: direct baseline

```text
ANSWER_WRITE_MODE=direct
queue/hybrid OFF
runtime buffer production OFF
summary tool PASS
checker mismatch=0
```

### Step 2: shadow-only baseline

```text
session allowlist only
shadow percentage 0
summary tool PASS
post-final refresh visible
no production queue/buffer keys
```

### Step 3: isolated Redis answer topology

```text
redis_answers noeviction
AOF healthy
evicted_keys=0
rejected_connections=0
namespace scan clean
```

### Step 4: start dedicated answer_flush worker in staging

```text
worker online
pool not solo for answer_flush proof, unless explicitly testing solo baseline
concurrency=2 initial
prefetch_multiplier=1
queue binding only answer_flush
maintenance worker separate
```

### Step 5: synthetic buffer writes

```text
create synthetic sessions only
write 3-5 questions per session
include modifications
verify runtime:session:* keys only
verify no raw token/PII logs
```

### Step 6: normal drain proof

```text
answer_flush drains pending to zero
processing returns to zero
PostgreSQL answers match expected state
checker mismatch=0
```

### Step 7: worker restart during backlog

```text
create controlled backlog
restart answer_flush worker in staging
processing items recover or retry
queue drains to zero
no duplicate DB answers
checker mismatch=0
```

### Step 8: DB/Redis transient tests

```text
simulate Redis reconnect in staging
simulate DB transient/backpressure within safe bounds
verify controlled retry/503 behavior
verify no fake saved response
```

### Step 9: final submit with pending buffer

```text
leave pending dirty buffer
submit final
session-scoped forced flush/verify durable state
HTTP 200 only after durable verification
checker after final submit mismatch=0
```

### Step 10: observation gate

```text
queue depth=0
processing depth=0
deadletter=0 unless expected/approved test case
redis_errors=0
payload_hash_mismatch=0
DB long active queries=0
idle_in_transaction=0
logs clean
```

## 13. Production canary prerequisites

Production canary remains not approved.

Before asking for canary approval:

```text
Phase 6.5a Redis answer-critical design approved
Phase 6.5b Celery answer_flush topology approved
staging forced-flush proof PASS
Redis noeviction answer-critical policy proven
answer_flush worker topology proven
rollback drill documented
read-only preflight script reviewed
summary/checker gates automated
operator approval text defined
session/exam allowlist only
no percentage rollout
```

Canary proposal must include:

```text
exact session/exam scope
activation env diff
services to recreate
services not restarted
preflight gates
runtime observation gates
disable/rollback steps
failure stop criteria
sanitized reporting template
```

## 14. Rollback design

First rollback action for future experiments:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

If only app/env changed:

```text
recreate app-plane only
confirm health 200
confirm queue/hybrid OFF
confirm summary tool PASS
```

If Celery topology changed:

```text
stop/disable answer_flush worker only if approved
keep maintenance worker stable
confirm no pending answer-critical backlog before worker removal
preserve sanitized diagnostics
```

If Redis topology/policy changed:

```text
data-service rollback requires separate maintenance approval
no Redis restart/change bundled into app-plane rollback unless explicitly approved
no broad Redis deletion
exact-key cleanup only if approved
```

## 15. Implementation sequencing proposal

No implementation is approved by this document. If approved later, sequence should be:

1. Source-only Celery routing design patch:

```text
add explicit queue names/routing config default-off
no production queue/hybrid activation
unit tests for routing defaults
```

2. Staging-only compose/topology patch:

```text
add celery_worker_answer_flush in staging file or documented staging override
queue binding answer_flush only
concurrency=2 initial
prefetch_multiplier=1
```

3. Staging proof harness:

```text
synthetic sessions only
summary/checker gates
worker restart test
Redis reconnect test
final submit pending-buffer test
```

4. Canary proposal document only:

```text
only if staging proof PASS
production remains NO until explicit approval
```

## 16. Decision matrix

| Decision | Status | Reason |
| --- | --- | --- |
| Current single Celery `solo` worker answer production safe | NO | concurrency=1 and mixed workload can starve answer flush |
| Dedicated answer_flush worker preferred | YES | isolates answer-critical draining from maintenance jobs |
| Queue/hybrid production | NO | Redis, Celery, and forced-flush proof blockers remain |
| Final submit priority | MUST remain highest | final submit cannot wait behind generic backlog |
| Redis/Celery source-of-truth | NO | PostgreSQL/durable journal required for acknowledged success |
| Production canary | NO | not approved and staging proof missing |
| Next step | staging forced-flush proof plan/harness design | only after Redis and Celery designs are reviewed |

Final conservative decision:

```text
Do not enable Phase 6 production.
Do not enable queue/hybrid.
Do not deploy Celery topology to VPS.
Proceed next with a source-only staging forced-flush proof plan/harness design.
```
