# Phase 4.3.2G — Production-Live Revalidation Report

This report records the approved production-live revalidation of commit `be684df9ac8730c3342376bd55a519621dcf7ece`.

Scope: validate the direct answer write-path latency remediation from Phase 4.3.2G. This was **not** Phase 5 rollout.

## 1. Reviewed GitHub State

Remote branch before production action:

```text
be684df9ac8730c3342376bd55a519621dcf7ece perf: reduce direct answer write latency pressure
```

No new remote commits were found after `be684df` before the revalidation started.

## 2. Operator Approval

Operator explicitly approved production-live revalidation with these boundaries:

- deploy patch `be684df`;
- create and verify a fresh production DB safety snapshot before write/load tests;
- verify no active published exam windows and no in-progress sessions before synthetic data creation;
- run dry-run, direct-100, direct-300, direct-600 only if previous tier passes;
- use synthetic data only;
- cleanup exact synthetic prefixes;
- report sanitized results.

## 3. Production Actions Performed

Performed:

- Fresh DB safety snapshot created and verified.
- One runtime file from `be684df` deployed:
  - `app/services/answer_sync_service.py`
- API/admin API containers were restarted one by one after file deployment.
- DB, Redis, PgBouncer, and Nginx were **not** restarted.
- Synthetic data was created and later cleaned up.
- Direct-100 and direct-300 were executed.
- Direct-600 was **not executed** because direct-300 did not pass the gate.

Not performed:

- no DB schema migration;
- no public endpoint contract change;
- no APK/AAB build;
- no hybrid/queue/runtime-buffer activation;
- no Nginx config change;
- no real student account/session/answer use;
- no raw token/session CSV/summary JSON committed.

## 4. Fresh Safety Snapshot

Fresh production DB safety snapshot:

| Field | Value |
|---|---|
| Path | `/root/ujian_online/backups/backup_20260604_015400_pre_phase432g.sql.gz` |
| Size | 11,382,968 bytes |
| Integrity | `gzip -t`: pass |
| SHA256 prefix | `5e59009fc18632c3` |
| Exported/committed | no |

## 5. Preflight Gate

Initial read-only preflight and pre-write gate:

| Check | Result |
|---|---:|
| Active published exam windows | 0 |
| Global in-progress sessions before synthetic data | 0 |
| Next published start WIB | 2026-06-04 07:30:00 |
| API `/health` after deploy | 200 |
| PgBouncer health | healthy |
| Redis rejected connections | 0 |
| Redis evicted keys | 0 |

Safe-mode env sample after deploy:

```env
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
EXAM_PEAK_MODE=true
VIOLATION_ASYNC_ENABLED=true
ADMIN_MONITORING_DETAIL_LEVEL=summary
MOBILE_APK_PRIMARY=true
SEB_DESKTOP_LEGACY_ENABLED=false
SEB_QR_ENABLED=false
SEB_DEBUG_ENDPOINTS_ENABLED=false
APK_BUILD_ENDPOINT_ENABLED=false
TELEGRAM_ALERTING_ENABLED=false
HEAVY_EXPORT_ENABLED=false
```

Patch marker verification inside API container:

```text
HAS_CHANGED_PAYLOAD=True
HAS_PEAK_SKIP=True
```

## 6. Synthetic Data Strategy

Synthetic prefix:

```text
LOADTEST_SYNTHETIC_20260604_PHASE432G_
```

Synthetic class:

```text
LOADTEST_X_PHASE432G
```

Synthetic scope:

| Item | Count |
|---|---:|
| Synthetic users | 651 |
| Synthetic student sessions | 650 |
| Synthetic exam | 1 unpublished |
| Synthetic question | 1 |
| Synthetic options | 4 |
| Real in-progress sessions excluding synthetic | 0 |
| Active published exam windows | 0 |

Tokens and session CSV were stored only under `/tmp` and deleted during cleanup.

## 7. Dry Run

Dry-run completed with no HTTP traffic. The helper printed:

- target `http://127.0.0.1`;
- 650 unique synthetic sessions;
- direct/off safety declaration;
- masked first token;
- SEB config hash supplied.

No dry-run summary JSON was created by the helper.

## 8. Direct-100

A first direct-100 attempt returned 403 because the synthetic load-test User-Agent did not satisfy SXB middleware. This was diagnosed as a test harness issue, not a runtime patch failure. No answer rows were created by that blocked attempt. The runner was corrected to use a SEB-compatible synthetic User-Agent:

```text
Safe Exam Browser Phase432G Synthetic
```

Corrected direct-100 rerun:

| Metric | Phase 4.3.2F Baseline | Phase 4.3.2G Result |
|---|---:|---:|
| VUs | 100 | 100 |
| Duration | 180s | 180s |
| Total requests | 10,224 | 9,360 |
| Failures | 0 | 0 |
| Status distribution | 200: 10,224 | 200: 9,360 |
| Answer p50 | 193.99ms | 153.44ms |
| Answer p95 | 492.22ms | 244.06ms |
| Answer p99 | 1,903.34ms | 1,225.94ms |
| Answer max | 5,109.23ms | 3,873.55ms |
| Final-submit | 2/2 success | 2/2 success |
| Load1 max | 10.63 | 7.95 |
| DB active max | 12 | 11 |
| DB idle-in-transaction max | 16 | 8 |
| DB active >5s max | 0 | 0 |
| Redis rejected | 0 | 0 |
| Redis evicted | 0 | 0 |

Consistency after corrected direct-100:

| Check | Result |
|---|---:|
| Sessions total | 650 |
| Submitted sessions | 2 |
| In-progress sessions | 648 |
| Sessions with answers | 100 |
| Answer rows total | 100 |
| Max answers per session | 1 |
| Sessions with >1 answer | 0 |
| Terminal without answers | 0 |
| Terminal without score | 0 |
| Score out of range | 0 |
| Real in-progress excluding synthetic | 0 |

Direct-100 decision:

```text
PASS: functional/data pass with materially better latency and lower idle-tx pressure.
```

## 9. Direct-300

Direct-300 result:

| Metric | Phase 4.3.2F Baseline | Phase 4.3.2G Result |
|---|---:|---:|
| VUs | 300 | 300 |
| Duration | 300s | 300s |
| Total requests | 10,999 | 11,790 |
| Failures | 0 | 5 |
| Status distribution | 200: 10,999 | 200: 11,785; client status 0: 5 |
| Answer p50 | 4,840.34ms | 4,236.20ms |
| Answer p95 | 18,498.30ms | 15,802.07ms |
| Answer p99 | 28,242.70ms | 23,573.50ms |
| Answer max | 53,663.94ms | 47,190.70ms |
| Final-submit | 6/6 success | 6/6 success |
| Load1 max | 11.93 | 20.40 |
| DB active max | 38 | 56 |
| DB idle-in-transaction max | 57 | 88 |
| DB active >5s max | 0 | 0 |
| Redis rejected | 0 | 0 |
| Redis evicted | 0 | 0 |

Consistency after direct-300:

| Check | Result |
|---|---:|
| Sessions total | 650 |
| Submitted sessions | 6 |
| In-progress sessions | 644 |
| Sessions with answers | 300 |
| Answer rows total | 300 |
| Max answers per session | 1 |
| Sessions with >1 answer | 0 |
| Terminal without answers | 0 |
| Terminal without score | 0 |
| Score out of range | 0 |
| Real in-progress excluding synthetic | 0 |

Direct-300 decision:

```text
NO-GO: although latency improved and data consistency remained valid, there were 5 client failures and DB active/idle-tx pressure increased versus the Phase 4.3.2F baseline.
```

## 10. Direct-600

Direct-600 was skipped.

Reason:

```text
Validation rule: run direct-600 only if direct-300 passes. Direct-300 had 5 client failures and worse DB pressure, so the sequence stopped.
```

## 11. DB / PgBouncer / Redis Notes

Post-direct300 and post-cleanup health remained stable:

| Check | Result |
|---|---:|
| API `/health` | 200 |
| Active published exam windows after cleanup | 0 |
| Global in-progress sessions after cleanup | 0 |
| DB active >5s after cleanup | 0 |
| DB idle-tx >5s after cleanup | 0 |
| PgBouncer health | healthy |
| Redis rejected connections | 0 |
| Redis evicted keys | 0 |

Final recovery sample:

```text
health=200
active_published_windows=0
global_in_progress_sessions=0
next_published_start_wib=2026-06-04 07:30:00
pg_state_active=1
pg_state_idle=150
pg_active_over_5s=0
pg_idle_tx_over_5s=0
redis_rejected=0
redis_evicted=0
```

## 12. Cleanup Status

Exact synthetic cleanup was performed.

Deleted aggregate:

| Item | Deleted |
|---|---:|
| Security events | 0 |
| User activity logs | 0 |
| Exam logs | 12 |
| Answers | 300 |
| Exam sessions | 650 |
| Question options | 4 |
| Questions | 1 |
| Exams | 1 |
| Users | 651 |

Verification:

| Check | Result |
|---|---:|
| Remaining synthetic users | 0 |
| Remaining synthetic exams | 0 |
| Global in-progress sessions | 0 |
| Active published exam windows | 0 |

Temporary files deleted from `/tmp` included session CSV, token CSV, SEB hash file, summary JSON, monitor TSV, helper copy, and isolated Python dependency directory.

## 13. Risk Assessment

Positive:

- Patch deployed successfully.
- Direct-100 materially improved.
- Direct-300 p50/p95/p99/max latency improved versus Phase 4.3.2F.
- Final-submit samples succeeded at 100 and 300.
- Answer consistency checks passed.
- Redis remained stable.
- Cleanup succeeded.
- Production health recovered/held normal.

Negative:

- Direct-300 had 5 client-side failures (`status 0`).
- Direct-300 DB active max and idle-in-transaction max were worse than Phase 4.3.2F.
- Direct-600 could not be run under the validation gate.

## 14. Rollback Instruction

Code rollback if needed:

```bash
git revert be684df9ac8730c3342376bd55a519621dcf7ece
```

Then redeploy safe-mode direct/off in a safe window.

DB restore is not recommended because exact-prefix cleanup succeeded and health is normal. The fresh safety snapshot remains on the VPS for emergency reference only and must not be committed/exported.

## 15. Decision

Phase 4.3.2G code remediation:

```text
PASS
```

Phase 4.3.2G production-live performance validation:

```text
PARTIAL / NO-GO for full performance pass
```

Reason:

- direct-100 passed and improved;
- direct-300 latency improved but had 5 client failures and worse DB pressure;
- direct-600 was skipped because direct-300 did not pass the gate.

Phase 5:

```text
still blocked
```

Recommended next step:

```text
Investigate direct-300 client status 0 failures and DB active/idle-tx increase before any Phase 5 proposal. Focus next on connection/pool pressure, request timeout sources, and session-lock/query timing instrumentation for the answer hot path.
```
