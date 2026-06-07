# Phase 6.5a Redis Answer-Critical Design

Date: 2026-06-07

## 1. Purpose and non-goals

### Purpose

Define a safe Redis design for future answer runtime buffer / queue experiments after Phase 6.4 proved hash-only shadow validation across five synthetic sessions.

This document is a design artifact only. It exists to make future Redis-related work explicit before any staging forced-flush proof or production canary is discussed.

Design goals:

```text
protect student answer safety
keep PostgreSQL as source-of-record
define Redis policies safe enough for answer-critical experiments
define failure behavior before implementation
define acceptance gates before staging/canary
avoid silent data loss under Redis memory pressure
avoid raw tokens, PII, or raw answer leakage in Redis/logs
```

### Non-goals

```text
no production activation
no queue activation
no hybrid activation
no runtime buffer production activation
no Redis source-of-truth approval
no VPS runtime change
no .env change
no docker-compose runtime change
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

## 2. Current Redis baseline

Source configuration in `docker-compose.production.yml`:

```text
image: redis:7-alpine
appendonly=yes
appendfsync=everysec
auto-aof-rewrite-percentage=100
auto-aof-rewrite-min-size=64mb
maxmemory=1400mb
maxmemory-policy=allkeys-lru
maxmemory-samples=7
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
aof_rewrite_in_progress=0
aof_last_bgrewrite_status=ok
rdb_last_bgsave_status=ok
```

Current safe use:

```text
cache-like data
monitoring/cache summaries
rate-limit/session-like temporary state where eviction is acceptable
hash-only runtime shadow validation evidence with TTL
```

Current unsafe use:

```text
answer source-of-truth
acknowledged answer queue without durable recovery
runtime buffer production where answer-critical keys may be evicted
```

## 3. Why `allkeys-lru` is unsafe for answers

`allkeys-lru` can evict any key when Redis reaches memory pressure. Redis does not know which keys are answer-critical unless the design isolates them or forbids eviction.

This means an answer-critical key such as a pending queue item, dirty question set, or session answer hash can disappear before a worker flushes it to PostgreSQL.

Acceptable use under `allkeys-lru`:

```text
cache entries
best-effort monitoring data
hash-only shadow evidence where PostgreSQL remains source-of-record
```

Not acceptable under `allkeys-lru`:

```text
acknowledged answer save state
pending answer flush source
final submit source-of-truth
anything where data loss changes student grading state
```

Current Redis can continue to support Phase 6 shadow because the shadow stores hash-only evidence and final submit does not read Redis shadow for grading. It must not be used as answer source-of-truth.

## 4. Preferred target: split Redis

Preferred future design: split cache Redis from answer-critical Redis.

### 4.1 `redis_cache`

Purpose:

```text
cache
rate limiting
pub/sub
admin summary cache
monitoring cache
non-critical temporary state
```

Policy:

```text
eviction allowed
allkeys-lru or volatile-lru depending cache profile
all cache keys namespaced
TTL bounded for non-persistent cache keys
cache miss must degrade safely to database/origin reads or controlled response
```

Safety rules:

```text
no answer-critical source state
no raw tokens in keys/logs
no raw PII in keys/logs
no raw answer content
```

### 4.2 `redis_answers`

Purpose:

```text
answer runtime buffer/queue metadata only if a future design is approved
answer flush coordination
answer flush metrics
answer-critical staging/canary experiments only after gates pass
```

Required policy:

```text
maxmemory-policy=noeviction
AOF enabled
appendfsync=everysec minimum, reviewed against latency/durability requirements
strict memory headroom
strict rejected write alerts
strict AOF health alerts
namespace allowlist for answer-critical keys only
```

Security/privacy rules:

```text
no raw tokens
no session tokens
no usernames/full names/emails
no raw answer text in keys
no raw answer text in logs
prefer hashes/metadata where possible
sanitize all diagnostics
```

Proposed answer-critical namespaces:

```text
runtime:session:{session_id}:answers
runtime:session:{session_id}:dirty_questions
runtime:session:{session_id}:answered_count
runtime:answer_queue:pending
runtime:answer_queue:processing
runtime:answer_queue:deadletter
runtime:answer_flush:metrics
```

Current existing source names already include:

```text
runtime:session:{session_id}:answers
runtime:session:{session_id}:dirty_questions
runtime:session:{session_id}:answered_count
runtime:answer_queue:pending
runtime:answer_queue:processing
runtime:answer_queue:queued:{session_id}
runtime:answer_queue:flush:lock
runtime:answer_shadow:session:{session_id}:answers
runtime:answer_shadow:session:{session_id}:meta
runtime:answer_shadow:sessions
```

`runtime:answer_shadow:*` remains hash-only shadow evidence and is not source-of-truth.

### 4.3 Split Redis acceptance rules

Before `redis_answers` can be used for staging queue/hybrid experiments:

```text
`redis_answers` exists separately from `redis_cache`
`redis_answers` policy is noeviction
`redis_answers` AOF is healthy
`redis_answers` rejected_connections=0
`redis_answers` evicted_keys=0
answer key namespace scan matches allowlist only
memory headroom is proven under synthetic staging load
application settings can route answer-critical Redis separately without touching cache Redis
rollback can restore direct mode without data-service restart where possible
```

## 5. Alternative: single Redis `noeviction`

If a split Redis deployment is not approved, a single Redis with `maxmemory-policy=noeviction` is the minimum safer alternative for answer-critical experiments.

This is riskier because:

```text
cache keys and answer-critical keys compete in one memory pool
cache growth can cause Redis writes to fail for answers
cache TTL audit becomes mandatory
non-critical cache must support backpressure or bypass
operator has less isolation during incidents
one Redis restart affects all workloads
```

Additional requirements for this alternative:

```text
all cache keys audited for TTL and bounded cardinality
non-critical cache writes must tolerate Redis OOM/write failure
answer writes must fail safely if Redis has no memory
no fake saved response when answer-critical write fails
memory usage alarms must fire before answer writes are threatened
```

Single Redis `noeviction` may be acceptable only for staging proof or a narrowly approved canary. It is not preferred for production readiness.

## 6. Answer durability principle

This section is mandatory for future Phase 6 work.

Redis must not become the sole source-of-truth.

A client success response must mean one of these is true:

```text
PostgreSQL is already committed; or
a separately approved durable recovery path has accepted the write and can prove recovery after Redis/app/worker restart.
```

Mode-specific ack semantics:

### 6.1 Direct mode

```text
client success only after PostgreSQL commit
Redis post-commit markers/shadow are best-effort only
Redis failure after DB commit must not turn saved answer into failure
```

Current production mode remains direct.

### 6.2 Shadow mode

```text
client success is unaffected by Redis shadow
shadow stores hash-only mirror/evidence
PostgreSQL remains source-of-record
final submit does not read shadow keys for grading
```

This was proven by Phase 6.4 synthetic validation.

### 6.3 Proposed hybrid/queue mode

For any future design:

```text
client success must not rely on volatile Redis alone
success can be acknowledged after direct PostgreSQL commit; or
a durable journal write exists and has recovery proof
Redis may coordinate flush state but must not be the only durable copy
```

Potential durable-journal patterns to evaluate before implementation:

```text
PostgreSQL answer journal table with idempotency key
PostgreSQL outbox table for flush state
synchronous direct write with Redis-only performance hints
```

Final submit principle:

```text
final submit must force/verify durable answer state before grading
final submit must not grade from volatile Redis-only state
final submit must fail safely or retry if durable state cannot be verified
```

## 7. Failure behavior

Expected behavior for future design experiments:

| Failure | Expected behavior | Student safety rule |
| --- | --- | --- |
| Redis unavailable | Direct fallback if PostgreSQL path is available; otherwise controlled `503` with `Retry-After` for answer-critical paths | no fake saved |
| Redis `noeviction` memory full | Answer-critical Redis write fails explicitly; direct PostgreSQL fallback or controlled `503` | no silent drop |
| Redis reconnect | Bounded retry with jitter; no duplicate DB writes due to idempotency | no double grading |
| AOF rewrite failed | Alert, block queue/hybrid promotion, keep direct mode | no canary while persistence unhealthy |
| Partial write | Use atomic pipeline/transaction or detect incomplete state and fail safely | no partial saved response |
| Duplicate journal events | Idempotency key/session/question/version prevents duplicate DB state | latest valid answer wins |
| Stale dirty set | Checker/flush reconciles Redis metadata with DB durable state; stale metadata cannot affect final grade | DB remains source-of-record |
| Final submit while buffer pending | Force/verify flush to durable state; if not possible, fail safely/retry | no grading from pending volatile state |

Operational response:

```text
prefer direct PostgreSQL path when Redis answer-critical path is degraded
bounded retry only
controlled 503/retry-after when safety cannot be guaranteed
log sanitized failure class, not raw answers/tokens/PII
student answer safety priority over latency
```

## 8. Memory sizing and capacity model

This is a conservative sizing framework, not a final capacity claim.

### 8.1 Assumptions

```text
concurrent students: 300 and 600 scenarios
questions per student: 40 baseline, 60 high
active dirty questions per student: 3-10 during normal answering, up to all questions during reconnect edge cases
stored payload form: hash/metadata where possible, not raw answer content
per answer metadata estimate: 512 bytes to 2 KB including Redis hash overhead
per dirty question set entry: 64-128 bytes including overhead
per queue item: 64-256 bytes
per session metadata/count keys: 256-1024 bytes
TTL window: 4 hours for shadow-like evidence; queue/buffer state should drain quickly and be bounded
safety headroom: keep used_memory <= 50% normal, alert at 65%, critical at 80% for `redis_answers`
```

### 8.2 Scenario estimate: 300 concurrent students

Low estimate:

```text
300 students * 40 answers * 512 B = ~6 MB answer metadata
300 students * 10 dirty entries * 128 B = ~0.4 MB dirty sets
300 queue/session metadata * 1 KB = ~0.3 MB
Redis overhead / fragmentation multiplier 3x = ~20 MB
```

High conservative estimate:

```text
300 students * 60 answers * 2 KB = ~36 MB answer metadata
300 students * 60 dirty entries * 128 B = ~2.3 MB dirty sets
300 queue/session metadata * 2 KB = ~0.6 MB
Redis overhead / fragmentation multiplier 3x = ~117 MB
```

### 8.3 Scenario estimate: 600 concurrent students

Low estimate:

```text
600 students * 40 answers * 512 B = ~12 MB answer metadata
600 students * 10 dirty entries * 128 B = ~0.8 MB dirty sets
600 queue/session metadata * 1 KB = ~0.6 MB
Redis overhead / fragmentation multiplier 3x = ~40 MB
```

High conservative estimate:

```text
600 students * 60 answers * 2 KB = ~72 MB answer metadata
600 students * 60 dirty entries * 128 B = ~4.6 MB dirty sets
600 queue/session metadata * 2 KB = ~1.2 MB
Redis overhead / fragmentation multiplier 3x = ~234 MB
```

### 8.4 Capacity recommendation

For `redis_answers`, do not size only from expected payload. Include incident headroom:

```text
minimum test allocation: >=512 MB isolated maxmemory
preferred production candidate: >=1 GB isolated maxmemory
normal alert: used_memory >=65%
critical alert: used_memory >=80%
block canary: used_memory >=80%, rejected writes >0, AOF unhealthy, fragmentation severe
```

The sizing must be validated with staging synthetic data and realistic key overhead before production canary.

## 9. Persistence and backup

Required persistence for answer-critical Redis experiments:

```text
AOF enabled
appendfsync everysec minimum
AOF rewrite monitored
AOF last rewrite status must be ok
Redis restart/recovery test required
RDB-only is not acceptable for answer-critical state
```

Fsync implications:

```text
appendfsync everysec can lose up to roughly one second of Redis-only writes during crash
therefore Redis-only cannot justify client success without another durable journal
appendfsync always may reduce latency/throughput and still needs recovery proof
```

Disaster mode:

```text
PostgreSQL remains source-of-record
if Redis answer-critical state is lost or suspect, queue/hybrid must be disabled
operator should reconcile from PostgreSQL/checker, not Redis-only state
```

Backup principle:

```text
Redis AOF helps restart recovery but is not a substitute for PostgreSQL backup/source-of-record
no DB dump or Redis artifact should be committed to Git
```

## 10. Observability

Required Redis/system metrics:

```text
used_memory
used_memory_peak
maxmemory
maxmemory_policy
mem_fragmentation_ratio
rejected_connections
evicted_keys
expired_keys
connected_clients
blocked_clients
aof_enabled
aof_rewrite_in_progress
aof_last_bgrewrite_status
rdb_last_bgsave_status
```

Required namespace metrics:

```text
keyspace count by namespace
runtime:session:*:answers count
runtime:session:*:dirty_questions count
runtime:session:*:answered_count count
runtime:answer_queue:pending depth
runtime:answer_queue:processing depth
runtime:answer_queue:deadletter count
runtime:answer_flush:metrics values
runtime:answer_shadow:* count and TTL health
```

Required answer-flow metrics:

```text
flush latency p50/p95/p99
final submit forced flush duration
pending queue oldest age
processing queue oldest age
deadletter count
flush retry count
flush failure class count
idempotency duplicate count
```

Required checker/summary metrics:

```text
payload_hash_mismatch
redis_errors
missing_in_redis
extra_in_redis
stale_runtime_sessions
shadow_keys_without_ttl
runtime_answer_buffer_keys_count
answer_queue_keys_count
legacy_answer_queue_keys_count
post_final_refresh_missing_count
shadow_validation_summary.py output
runtime_buffer_consistency_check.py output
```

Alert examples:

```text
CRITICAL if evicted_keys increases on redis_answers
CRITICAL if rejected_connections increases on redis_answers
CRITICAL if AOF rewrite/status fails
CRITICAL if pending queue oldest age exceeds forced-flush SLA
CRITICAL if payload_hash_mismatch > 0
WARNING if used_memory >=65%
CRITICAL if used_memory >=80%
```

## 11. Preflight and acceptance gates

Before any staging/canary Redis answer-critical experiment:

```text
Redis answer-critical policy != allkeys-lru
Redis answer-critical policy == noeviction
evicted_keys=0
rejected_connections=0
AOF healthy
AOF rewrite not failing
summary tool PASS
runtime_answer_buffer_keys_count=0 before activation
answer_queue_keys_count=0 before activation
legacy_answer_queue_keys_count=0 before activation
direct mode baseline clean
active_sessions=0 for production-adjacent validation windows
running_exam_windows=0 for production-adjacent validation windows
DB long active queries=0
idle_in_transaction=0
```

Application safety gates:

```text
ANSWER_WRITE_MODE remains direct unless explicitly approved staging/canary
ANSWER_QUEUE_ENABLED=false in production
ANSWER_QUEUE_PERCENTAGE=0
shadow percentage=0
allowlist only for validation
no raw answer/token/PII output
```

Promotion gates from staging to canary proposal:

```text
forced flush proof PASS
worker restart during backlog PASS
Redis reconnect test PASS
final submit with pending buffer PASS
summary checker mismatch=0 before and after final submit
queue drains to zero
logs clean
rollback drill documented
```

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
allowlist-only synthetic sessions
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
hash-only Redis shadow keys
summary tool PASS
no runtime answer buffer production keys
no answer queue keys
```

### Step 3: `redis_answers` topology boot

```text
boot isolated redis_answers in staging
policy=noeviction
AOF healthy
namespace scan clean
no rejected/evicted keys
```

### Step 4: synthetic answer buffer write

```text
write synthetic answers through future staging-only buffer path
verify keys under runtime:session:* only
verify no raw tokens/PII/raw answer log output
verify dirty set and answered_count consistency
```

### Step 5: forced flush

```text
run dedicated answer flush path
verify PostgreSQL committed state
verify queue pending/processing drain
verify idempotent replay behavior
```

### Step 6: worker restart during backlog

```text
create controlled synthetic backlog
restart answer_flush worker in staging
verify processing items recover or move to safe retry/deadletter
verify no duplicate DB answers
verify queue drains to zero
```

### Step 7: Redis reconnect test

```text
simulate Redis reconnect/transient failure in staging only
verify direct fallback or controlled 503/retry-after
verify no fake saved response
verify sanitized logs
```

### Step 8: final submit with pending buffer

```text
create pending synthetic buffer
trigger final submit
force/verify durable state before grading
final submit HTTP 200 only if durable state verified
checker mismatch=0 after final submit
```

### Step 9: final staging gates

```text
summary checker payload_hash_mismatch=0
redis_errors=0
missing_in_redis=0
extra_in_redis=0
queue drains to zero
deadletter count=0 unless expected test path is documented
DB long active queries=0
idle_in_transaction=0
logs clean
```

## 13. Rollback design

First rollback action for future experiments:

```text
restore ANSWER_WRITE_MODE=direct
set ANSWER_QUEUE_ENABLED=false
set ANSWER_QUEUE_PERCENTAGE=0
set ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
set ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
clear ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS
clear ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS
recreate app-plane only if only app/env changed
```

Redis cleanup rules:

```text
no broad Redis deletion
exact-key cleanup only if approved
prefer TTL expiration for synthetic shadow keys
preserve sanitized diagnostics before cleanup
```

Data-service rollback:

```text
Redis policy/topology changes require separate maintenance window
Redis restart/change must not be bundled with app-plane rollback unless explicitly approved
DB/Redis/PgBouncer restart remains forbidden without separate approval
```

Failure documentation:

```text
record failure class
record sanitized session/exam IDs only if needed
no raw answers
do not print tokens/session tokens/usernames/full names/emails
include checker/summary aggregate counts
```

## 14. Decision matrix

| Decision | Status | Reason |
| --- | --- | --- |
| Current Redis `allkeys-lru` answer production safe | NO | answer-critical keys can be evicted under pressure |
| Current Redis acceptable for hash-only shadow | YES | PostgreSQL remains source-of-record and final submit does not read shadow |
| Preferred future design | Split Redis | isolates cache eviction from answer-critical noeviction state |
| Single Redis `noeviction` | Possible but riskier | cache and answer-critical keys compete in one memory pool |
| Redis source-of-truth | NO | client success needs PostgreSQL commit or separately approved durable journal |
| Queue/hybrid production | NO | Redis policy, Celery topology, and forced-flush proof blockers remain |
| Production canary | NO | not approved and prerequisites are incomplete |
| Next step | Phase 6.5b Celery `answer_flush` topology design | define worker queues/concurrency/idempotency before staging forced-flush proof |

Final conservative decision:

```text
Do not enable Phase 6 production.
Do not enable queue/hybrid.
Do not make Redis source-of-truth.
Proceed only with source-only Phase 6.5b Celery answer_flush topology design.
```
