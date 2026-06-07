# Phase 6.3 Repeated Validation Report / Plan

Date: 2026-06-07

## 1. Purpose

This report summarizes the validated Phase 6.2e repeated shadow evidence and defines the next Phase 6.3 validation posture. It is not a production enablement approval.

## 2. Current evidence baseline

Latest completed validation:

```text
Phase 6.2e repeated shadow validation
synthetic sessions: 3
answer save paths: PASS
checker-before payload_hash_mismatch=0: PASS for all sessions
final submit HTTP 200/submitted: PASS for all sessions
post-final SHADOW_POST_FINAL_REFRESH_OK log marker: PASS for all sessions
checker-after payload_hash_mismatch=0: PASS for all sessions
redis_errors=0: PASS
queue/hybrid evidence: 0
runtime buffer production keys: 0
answer queue keys: 0
shadow disabled after validation: PASS
```

## 3. What was proven

```text
1. Direct PostgreSQL answer save remains stable with shadow enabled for synthetic allowlisted sessions.
2. Redis shadow stores hash-only mirrors, not raw answer content.
3. The Phase 6.2a numeric normalization class remains fixed.
4. The Phase 6.2c post-final shadow refresh fixes final-submit staleness.
5. The Phase 6.2e observability patch makes SHADOW_POST_FINAL_REFRESH_OK visible in Docker/app logs.
6. Final submit remains PostgreSQL/direct and does not read Redis shadow for grading/status.
7. Redis shadow refresh is best-effort and not source-of-truth.
```

## 4. What was not proven

```text
1. Queue/hybrid production readiness was not proven.
2. Redis runtime buffer as source-of-truth was not proven and remains disallowed.
3. Forced flush under production-like worker topology was not proven.
4. Celery answer flush readiness was not proven.
5. Production canary safety was not approved or tested.
6. Broad cohort or percentage rollout was not tested.
```

## 5. Remaining hard blockers before Phase 6 production

```text
Redis maxmemory-policy remains allkeys-lru, unsafe for answer source-of-truth.
Celery worker remains solo pool/concurrency=1, not ready for answer flush production.
No forced-flush proof under staging/canary topology.
No approved production canary plan.
No queue/hybrid production approval.
```

## 6. Recommended Phase 6.3 validation plan

Phase 6.3 should remain default-OFF/source-safe and use only synthetic or controlled non-real sessions unless a separate operator approval expands scope.

Recommended sequence:

```text
1. Repeat allowlisted synthetic validation with 5 sessions if operator wants a larger sample.
2. Add an automated read-only report that summarizes checker-before/checker-after across sampled sessions.
3. Add stale-key aging/TTL reporting so old synthetic shadow keys cannot confuse future checker runs.
4. Add explicit log marker checks for SHADOW_POST_FINAL_REFRESH_OK and SHADOW_POST_FINAL_REFRESH_FAILED.
5. Keep percentage rollout disabled; use session allowlist only.
6. Keep ANSWER_WRITE_MODE=direct and ANSWER_QUEUE_ENABLED=false.
```

## 7. Production posture

```text
Phase 6 production: NO
Queue/hybrid production: NO
Redis source-of-truth: NO
Runtime buffer production: NO
Percentage rollout: NO
```

## 8. Next required approval for any further validation

Any further shadow validation should require a separate explicit operator approval and a precise test scope.

Suggested approval text:

```text
approve Phase 6.3 repeated shadow validation for synthetic sessions only
```

## 9. Final recommendation

```text
Use Phase 6.2e evidence as a successful shadow/readiness milestone, not as production queue/hybrid authorization. Continue with Phase 6.3 validation/reporting improvements while keeping production in direct PostgreSQL mode.
```
