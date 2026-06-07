# Phase 6.5c Staging Forced-Flush Proof Plan / Harness Design

Date: 2026-06-07

## 1. Purpose and scope

This document defines a source-only plan for proving answer forced-flush behavior in an isolated staging / production-like topology.

It follows:

```text
Phase 6.4 five-session synthetic shadow validation: PASS
Phase 6.5 Redis/Celery readiness plan: created
Phase 6.5a Redis answer-critical design: created
Phase 6.5b Celery answer_flush topology design: created
```

Goal:

```text
prove that future queue/hybrid/runtime-buffer experiments can safely flush answer state to PostgreSQL before final submit grading
prove worker restart/retry/reconnect behavior without data loss or duplicate grading state
prove summary/checker gates remain clean before and after final submit
```

This is a design document only. It does not implement a harness, deploy to VPS, change runtime, or approve production canary.

## 2. Non-goals and hard boundaries

Not approved by this document:

```text
production activation
queue activation
hybrid activation
runtime buffer production activation
Redis source-of-truth
production load-test
VPS deploy
.env change
runtime docker-compose change
service restart
DB migration/schema change
APK change
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

The forced-flush proof must run only in staging or an isolated production-like environment with synthetic data.

## 3. Required prerequisite designs

Before implementation/execution of this proof harness:

```text
Phase 6.5a Redis answer-critical design reviewed
Phase 6.5b Celery answer_flush topology design reviewed
staging environment declared isolated from production
staging Redis answer-critical policy can be tested safely
staging Celery answer_flush worker can be restarted safely
synthetic data creation and cleanup plan reviewed
```

Production remains blocked until the staging proof passes and a separate production canary proposal is approved.

## 4. Staging environment topology

Minimum staging topology:

```text
FastAPI app-plane staging replicas
PostgreSQL staging database with production-like schema
PgBouncer staging pooler, if production-like test uses PgBouncer
redis_cache or current Redis-equivalent for cache/broker if needed
redis_answers with maxmemory-policy=noeviction for answer-critical state
celery_worker_maintenance bound to maintenance/default queues
celery_worker_answer_flush bound only to answer_flush queue
celery_beat with explicit task routing
```

Staging Redis answer-critical gates:

```text
maxmemory-policy=noeviction
AOF enabled
appendfsync configured and documented
evicted_keys=0
rejected_connections=0
AOF last rewrite status ok
namespace scan clean before proof
```

Staging Celery answer_flush gates:

```text
worker online
queue binding answer_flush only
pool and concurrency explicit
initial concurrency=2 unless design review changes it
prefetch_multiplier=1
maintenance tasks not routed to answer_flush
```

## 5. Synthetic data scope

Synthetic-only scope:

```text
exam prefix: __PHASE6_FORCE_FLUSH_TEST__
account prefix: __PHASE6_FORCE_FLUSH_TEST__
no real student data
no real exam data
no raw answer values printed
no tokens/session tokens printed
no usernames/full names/emails printed
```

Recommended minimum matrix:

| Scenario | Sessions | Questions/session | Purpose |
| --- | ---: | ---: | --- |
| direct baseline | 3 | 3-5 | prove staging baseline clean |
| shadow-only baseline | 3 | 3-5 | prove summary/checker gates clean |
| normal buffer drain | 5 | 5 | prove answer_flush drains to DB |
| worker restart during backlog | 5 | 5 | prove restore/retry/idempotency |
| Redis reconnect/failure | 3 | 3-5 | prove fail-safe behavior |
| final submit pending buffer | 5 | 5 | prove forced durable state before grading |

No production-size load is required or allowed.

## 6. Harness design overview

The harness should be a staging-only operator tool. Proposed path if implemented later:

```text
scripts/staging_forced_flush_proof.py
```

It must refuse to run unless staging guardrails are present.

Required guardrails:

```text
APP_ENV != production, or explicit STAGING_FORCE_FLUSH_PROOF=true
public production domain not targeted
database name/host matches approved staging allowlist
synthetic prefix required
ANSWER_QUEUE_PERCENTAGE must be 0 unless explicitly testing staging-only queue mode
no raw answer/token/PII output
redaction enabled by default
```

Suggested subcommands:

```text
preflight
create-synthetic-scope
run-direct-baseline
run-shadow-baseline
run-buffer-drain
run-worker-restart
run-redis-reconnect
run-final-submit-pending
run-summary-gates
cleanup-plan
```

The harness should write only sanitized logs and a local staging report artifact that is not committed unless redacted and reviewed.

## 7. Preflight gates

Before creating synthetic staging sessions:

Health gates:

```text
local /health=200
staging public /health=200, if public staging exists
all staging app containers healthy
DB healthy
PgBouncer healthy if used
redis_answers PONG
celery_worker_answer_flush online
celery_worker_maintenance online
```

DB gates:

```text
active real sessions=0, or staging isolated with only synthetic sessions
long active queries >60s = 0
idle_in_transaction = 0
final_submit_drain = 0
```

Redis gates:

```text
redis_answers maxmemory-policy=noeviction
redis_answers rejected_connections=0
redis_answers evicted_keys=0
runtime_answer_buffer_keys_count=0 before proof
answer_queue_keys_count=0 before proof
legacy_answer_queue_keys_count=0 before proof
```

Celery gates:

```text
answer_flush queue depth=0
answer_flush processing depth=0
answer_flush deadletter count=0
maintenance queue cannot consume answer_flush tasks
answer_flush worker concurrency and prefetch match design
```

Tool gates:

```text
python scripts/shadow_validation_summary.py --limit 20 --fail-on-mismatch
python scripts/runtime_buffer_consistency_check.py --limit 20
```

Expected:

```text
payload_hash_mismatch=0
redis_errors=0
missing_in_redis=0
extra_in_redis=0
runtime_answer_buffer_keys_count=0
answer_queue_keys_count=0
legacy_answer_queue_keys_count=0
```

## 8. Proof sequence

### Step 1: direct baseline

Configuration:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
runtime buffer production OFF
shadow OFF or allowlisted-only if proving shadow baseline separately
```

Execution:

```text
create 3 synthetic sessions
submit q1/q2
modify q1
batch q3
journal q2 if endpoint exists
final submit
```

Pass gates:

```text
all answer saves HTTP 200/saved
all final submit HTTP 200/submitted
checker mismatch=0
summary tool PASS
logs clean
```

### Step 2: shadow-only baseline

Configuration:

```text
ANSWER_WRITE_MODE=direct
queue/hybrid OFF
shadow enabled only for synthetic session allowlist
shadow percentage=0
```

Pass gates:

```text
hash-only shadow keys
TTL present
no raw answer/token/PII in Redis/logs
checker-before mismatch=0
checker-after mismatch=0
SHADOW_POST_FINAL_REFRESH_OK visible
summary tool PASS
shadow disabled after step
```

### Step 3: normal answer buffer drain

Configuration:

```text
staging-only runtime buffer mode under synthetic allowlist
redis_answers noeviction
answer_flush worker online
```

Execution:

```text
create 5 synthetic sessions
write 5 answers/session with modifications
verify runtime:session:* keys and runtime:answer_queue:pending entries exist only for synthetic sessions
let answer_flush worker drain
```

Pass gates:

```text
pending depth returns to 0
processing depth returns to 0
deadletter=0
PostgreSQL has expected latest answers
runtime checker mismatch=0
summary tool PASS
```

### Step 4: worker restart during backlog

Execution:

```text
create controlled synthetic backlog
confirm pending/processing state
restart celery_worker_answer_flush in staging only
observe rescue/retry behavior
wait for drain
```

Pass gates:

```text
no duplicate DB answer rows
latest answer wins for modified questions
pending=0
processing=0
deadletter=0 unless test intentionally injects poison payload
checker mismatch=0
flush logs sanitized
```

### Step 5: Redis reconnect/failure behavior

Execution options must be staging-only and reviewed. Examples:

```text
temporarily block Redis answer endpoint from answer_flush worker container in staging
restart redis_answers in staging maintenance window only
simulate Redis client reconnect by killing staging app/worker connection
```

Expected behavior:

```text
direct fallback where configured and safe
controlled 503 Retry-After where durable state cannot be guaranteed
no fake saved response
no raw answer/token/PII logs
recovery after reconnect
summary/checker clean after recovery
```

### Step 6: final submit with pending buffer

Execution:

```text
create synthetic session with pending dirty buffer
pause or delay background drain safely
trigger final submit
force session-scoped flush/verify durable state before grading
resume background drain
```

Pass gates:

```text
final submit HTTP 200 only after durable state verified
or controlled 503 Retry-After if durable state cannot be verified
checker-after mismatch=0
pending/processing drain to 0
final submit does not grade from Redis-only state
```

### Step 7: post-proof observation

Observation window:

```text
30-60 minutes in staging
```

Collect:

```text
health
traceback
connection errors
HTTP 500/503/409 counts
answer save errors
final submit errors
Redis rejected_connections
evicted_keys
AOF health
DB long active queries
idle_in_transaction
Celery queue depths
worker restarts
summary tool output
checker output
```

## 9. Pass/fail criteria

PASS only if:

```text
all direct baseline saves/final submits pass
shadow baseline hash-only and mismatch=0
normal buffer drain queue depth returns to 0
worker restart during backlog recovers without duplicate/lost answer state
Redis reconnect test fails safely or recovers cleanly
final submit with pending buffer verifies durable state before grading
payload_hash_mismatch=0
redis_errors=0
missing_in_redis=0
extra_in_redis=0
answer queue deadletter=0 unless expected injected poison test is documented
DB long active queries=0 after run
idle_in_transaction=0 after run
logs contain no raw answer/token/PII
```

FAIL if:

```text
any answer save falsely reports saved without durable state
any final submit grades from unverified volatile Redis state
payload_hash_mismatch > 0
redis_errors > 0 after recovery window
missing_in_redis or extra_in_redis unexpected
queue/processing stuck after timeout
deadletter unexpected
worker restart causes duplicate DB rows or stale final state
Redis evicted_keys increases on redis_answers
rejected_connections increases without safe response behavior
raw answer/token/PII appears in output/logs
```

## 10. Required output report

If implemented later, the harness should generate a sanitized staging report:

```text
docs/phase-6.5c-staging-forced-flush-proof-result-YYYYMMDD.md
```

Required report fields:

```text
Git head
staging environment ID, sanitized
approved execution scope
synthetic scope summary, redacted
preflight gates
Redis policy/AOF gates
Celery worker topology gates
per-scenario results
checker-before/after aggregates
summary tool output
queue depth/deadletter metrics
worker restart result
Redis reconnect/failure result
final submit pending-buffer result
post-proof observation
forbidden artifact check
final PASS/FAIL decision
```

Do not commit raw JSON artifacts, DB dumps, CSVs, session tokens, raw answers, or real user data.

## 11. Rollback and cleanup plan

First rollback action in staging:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_SESSION_IDS=
ANSWER_RUNTIME_BUFFER_SHADOW_EXAM_IDS=
```

Then:

```text
recreate app-plane only if only app/env changed
confirm health 200
confirm queue/hybrid OFF
confirm summary tool PASS
confirm pending/processing/deadletter state documented
```

Cleanup rules:

```text
no broad Redis deletion
exact synthetic keys only and only after approval
prefer TTL-based cleanup for shadow evidence
synthetic DB rows cleanup only in staging and only through reviewed cleanup script
preserve sanitized diagnostics before cleanup
```

If a data service was changed in staging:

```text
Redis/Celery topology rollback must follow staging maintenance plan
production data-service rollback procedures do not apply unless separately approved
```

## 12. Harness implementation guardrails

If a script is implemented later, it must include hard safety checks:

```text
refuse if APP_ENV=production
refuse if target host is production domain/IP
refuse if synthetic prefix is missing
refuse if --i-understand-this-is-staging-only flag is absent
redact IDs by default
never print raw answer values
do not write CSV/session artifacts by default
write temporary artifacts outside Git tree
```

Suggested command shape:

```text
python scripts/staging_forced_flush_proof.py preflight --staging-only
python scripts/staging_forced_flush_proof.py run-all --synthetic-prefix __PHASE6_FORCE_FLUSH_TEST__ --redact
python scripts/staging_forced_flush_proof.py summarize --fail-on-mismatch
```

The script must not contain production credentials or hardcoded production endpoints.

## 13. Production canary relationship

This staging proof is a prerequisite, not approval.

Even if staging proof passes:

```text
Phase 6 production remains NO
queue/hybrid production remains NO
Redis source-of-truth remains NO
production canary remains NO until separate canary proposal and explicit approval
```

A future production canary proposal must reference the staging proof result and still use:

```text
session/exam allowlist only
percentage rollout disabled
clear preflight gates
clear rollback steps
explicit operator approval text
```

## 14. Decision matrix

| Decision | Status | Reason |
| --- | --- | --- |
| Build production runtime now | NO | this is source-only planning |
| Run proof on VPS production | NO | production load/runtime changes forbidden |
| Implement staging harness next | MAYBE, after review | source-only script with production refusal guards |
| Require Redis noeviction answer topology | YES | from Phase 6.5a |
| Require dedicated answer_flush worker | YES | from Phase 6.5b |
| Require checker/summary gates | YES | Phase 6.3/6.4 tools are mandatory gates |
| Production canary after this doc | NO | requires actual staging proof PASS and separate approval |

Final recommendation:

```text
Review this Phase 6.5c plan. If approved, next work should be a source-only staging harness script with hard production-refusal guards and tests for those guards. Do not run it against production.
```
