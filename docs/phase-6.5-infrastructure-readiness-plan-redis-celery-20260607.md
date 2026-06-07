# Phase 6.5 Infrastructure Readiness Plan: Redis Policy and Celery Topology

Date: 2026-06-07

## 1. Baseline from Phase 6.4

Phase 6.4 result:

```text
Phase 6.4 five-session validation: PASS
Summary tool gate: PASS
5/5 synthetic sessions answer-save: PASS
5/5 checker-before payload_hash_mismatch=0
5/5 final submit HTTP 200/submitted
5/5 SHADOW_POST_FINAL_REFRESH_OK visible
5/5 checker-after payload_hash_mismatch=0
Post-disable observation: PASS
```

Latest reviewed head when this plan was created:

```text
682efac3d438cd59538bf15b6a844d953535b3b6
```

Phase 6 production decision remains:

```text
Phase 6 production: NO
Queue/hybrid: NO
Runtime buffer source-of-truth: NO
Redis source-of-truth: NO
```

## 2. Scope

This is a planning document only. It does not change runtime state.

Allowed now:

```text
source/docs planning
read-only audits
staging/prod-like design
acceptance criteria definition
rollback design
```

Not allowed now:

```text
enable queue
enable hybrid
enable runtime buffer production
change ANSWER_WRITE_MODE away from direct
use percentage rollout
make Redis source-of-truth
production load-test
APK changes
DB migration/schema change
DB/Redis/PgBouncer restart
broad Redis key deletion
```

Production defaults remain:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

## 3. Current blocker summary

| Area | Current state | Blocker decision |
| --- | --- | --- |
| Redis eviction | `maxmemory-policy=allkeys-lru` | BLOCKER: answer-critical keys can be evicted under pressure |
| Redis durability | AOF enabled, `appendfsync=everysec` | Acceptable for cache/shadow, not enough proof for answer source-of-truth |
| Celery worker | `pool=solo`, `max-concurrency=1` | BLOCKER: not a scalable answer flush topology |
| Queue backlog proof | no answer queue backlog in direct mode | BLOCKER: no production-like forced-flush/backlog drain proof |
| Final submit | does not read Redis shadow | GOOD: PostgreSQL remains grading/source-of-record |
| Canary | no approval | BLOCKER: no production canary may start |

## 4. Redis readiness plan

### 4.1 Current source configuration

Repo `docker-compose.production.yml` currently defines Redis as:

```text
image: redis:7-alpine
appendonly=yes
appendfsync=everysec
maxmemory=1400mb
maxmemory-policy=allkeys-lru
container memory limit=1792M
```

Live Phase 6.4 blocker audit observed:

```text
maxmemory-policy=allkeys-lru
maxmemory=1468006400
maxmemory_human=1.37G
used_memory_human=10.02M
used_memory_peak_human=14.38M
rejected_connections=0
evicted_keys=0
appendonly=yes
appendfsync=everysec
aof_enabled=1
aof_last_bgrewrite_status=ok
rdb_last_bgsave_status=ok
```

### 4.2 Why `allkeys-lru` blocks answer production

`allkeys-lru` may evict any key when Redis reaches memory pressure. That is acceptable for cache-like data and acceptable for Phase 6 shadow because the shadow stores hash-only evidence and PostgreSQL remains source-of-record.

It is not acceptable for production answer queue/runtime buffer because answer-critical keys could disappear before they are flushed to PostgreSQL.

### 4.3 Conservative target architecture

Preferred target: split cache Redis from answer-critical Redis.

```text
redis_cache
  purpose: cache, rate limits, pub/sub, monitoring caches
  policy: allkeys-lru or volatile-lru depending cache profile
  safe to evict: yes

redis_answers
  purpose: answer runtime queue/buffer metadata only if future design is approved
  policy: noeviction
  persistence: AOF enabled
  isolated memory budget: yes
  alerting: strict rejected writes / memory / AOF / backlog
  safe to evict: no
```

Important constraint:

```text
Even with redis_answers, Redis must not become the sole source-of-truth. Any future queue/hybrid mode must either keep PostgreSQL as the acknowledged source-of-record or use a durable PostgreSQL-backed journal/ack design before accepting client success.
```

### 4.4 Alternative if a split Redis is not approved

If only one Redis instance is allowed, then answer queue production should remain blocked unless all of these are true:

```text
maxmemory-policy changed from allkeys-lru to noeviction
all cache keys audited for bounded TTL and no unbounded growth
memory headroom proven under staging/prod-like traffic
Redis write failure behavior returns safe retry/503 for answer paths
no answer success is acknowledged unless durable recovery path exists
```

This option is riskier because cache and answer-critical workloads compete in one memory pool.

### 4.5 Redis acceptance gates before any canary discussion

Required read-only/prod-like gates:

```text
CONFIG GET maxmemory-policy != allkeys-lru for answer-critical Redis
policy is noeviction for answer-critical keys
rejected_connections=0
evicted_keys=0 for answer-critical Redis
AOF enabled and healthy
AOF rewrite status healthy
used_memory below warning threshold with headroom
all answer-critical keys namespaced
all non-critical keys have bounded TTL
summary tool reports runtime_answer_buffer_keys_count=0 before activation
summary tool reports answer_queue_keys_count=0 before activation
```

Required failure gates in staging/prod-like environment:

```text
Redis memory pressure does not silently drop answer-critical keys
write failure returns explicit retry/error, never fake saved
restart/reconnect preserves expected durable state or fails safely
no raw answers/tokens/PII stored in Redis shadow paths
```

## 5. Celery worker topology readiness plan

### 5.1 Current source configuration

Repo `docker-compose.production.yml` currently defines one Celery worker:

```text
command: celery -A app.tasks.scheduler worker --loglevel=warning --pool=solo --max-tasks-per-child=200
DB_POOL_SIZE=2
DB_MAX_OVERFLOW=4
memory limit=512M
```

Live Phase 6.4 blocker audit observed:

```text
pool implementation=celery.concurrency.solo:TaskPool
max-concurrency=1
prefetch_count=4
runtime_answer_queue_keys=0
legacy_answer_queue_keys=0
celery_keys=0
kombu_keys=0
```

### 5.2 Why `solo` blocks answer flush production

`solo` executes one task at a time in one process. It is simple and stable for maintenance jobs, but it is not enough proof for answer flushing because:

```text
no parallel flush capacity
one long task can block later answer flushes
no isolation between maintenance tasks and answer-critical tasks
prefetch behavior is not tuned for answer fairness
no dedicated answer queue worker health model
```

### 5.3 Conservative target topology

Introduce dedicated worker lanes in source/staging first:

```text
celery_worker_maintenance
  queue: default/maintenance/scheduler tasks
  purpose: existing non-answer jobs
  pool: conservative current-compatible configuration

celery_worker_answer_flush
  queue: answer_flush only
  purpose: answer buffer flush tasks only
  pool: prefork or threads after compatibility test
  concurrency: start small in staging, e.g. 2-4, then tune
  prefetch_multiplier: 1
  acks_late: true only if tasks are idempotent
  max_tasks_per_child: bounded
  DB pool: bounded and coordinated with PgBouncer
```

The answer flush worker must not share capacity with heavy export, monitoring, Telegram, archive, or maintenance jobs.

### 5.4 Celery task requirements

Before any production queue/hybrid:

```text
answer flush tasks are idempotent by session/question/version
retry is bounded with backoff
poison/failing sessions are moved to a visible failure set/table
operator-visible backlog metrics exist
no raw answer content appears in logs
DB commit is the only durable completed state
partial flush can be safely retried
```

### 5.5 Celery acceptance gates

Staging/prod-like gates:

```text
answer_flush worker starts healthy
worker pool is not solo for answer_flush
concurrency explicitly set and measured
queue backlog drains to 0 after synthetic runs
worker restart during backlog does not create duplicates or data loss
DB long active queries=0 after run
idle_in_transaction=0 after run
summary checker mismatch=0 before/after final submit
final submit remains successful while worker is degraded only if direct-safe fallback is active
```

Production pre-canary read-only gates:

```text
celery inspect stats shows answer_flush worker online
answer_flush queue depth=0 before activation
default/maintenance queue cannot starve answer_flush
worker logs show no tracebacks/error clusters
Redis rejected/evicted=0
PgBouncer wait/DB long queries normal
```

## 6. Forced flush proof plan

### 6.1 Current code state

Phase 6.4 blocker audit observed:

```text
flush_runtime_answer_buffer_for_session_present=True
forced_flush_function_present=True
runtime_buffer_enabled_gate_present=True
final_submit_reads_shadow_keys=False
redis_shadow_source_of_truth=False
```

Positive point:

```text
Final submit does not read Redis shadow keys. PostgreSQL remains grading/source-of-record.
```

Remaining blocker:

```text
Forced flush hooks exist, but forced flush has not been proven under a production-like Redis/Celery topology.
```

### 6.2 Required proof sequence

All proof must happen in isolated staging/prod-like topology before production canary:

1. Direct baseline:

```text
ANSWER_WRITE_MODE=direct
queue/hybrid OFF
summary checker mismatch=0
```

2. Shadow-only baseline:

```text
allowlist-only synthetic sessions
percentage 0
summary tool PASS
no production buffer/queue keys
```

3. Queue/hybrid source-only staging trial:

```text
not production
synthetic only
dedicated answer Redis policy safe
dedicated answer_flush worker online
forced flush on final submit enabled for staging only
```

4. Failure injection in staging:

```text
answer_flush worker paused/restarted with pending items
Redis reconnect tested
duplicate answer modifications tested
final submit triggers bounded flush rounds
no duplicate DB answers
no stale Redis answer hashes
no raw answer leakage
```

5. Staging acceptance:

```text
answer save success criteria explicit
final submit HTTP 200/submitted for all synthetic sessions
payload_hash_mismatch=0 before final submit
payload_hash_mismatch=0 after final submit
redis_errors=0
missing_in_redis=0
extra_in_redis=0
queue backlog returns to 0
DB active/idle gates clean
logs clean
```

## 7. Production canary readiness plan

Production canary is not approved now.

Minimum prerequisites before asking for canary approval:

```text
Redis answer-critical policy fixed and proven
Celery answer_flush topology implemented and proven in staging
forced flush proof completed under staging/prod-like topology
rollback plan reviewed
read-only preflight script reviewed
operator-visible gates defined
no percentage rollout
session/exam allowlist only
PostgreSQL remains source-of-record
final submit does not depend on Redis shadow
```

Canary approval must be separate and explicit. Until then:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
```

## 8. Rollback principles

For any future staging/canary attempt:

```text
first rollback action: restore direct mode
set ANSWER_QUEUE_ENABLED=false
set ANSWER_QUEUE_PERCENTAGE=0
set ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
set ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
clear allowlists
recreate app-plane only unless data-service change was explicitly approved
never broadly delete Redis keys without exact-key cleanup approval
preserve sanitized diagnostics only
```

If Redis policy/topology was changed, rollback requires a separate data-service maintenance plan because Redis restart/change is explicitly higher risk than app-plane recreation.

## 9. Proposed next implementation tasks

### Task A: Redis answer-critical design document

Deliverable:

```text
docs/phase-6.5a-redis-answer-critical-design-YYYYMMDD.md
```

Content:

```text
split Redis vs single Redis decision
memory sizing
key namespaces
TTL policy
persistence policy
failure behavior
observability
rollback plan
```

No runtime change.

### Task B: Celery answer_flush topology source plan

Deliverable:

```text
docs/phase-6.5b-celery-answer-flush-topology-YYYYMMDD.md
```

Content:

```text
worker services
queues
concurrency
prefetch
DB pool budget
idempotency contract
backlog metrics
rollback plan
```

No production activation.

### Task C: Staging forced-flush proof harness

Deliverable:

```text
scripts/staging_force_flush_proof.py or equivalent docs + scripts
```

Constraints:

```text
must not target production
synthetic data only
no raw answer/token/PII output
summary tool/checker gates required
```

### Task D: Production canary proposal only after A-C pass

Deliverable:

```text
docs/phase-6.6-production-canary-proposal-YYYYMMDD.md
```

Status now:

```text
NOT READY / NOT APPROVED
```

## 10. Final decision

```text
Phase 6.4: PASS
Proceed to infrastructure readiness planning: YES
Proceed to production Phase 6: NO
Proceed to queue/hybrid production: NO
Proceed to Redis source-of-truth: NO
Proceed to production canary: NO
```

Recommended immediate next step:

```text
Create Phase 6.5a Redis answer-critical design doc first, then Phase 6.5b Celery answer_flush topology doc. Do not modify VPS runtime until both designs and a staging forced-flush proof plan are approved.
```
