# Phase 4.3.2H — Direct-300 Client Failure + DB Pressure Investigation

Phase ini menindaklanjuti Phase 4.3.2G production-live revalidation. Phase 5 tetap diblokir.

Scope fase ini: investigasi dan tooling/instrumentation saja. Tidak ada production deploy, restart, migration, synthetic rerun, APK build, atau aktivasi hybrid/queue/runtime-buffer.

## 1. Latest Reviewed GitHub State

Reviewed branch head:

```text
ded4b1388603382a2dc5de60cc16109cd5835f19 docs: record phase 4.3.2g revalidation
```

No new remote commits were found after `ded4b` before Phase 4.3.2H changes started.

## 2. Phase 4.3.2G Problem Statement

Direct-100 after the Phase 4.3.2G runtime patch passed and materially improved latency.

Direct-300 did **not** pass the gate:

| Metric | Phase 4.3.2F | Phase 4.3.2G |
|---|---:|---:|
| Failures | 0 | 5 client status 0 |
| Answer p95 | 18,498.30ms | 15,802.07ms |
| Answer p99 | 28,242.70ms | 23,573.50ms |
| Answer max | 53,663.94ms | 47,190.70ms |
| DB active max | 38 | 56 |
| DB idle-in-transaction max | 57 | 88 |
| Redis rejected | 0 | 0 |
| Redis evicted | 0 | 0 |

Direct-600 was skipped because direct-300 did not pass.

## 3. Current Interpretation

### 3.1 Client `status 0` failures

`status 0` is produced by `scripts/load_test_answer_sync.py` when `httpx` raises an exception. Before this phase, the helper collapsed every exception into only `status_code=0`, without recording exception class.

The most likely causes are:

1. `httpx.ReadTimeout`, `PoolTimeout`, `ConnectTimeout`, or connection reset;
2. local load generator saturation or socket pressure;
3. upstream response tail exceeding the helper timeout;
4. Nginx/upstream retry interaction under slow backend tail.

Why timeout is plausible:

- load helper timeout was fixed at `connect=10s`, `read=30s`, `write=30s`, `pool=30s`;
- direct-300 answer max was ~47.19s;
- success latency tail already exceeded 30s, so some requests may fail on client-side timeout while others complete later.

This is not yet proven. The Phase 4.3.2H load-helper patch records sanitized exception class counts so the next rerun can distinguish `ReadTimeout` vs `PoolTimeout` vs connection errors.

### 3.2 DB active / idle-in-transaction increase

The direct answer hot path still has multiple DB phases:

1. session probe SELECT;
2. explicit commit after probe;
3. SEB key validation cache/DB lookup;
4. question validation cache/DB lookup;
5. session advisory lock;
6. session row lock;
7. answer UPSERT;
8. commit;
9. Redis/runtime markers;
10. progress publish skipped during peak mode.

Potential pressure sources:

- transaction scope after SEB/question DB lookups may remain open until write commit;
- session-level advisory lock + row lock serialize overlapping writes per session;
- PgBouncer transaction pooling + many API worker processes can produce many active/idle sampled sessions under 300 VU;
- `get_db` dependency performs a final commit at request teardown, although the service already commits; this did not obviously cause long `idle in transaction >5s`, but should be watched;
- one-question synthetic data intentionally stresses identical `session_id + question_id` UPSERT/no-op contention and mirrors repeated autosave retry behavior.

Phase 4.3.2G post-run showed DB active >5s max 0, so the sampled idle-in-transaction pressure appears short-lived, but the count increased enough to block Phase 5 confidence.

### 3.3 Final-submit coupling

Final-submit path was not changed by Phase 4.3.2G and sample final-submit succeeded:

- direct-100: 2/2 success;
- direct-300: 6/6 success.

Current evidence does not show final-submit data correctness regression. However, submit waves still share DB/PgBouncer capacity, so they must remain in future measurement.

## 4. Patch Summary

### 4.1 Runtime instrumentation — opt-in only

Files:

```text
app/config.py
app/services/answer_sync_service.py
docker-compose.production.yml
```

New env flags:

```env
ANSWER_HOT_PATH_TIMING_ENABLED=false
ANSWER_HOT_PATH_TIMING_THRESHOLD_MS=1000
```

Default remains disabled.

When enabled, answer hot-path timing logs are emitted only when total hot-path time is at or above threshold. Log marker:

```text
SUBMIT-ANSWER-TIMING
```

Captured timing keys:

- `rate_limit_ms`
- `session_probe_ms`
- `probe_commit_ms`
- `seb_validation_ms`
- `question_validation_payload_ms`
- `answer_validation_ms`
- `session_advisory_lock_wait_ms`
- `session_row_lock_wait_ms`
- `upsert_execute_ms`
- `upsert_rowcount`
- `commit_ms`
- `runtime_marker_ms`
- `legacy_cache_marker_ms`
- `progress_publish_ms`
- fallback path keys if the legacy non-unique fallback ever triggers

Safety:

- no answer text logged;
- no token/session token logged;
- no raw request body logged;
- no PII logged beyond existing numeric session/question identifiers already present in operational logs;
- no behavior change while flag is false.

### 4.2 Load-test helper diagnostics

File:

```text
scripts/load_test_answer_sync.py
```

The helper now includes sanitized `error_counts` in summary output for client-side exceptions. Example shape:

```json
{
  "status_counts": {"0": 5, "200": 11785},
  "error_counts": {"ReadTimeout": 5}
}
```

No raw token/session/PII is included in summary.

## 5. Measurement Plan for Next Approved Rerun

Do not rerun production without explicit approval, fresh backup, no active windows, and synthetic-only setup.

Recommended next run should collect:

1. load helper `error_counts`;
2. `SUBMIT-ANSWER-TIMING` logs with threshold e.g. 1000ms or 5000ms;
3. PgBouncer:
   - `SHOW POOLS`;
   - `SHOW STATS`;
   - waiting clients / active clients;
4. Postgres `pg_stat_activity`:
   - state distribution;
   - `wait_event_type`, `wait_event`;
   - transaction age;
   - query age;
   - lock waits;
5. Nginx access/error logs around status 0 window:
   - upstream response time;
   - upstream connection/header times;
   - reset/timeout lines;
6. host load generator resources:
   - CPU/load;
   - open file/socket counts if available.

## 6. Recommended Decision Rules

- If `error_counts` is mostly `ReadTimeout` and server logs show successful late responses, tune load helper timeout only for measurement and continue backend timing analysis.
- If `PoolTimeout` dominates, inspect load-generator connection limits and host socket exhaustion before blaming server.
- If `ConnectError`/reset dominates, inspect Nginx/upstream logs and API worker restarts.
- If backend timing shows long `session_advisory_lock_wait_ms` or `session_row_lock_wait_ms`, focus on session-level overlapping autosaves and client de-dupe/debounce.
- If `upsert_execute_ms` or `commit_ms` dominates, focus DB write/WAL/pool behavior.
- If `seb_validation_ms` or `question_validation_payload_ms` dominates, inspect cache misses and transaction boundaries around read phases.

## 7. Phase Decision

Phase 4.3.2H current status:

```text
instrumentation patch ready; production revalidation pending explicit approval
```

Phase 5:

```text
still blocked
```
