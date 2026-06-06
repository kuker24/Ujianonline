# Phase 5/6 VPS Architecture Readiness Audit - 2026-06-06

## 1. Executive summary

Audit ini bersifat **read-only** terhadap VPS Ujian Online. Tidak ada deploy, restart,
migration, load-test besar, build APK, edit `.env`, atau aktivasi Phase 5/6.

Keputusan konservatif:

- Current production live mode tetap **direct safe-mode**.
- `ANSWER_WRITE_MODE=direct`, `ANSWER_QUEUE_ENABLED=false`, `ANSWER_QUEUE_PERCENTAGE=0`.
- Phase 5 direct consolidation: **PARTIAL / mostly complete for active routes**, tetapi masih perlu hardening source-only dan review beberapa dependency/Redis failure edge sebelum diklaim selesai penuh.
- Phase 6 runtime buffer production: **NOT READY**.
- Phase 6 shadow/default-off: **PARTIAL / reasonable to design as default-off only**, setelah menambah consistency checker, metrics, cleanup, dan guard tests.
- Queue/hybrid production: **NO**. Jangan aktifkan `ANSWER_QUEUE_ENABLED=true`, `ANSWER_WRITE_MODE=queue`, atau `ANSWER_WRITE_MODE=hybrid` sebelum ada bukti shadow/canary dan approval operator.

Fakta penting:

- VPS `/root/ujian_online` **bukan git checkout**.
- API/worker memakai **bind-mounted source** dari `/root/ujian_online/app -> /app/app`.
- Sebagian live source **tidak sama** dengan GitHub head `48d130a`; terutama `answer_sync_service.py`, `app/config.py`, dan host `docker-compose.production.yml` belum memuat marker `SUBMIT-ANSWER-TIMING` / env timing dari GitHub.
- Redis punya headroom besar saat audit, tetapi eviction policy `allkeys-lru` **tidak aman** untuk answer buffer sebagai source of truth.
- PostgreSQL tidak sedang bottleneck pada saat audit, tetapi tabel `answers` adalah write hotspot historis dan direct-300 tetap NO-GO performa.
- Celery worker sehat tetapi `--pool=solo` concurrency 1; ini belum cukup untuk answer flush production tanpa worker plane terpisah/observability.

## 2. Latest GitHub head reviewed

Branch target: `review/sanitized-root-20260531-115153`

Reviewed head:

```text
48d130ad184a835c7bf911dfc6a61891eeb40591
48d130a docs: record operator APK UI smoke pass
```

Comparison:

```text
base = 48d130ad184a835c7bf911dfc6a61891eeb40591
head = 48d130ad184a835c7bf911dfc6a61891eeb40591
commits base..head = 0
```

Result:

- No new commits after the provided base.
- No new forbidden artifacts in diff.
- No unexpected Phase 5/6 activation in diff.

## 3. VPS safety preflight

Collected read-only at `2026-06-06T20:54:52+07:00`.

| Check | Result |
|---|---:|
| Hostname | `adminujian` |
| Timezone | `Asia/Jakarta (WIB, +0700)` |
| App root | `/root/ujian_online` |
| Public/local `/health` | 200 |
| Active exam windows | 0 |
| In-progress/active/paused sessions | 0 |
| Active final-submit queries | 0 |
| Active drain queries | 0 |
| Long active DB queries > 60s | 0 |
| Idle-in-transaction | 0 |
| Disk `/` | 52% used |
| Redis ping | `PONG` |
| PostgreSQL `pg_isready` | accepting connections |
| Production load-test process | no match after strict recheck |

No restart/deploy/migration/load-test was performed.

## 4. VPS deployment model

VPS app root:

```text
/root/ujian_online
```

Deployment model:

- `/root/ujian_online` is **not a git checkout** (`.git` absent).
- Runtime source is mostly **copied files on host** and **bind-mounted** into containers.
- API image exists (`ujian_online-api`), but active code comes from host bind mounts for `/app/app`, `/app/static`, `/app/templates`, etc.
- Docker image may contain older copied files, but bind mounts override the app source for API containers.

Important mounts:

```text
/root/ujian_online/app -> /app/app                    rw
/root/ujian_online/static -> /app/static              rw
/root/ujian_online/templates -> /app/templates        rw
/root/ujian_online/uploads -> /app/uploads            rw
/root/ujian_online/apk_builds -> /app/apk_builds      rw
/root/ujian_online/logs -> /app/logs                  rw
/root/ujian_online/runtime_control -> /app/runtime_control rw
```

## 5. Container/service map

| Service | Container | Image | Status at audit |
|---|---|---|---|
| API primary | `ujian_online-api-1` | `ujian_online-api` | healthy |
| API replicas | `ujian_online-api2-1` ... `api8-1` | `ujian_online-api` | healthy |
| Admin APIs | `ujian_online-api_admin-1`, `api_admin2-1` | `ujian_online-api` | healthy |
| Celery worker | `ujian_online-celery_worker-1` | `ujian_online-celery_worker` | healthy |
| Celery beat | `ujian_online-celery_beat-1` | `ujian_online-celery_beat` | healthy |
| Nginx | `ujian_online-nginx-1` | `nginx:alpine` | healthy |
| PostgreSQL | `ujian_online-db-1` | `postgres:15-alpine` | healthy |
| PgBouncer | `ujian_online-pgbouncer-1` | `ujian_online-pgbouncer` | healthy |
| Redis | `ujian_online-redis-1` | `redis:7-alpine` | healthy |
| Prometheus/Grafana | `prometheus`, `grafana` | official images | healthy |

## 6. VPS live commit/marker evidence

Because VPS app root is not git, evidence is checksum/marker based.

| File | Host exists | Container exists | Host SHA256 | Container SHA256 | GitHub SHA256 | Matches GitHub | Relevant markers / interpretation |
|---|---:|---:|---|---|---|---:|---|
| `app/services/answer_sync_service.py` | yes | yes | `3fd39d4a...b29eeabf` | `3fd39d4a...b29eeabf` | `707862b4...6432381d` | no | Live has direct/queue/hybrid branches, no-op update skip, peak progress skip, journal idempotency. **GitHub timing marker `SUBMIT-ANSWER-TIMING` is not live**. |
| `app/services/final_submit_service.py` | yes | yes | `d2eb6754...202f3ddb` | same | same | yes | Priority final submit, queue/runtime flush branches guarded by flags, session advisory lock. |
| `app/api/exams.py` | yes | yes | `9e2ed370...a50eba0` | same | same | yes | Start/resume/admin runtime routes match GitHub. |
| `app/api/answer_sync.py` | yes | yes | `dda30d6e...baf854d` | same | same | yes | `/submit-answer` delegates to `AnswerSyncService`. |
| `app/api/final_submit.py` | yes | yes | `04edc7d8...8f339ad` | same | same | yes | `/submit` delegates to `FinalSubmitService`. |
| `app/api/violation_events.py` | yes | yes | `e71149c8...2c0d8f1f0` | same | same | yes | Adaptive critical-only violation fallback live. |
| `app/core/runtime_policy.py` | yes | yes | `d84bd264...9c2f359a` | same | same | yes | Mobile adaptive policy live. |
| `app/config.py` | yes | yes | `a63b8b87...2828896f` | same | `30800a4d...dd4407` | no | Live lacks `ANSWER_HOT_PATH_TIMING_*` settings from GitHub. |
| `app/database.py` | yes | yes | `0219eb76...354f879` | same | same | yes | PgBouncer-aware SQLAlchemy settings. |
| `docker-compose.production.yml` | yes | image copy also exists | `b375cd47...ecb3e90d4` | `6cc92421...526dd63` | `ec1d45f2...a1de06` | no | Host compose controls deployment and lacks GitHub timing env. Container copy is not runtime control source. |

Interpretation:

- Live app code is mostly aligned with GitHub head, but not perfectly.
- The most important mismatch is that Phase 4.3.2H hot-path timing instrumentation exists in GitHub source but is **not deployed** on VPS.
- This audit did not change or deploy those differences.

## 7. Safe-mode env audit

Secret-bearing values are masked.

| Flag | `.env` | compose fallback | container effective | Expected safe value | Status |
|---|---|---|---|---|---|
| `ANSWER_WRITE_MODE` | `direct` | `${ANSWER_WRITE_MODE:-direct}` | `direct` | `direct` | OK |
| `ANSWER_QUEUE_ENABLED` | `false` | `${ANSWER_QUEUE_ENABLED:-false}` | `false` | `false` | OK |
| `ANSWER_QUEUE_PERCENTAGE` | `0` | `${ANSWER_QUEUE_PERCENTAGE:-0}` | `0` | `0` | OK |
| `ANSWER_SYNC_INTERNAL_SERVICE` | unset | unset | unset | unset/disabled | OK |
| `ANSWER_HOT_PATH_TIMING_ENABLED` | unset | absent live | unset | `false` | OK, instrumentation not live |
| `ANSWER_HOT_PATH_TIMING_THRESHOLD_MS` | unset | absent live | unset | `1000` if deployed | OK, instrumentation not live |
| `EXAM_PEAK_MODE` | `true` | `${EXAM_PEAK_MODE:-false}` | `true` | `true` during exam-safe mode | OK |
| `VIOLATION_ASYNC_ENABLED` | `true` | `${VIOLATION_ASYNC_ENABLED:-true}` | `true` | `true` | OK |
| `ADMIN_MONITORING_DETAIL_LEVEL` | `summary` | `${ADMIN_MONITORING_DETAIL_LEVEL:-summary}` | `summary` | `summary` | OK |
| `MOBILE_APK_PRIMARY` | `true` | `${MOBILE_APK_PRIMARY:-true}` | `true` | `true` | OK |
| `SEB_DESKTOP_LEGACY_ENABLED` | `false` | `${SEB_DESKTOP_LEGACY_ENABLED:-false}` | `false` | `false` | OK |
| `SEB_QR_ENABLED` | `false` | `${SEB_QR_ENABLED:-false}` | `false` | `false` | OK |
| `SEB_DEBUG_ENDPOINTS_ENABLED` | `false` | `${SEB_DEBUG_ENDPOINTS_ENABLED:-false}` | `false` | `false` | OK |
| `APK_BUILD_ENDPOINT_ENABLED` | `false` | `${APK_BUILD_ENDPOINT_ENABLED:-false}` | `false` | `false` | OK |
| `TELEGRAM_ALERTING_ENABLED` | `false` | `${TELEGRAM_ALERTING_ENABLED:-false}` | `false` | `false` | OK |
| `HEAVY_EXPORT_ENABLED` | `false` | `${HEAVY_EXPORT_ENABLED:-true}` | `false` | `false` | OK effective; compose fallback would be risky without `.env` |
| `REDIS_URL` | masked | masked | masked | Redis service | OK |
| `DATABASE_URL` | masked direct DB in `.env` | masked PgBouncer fallback | masked PgBouncer effective | PgBouncer effective | OK effective |
| `DB_POOL_SIZE` | `12` | `${DB_POOL_SIZE:-12}` | `12` | conservative | OK |
| `DB_MAX_OVERFLOW` | `18` | `${DB_MAX_OVERFLOW:-18}` | `18` | conservative | OK |
| `DB_POOL_TIMEOUT` | `35` | `${DB_POOL_TIMEOUT:-35}` | `35` | acceptable | OK |
| `DB_POOL_RECYCLE` | `180` | `${DB_POOL_RECYCLE:-180}` | `180` | acceptable | OK |

App settings confirmed:

```text
answer_write_mode=direct
answer_queue_enabled=false
answer_queue_percentage=0
answer_queue_flush_on_submit=false
exam_peak_mode=true
violation_async_enabled=true
mobile_apk_primary=true
```

Runtime policy endpoint:

```text
mode=exam_peak
resource_mode=normal
cheating_reporting_mode=normal
disabled_violation_types=[]
final_submit_priority=true
policy_version=20260606-mobile-runtime-adaptive-v2
```

## 8. Live route and hot-path map

### P0 - final submit

| Field | Value |
|---|---|
| URL/method | `POST /api/exams/submit` |
| Router | `app.api.final_submit.submit_exam` |
| Service | `FinalSubmitService.submit_exam` |
| DB writes | `exam_sessions` status/end/score; `answers` scoring fields; `exam_logs` submission/breakdown |
| Redis writes | best-effort session state update; monitoring publish/delta |
| Transaction scope | probe transaction committed before SEB/network work; final lock/load/finalize in DB transaction |
| Locks | `pg_advisory_xact_lock(namespace=48102, session_id)`, row `FOR UPDATE` |
| Background tasks | none required for direct mode; monitoring publish best-effort |
| Response behavior | idempotent submitted response if already submitted/completed |
| Failure behavior | 503 on transient DB pressure; 500 on finalize failure |
| Can be blocked by | DB lock/load, SEB validation, rate limit; not by violation/monitoring best-effort |
| Phase 5/6 notes | Final submit must stay highest priority; Phase 6 requires session-scoped forced flush before grading |

### P1 - submit-answer

| Field | Value |
|---|---|
| URL/method | `POST /api/exams/submit-answer` |
| Router | `app.api.answer_sync.submit_answer` |
| Service | `AnswerSyncService.accept_single_answer` |
| DB writes | direct `INSERT ... ON CONFLICT DO UPDATE` into `answers` unless queue/hybrid selected; currently direct |
| Redis writes | answered marker/count and monitoring publish best-effort after commit |
| Transaction scope | session probe commits before SEB/question/cache work; answer upsert committed before Redis post-work |
| Locks | session advisory lock + session row `FOR UPDATE`; fallback answer row advisory lock if unique constraint missing |
| Background tasks | queue enqueue only if queue flags active; inactive today |
| Response behavior | `saved`; post-submit autosave returns no-op saved message |
| Failure behavior | 503 transient DB pressure; 409 write conflict |
| Can block final submit | only by contending on same session advisory/row lock; short direct write expected |
| Phase 5/6 notes | Active hot path uses AnswerSyncService. GitHub timing instrumentation not live. |

### P1 - legacy auto-save

| Field | Value |
|---|---|
| URL/method | `POST /api/exams/auto-save` |
| Router | `app.api.exam_answer_sync.auto_save_answers` |
| Service | `AnswerSyncService.accept_legacy_autosave` |
| DB writes | none; validates session via SELECT |
| Redis writes | `update_session_answers`, answered count/runtime snapshot |
| Transaction scope | read dependency currently points to write engine because no read replica; no DB commit from route |
| Locks | none |
| Failure behavior | Redis marker path is not fully best-effort at first `update_session_answers`; Redis outage may fail this legacy endpoint |
| Phase 5/6 notes | Not an answer DB write; does not affect final scoring source of truth. |

### P1 - auto-save-batch

| Field | Value |
|---|---|
| URL/method | `POST /api/exams/auto-save-batch` |
| Router | `app.api.exam_answer_sync.auto_save_batch` |
| Service | `AnswerSyncService.accept_batch` |
| DB writes | direct ORM update/insert into `answers`; no-op skip on unchanged payload |
| Redis writes | `update_session_answers`, answered count/runtime snapshot after DB commit |
| Transaction scope | validates session/question, advisory+row lock, commits changed rows before Redis post-work |
| Locks | session advisory lock + session row `FOR UPDATE`; serialized retry on conflict |
| Failure behavior | DB conflict retries serialized; Redis marker after commit is not fully isolated from response failure |
| Phase 5/6 notes | Uses service and direct mode. In runtime buffer mode can route to `AnswerRuntimeBufferService`, but flags OFF. |

### P1 - answer journal sync

| Field | Value |
|---|---|
| URL/method | `POST /api/exams/answer-journal/sync` |
| Router | `app.api.exam_answer_sync.sync_answer_journal` |
| Service | `AnswerSyncService.accept_journal_events` |
| DB writes | latest accepted event per question applied to `answers` direct mode |
| Redis writes | idempotency set `exam:answer-journal:v1:session:{id}:event-ids`; answered markers |
| Transaction scope | classify events then session lock/apply/commit; Redis idempotency write after commit best-effort |
| Locks | session advisory lock + session row `FOR UPDATE` |
| Failure behavior | initial Redis idempotency read depends on Redis; if Redis is down, journal sync can fail before DB apply |
| Phase 5/6 notes | Journal idempotency exists but relies on Redis. Shadow/Phase 6 must preserve event-id semantics. |

### P1 - runtime policy

| Field | Value |
|---|---|
| URL/method | `GET /api/runtime/policy` |
| Router | `app.api.runtime.get_runtime_policy_endpoint` |
| Writes | none |
| Redis | reads degrade/resource mode if available; safe fallback |
| Phase notes | Adaptive violation policy live; does not enable answer queue/hybrid. |

### P2 - start/resume/admin commands

| Path | Notes |
|---|---|
| `POST /api/exams/{exam_id}/start` | Creates/resumes session, uses Redis cache/lock for start validation, stores session snapshot. |
| `GET /api/exams/session/{session_id}/resume` | Session restore path; Redis session state used for timer/status. |
| Admin emergency/force/reset routes | Can mutate sessions but are admin-scoped. Not part of answer hot path. |

### P3 - violation/monitoring

| Path | Notes |
|---|---|
| `POST /api/exams/log-violation` | Async violation enqueue; adaptive policy may ignore non-critical during degraded mode. Should not block answer/final-submit. |
| `/api/monitoring/*` | Summary/detail monitoring, restart-safe/admin resource endpoints. Summary detail mode active. |

Current direct mode diagram:

```text
APK/Web
  -> endpoint (/submit-answer, /auto-save-batch, /answer-journal/sync)
  -> auth/session validate
  -> AnswerSyncService
  -> PostgreSQL direct write (source of truth)
  -> Redis marker/count best-effort or semi-best-effort
  -> response
```

Future Phase 6 target diagram (not active):

```text
APK/Web
  -> endpoint
  -> auth/session validate
  -> Redis runtime buffer
  -> quick response
  -> worker batch flush DB
  -> final submit forced flush
  -> grading from PostgreSQL
```

## 9. Answer write path deep audit

Answers to required questions:

1. Endpoints still writing directly to PostgreSQL: `/submit-answer`, `/auto-save-batch`, `/answer-journal/sync` in direct mode.
2. Active legacy answer endpoints route through `AnswerSyncService`.
3. Bypass paths exist in source but inactive by flags: `app.tasks.answer_processor` legacy Redis queue worker and `app.services.answer_runtime_buffer` runtime buffer flush. Admin/final-submit grading also updates answer score fields.
4. Direct single answer uses PostgreSQL upsert with `where=changed_answer_payload` no-op update skip.
5. `answered_at` is intentionally excluded from duplicate comparison in single-answer upsert.
6. Metadata merge uses `merge_statement_answer_metadata`; batch/journal merge existing metadata before writing.
7. `statement_answers` are merged into answer metadata safely via helper.
8. Journal idempotency exists via Redis event-id set with 48h TTL.
9. Session ownership validated by `ExamSession.user_id == current_user.id`.
10. Question validity checked against exam/question cache or DB query.
11. Session status checked as `in_progress` for direct writes; submitted/completed returns no-op for single-answer.
12. Locks: session advisory lock namespace `48102`; session row `FOR UPDATE`; fallback answer row advisory lock.
13. Single-answer direct path commits before Redis post-work. Batch/journal commit before some Redis marker work. Some Redis calls still happen before/after DB and can affect endpoint response in legacy/journal paths.
14. During `EXAM_PEAK_MODE=true`, progress publish is skipped for single-answer.
15. Single-answer Redis marker/count failures are handled best-effort/debug. Batch/journal have partial gaps around `update_session_answers` and initial idempotency read.
16. If Redis is down: `/submit-answer` direct DB write should still persist; `/auto-save`, `/auto-save-batch`, `/answer-journal/sync` can still have response risks depending on Redis call point.
17. If PostgreSQL write fails: transient pressure maps to 503 retry; other conflicts map to 409 or endpoint-specific errors.
18. Autosave after submitted: single-answer returns no-op success; batch/journal typically 404/400 because they require active/in_progress session.
19. Idempotency for APK retry/backoff is good for single-answer and improved for batch no-op; journal uses event IDs.
20. Metrics/logs today: route-level monitoring/runtime policy exists; live `SUBMIT-ANSWER-TIMING` instrumentation is **not deployed** even though present in GitHub.

Bypass findings:

| Path | Active today? | Risk |
|---|---:|---|
| `AnswerSyncService._write_single_answer_direct` | yes | expected source of truth direct write |
| `AnswerSyncService.accept_batch` ORM update/add | yes | expected direct batch write, but Redis post-marker failure can affect response after commit |
| `AnswerSyncService.accept_journal_events` ORM update/add | yes | expected direct journal write; Redis idempotency dependency should be reviewed |
| `app.tasks.answer_processor._upsert_answer` | no, flags OFF and queues empty | legacy queue worker bypasses service semantics; needs alignment before queue mode |
| `app.services.answer_runtime_buffer._flush_session_buffer` | no, flags OFF | Phase 6 flush path exists but not proven; no deadletter/consistency checker yet |
| `FinalSubmitService` / `exam_submission_service` answer score updates | yes on submit | expected grading, not autosave bypass |

## 10. Final submit path deep audit

Required answers:

1. Endpoint: `POST /api/exams/submit`.
2. Service: `FinalSubmitService.submit_exam`.
3. Idempotent: yes, already submitted/completed returns submitted response with stored score when available.
4. Locks session: yes, advisory lock namespace `48102` and row `FOR UPDATE`.
5. Prevent/ignore late autosave: single-answer late write returns no-op success; batch/journal reject non-active session.
6. Grade once: service checks submitted before finalizing; duplicate request returns existing result.
7. Queue/runtime dependency today: no, because flags are OFF. Flush branches are no-op unless enabled.
8. Phase 6 forced flush location: `_flush_answer_buffers_before_submit()` before `_load_session_for_finalize()` / grading.
9. Before enabling Redis buffer: forced flush must be proven, Redis no eviction/rejection, worker alive, consistency checker 0 mismatch, direct rollback immediate.
10. Errors: 503 transient DB/flush pressure with retry-after; 500 finalize failure; 400/404 invalid session.
11. Duplicate submits: idempotent submitted response.
12. Monitoring/violation broadcasts: best-effort after commit.
13. Redis touched today: best-effort session state update and monitoring publish; not source of truth.
14. Priority over violation/admin monitoring: design says yes; implementation keeps violation separate async and final submit direct.

Current final submit flow:

```text
POST /api/exams/submit
  -> hot-path auth
  -> rate limit
  -> session probe
  -> idempotent submitted check
  -> commit probe transaction
  -> SEB/APK header validation
  -> queue/runtime-buffer pre-flush (no-op today)
  -> advisory lock + session row FOR UPDATE
  -> load exam/questions/options/answers
  -> finalize grading and set session submitted
  -> insert exam logs
  -> commit
  -> best-effort Redis/session cache/monitor publish
  -> response
```

Non-negotiable final-submit invariants:

- Final submit must never depend on non-critical violation telemetry.
- Final submit must not wait on broad queue drain; only session-scoped forced flush is allowed.
- Grading must read persisted PostgreSQL state, unless Redis buffer has just been synchronously flushed and verified.
- Duplicate submit must remain idempotent.
- Late answer writes after submitted must not reopen/modify submitted results.

## 11. Redis usage audit

Redis facts:

| Metric | Value |
|---|---:|
| Version | 7.4.7 |
| Used memory | 11.16 MB |
| Peak memory | 12.58 MB |
| Maxmemory | 1.37 GB |
| Maxmemory policy | `allkeys-lru` |
| Rejected connections | 0 |
| Evicted keys | 0 |
| Connected clients | 29 |
| Blocked clients | 1 |
| DB0 keys | 668 |
| DB1 keys | 21,905 |
| AOF | enabled |
| AOF fsync | everysec from compose |
| RDB last bgsave | OK |
| Slowlog len | 1 |

DB0 pattern counts:

| Pattern | Count |
|---|---:|
| `runtime:*` | 3 |
| `runtime:session:*` | 0 |
| `runtime:answer*` | 0 |
| `runtime:answer_queue:*` | 0 |
| `runtime:violation:*` | 0 |
| `*answer*` | 544 |
| `*session*` | 544 |
| `*violation*` | 0 |
| `answer_queue:*` | 0 |
| `exam_session:*` | 0 |
| `exam_answers:*` | 0 |
| `exam_answered_questions:*` | 0 |

DB1/Celery:

| Pattern | Count |
|---|---:|
| `db1:celery*` | 21,888 |
| `db1:_kombu*` | 4 |

TTL findings:

- Current answer/session-like DB0 keys are primarily journal idempotency keys: `exam:answer-journal:v1:session:{id}:event-ids`.
- Runtime answer buffer keys are not present because Phase 6 is off.
- Selected runtime keys have TTLs.
- No selected DB0 answer/session/runtime pattern showed no-TTL keys in sampled counts.

Redis interpretation:

1. Current Redis is used for runtime policy/request metrics, session/journal markers, Celery broker/result backend, violation async if active, and cache/pubsub support.
2. Capacity is sufficient for **shadow/default-off** experiments: 11MB used vs 1.37GB cap.
3. Eviction policy `allkeys-lru` is **unsafe for answer buffer source-of-truth** because answer keys could be evicted under memory pressure.
4. AOF everysec helps but does not eliminate loss risk for source-of-truth answer buffer.
5. Phase 6 keys already designed in source: `runtime:session:{id}:answers`, `runtime:session:{id}:dirty_questions`, `runtime:session:{id}:answered_count`, `runtime:answer_queue:*`.
6. Rough memory estimate: 300 students x 50 questions x ~1-2KB serialized answer payload plus Redis overhead is likely tens of MB; 600 x 50 likely under ~100-200MB depending payload. Capacity is not the immediate blocker.
7. Risk of answer loss if Redis evicts keys is unacceptable for production queue/hybrid.
8. Required before source-of-truth buffer: `noeviction` or isolated Redis DB/instance with strict reserved memory, AOF verified, queue deadletter, consistency checker, and rollback.

## 12. Postgres/PgBouncer audit

PostgreSQL facts:

| Metric | Value |
|---|---:|
| Version | PostgreSQL 15.15 alpine |
| DB size | 184 MB |
| Active queries excluding audit | 0 |
| Idle connections | 59 |
| Idle-in-transaction | 0 |
| Long active > 60s | 0 |
| Lock waits | none observed |

Top write hotspot:

| Table | Total size | Live tuples | Dead tuples | Inserts | Updates | Notes |
|---|---:|---:|---:|---:|---:|---|
| `answers` | 118 MB | 264,076 | 35,368 | 96,278 | 388,957 | dominant write/update hotspot |
| `exam_sessions` | 4.7 MB | 7,205 | 1,041 | 4,306 | 3,878 | final submit/session status hotspot |
| `security_events` | 184 KB | 230 | 1 | 93 | 0 | small today |
| `exam_logs_2026_06` | 6.7 MB | 9,599 | 405 | n/a | n/a | partitioned logs active |

Important indexes:

- `answers`: `uq_answers_session_question (session_id, question_id)` unique.
- `answers`: `idx_answers_session_answered_at (session_id, answered_at DESC)`.
- `answers`: `idx_answers_question_session (question_id, session_id)`.
- `exam_sessions`: indexes by `status/exam/start`, `exam/status/end_time`, `user/exam`, partial unique active user/exam.
- `exam_logs`: partitioned indexes on `created_at`, `session_id, created_at`, `event_type, created_at`.

PgBouncer facts:

| Metric | Value |
|---|---:|
| Version | PgBouncer 1.22.1 |
| Pool mode | transaction |
| max_client_conn | 5000 |
| default_pool_size | 260 |
| min_pool_size | 60 |
| reserve_pool_size | 100 |
| max_db_connections | 360 |
| SHOW POOLS cl_waiting | 0 |
| SHOW LISTS free_servers | 40 |
| SHOW LISTS used_servers | 60 |

Interpretation:

1. PostgreSQL was not bottlenecked at audit time.
2. Historical direct-300 problem was latency tail and DB pressure under synthetic load: answer p95 ~15.8-18.5s, p99 ~23.6-28.2s, 5 client status-0 failures, increased active/idle-tx pressure.
3. The `answers` table is hammered by autosave/submit retries; no-op update skip reduces physical updates but direct mode still writes to PostgreSQL.
4. Indexes are adequate for current direct upsert/final submit basics.
5. Idle-in-transaction was 0 at audit, but historical pressure still requires instrumentation before Phase 6.
6. PgBouncer has no current waiting, but worker/API connection geometry can still create pressure during direct-300.

## 13. Worker/queue audit

Celery facts:

| Metric | Value |
|---|---:|
| Worker status | healthy |
| Beat status | healthy |
| Worker command | `celery -A app.tasks.scheduler worker --pool=solo --max-tasks-per-child=200` |
| Worker concurrency | 1 (`solo`) |
| Worker memory | ~79 MB / 512 MB |
| Beat memory | ~72 MB / 256 MB |
| Active tasks | empty |
| Reserved tasks | empty |
| Scheduled tasks | empty |
| Registered answer task | `app.tasks.answer_processor.process_answer_queue` |
| Processed answer queue tasks lifetime | 6,886 |
| DB0 answer queue pending/processing | absent/0 |

Queue implementation in source:

- Legacy queue keys: `answer_queue:pending`, `answer_queue:processing`, `answer_queue:processing:lock`.
- Runtime buffer keys: `runtime:answer_queue:pending`, `runtime:answer_queue:processing`, `runtime:answer_queue:flush:lock`.
- Celery beat schedules `process-answer-queue-rapid` every 5 seconds even while app flags keep production routing direct.

Readiness interpretation:

1. Existing answer queue worker exists but is legacy and not active for current direct mode.
2. Violation async worker loop exists in API processes when `VIOLATION_ASYNC_ENABLED=true`.
3. Runtime buffer flush loop exists but only starts when queue/hybrid flags enable it; currently disabled.
4. Worker plane is healthy but insufficient for production answer flush because concurrency is 1 and shared with scheduled tasks.
5. Production answer flush should use a separate queue/worker pool/concurrency and explicit pending/processing/deadletter metrics.
6. If worker dies today, direct mode answer writes continue. If queue/hybrid were enabled without safeguards, pending answers could lag and final submit would become risky.

## 14. Current phase status

| Phase area | Status | Evidence | Decision |
|---|---|---|---|
| Phase 5 direct service boundary | Mostly present | active endpoints route to `AnswerSyncService`/`FinalSubmitService` | PARTIAL, finishable |
| Phase 5 queue/hybrid flags | Present but disabled | env direct/false/0 | Keep blocked |
| Phase 6 runtime buffer source | Code exists | `answer_runtime_buffer.py` | Not production-ready |
| Phase 7/final-submit dependency | Forced flush hooks exist | `FinalSubmitService._flush_answer_buffers_before_submit` | Not proven; do not depend on Redis yet |

## 15. Phase 5 readiness assessment

| Requirement | Status | Evidence | Gap | Risk | Next patch |
|---|---|---|---|---|---|
| AnswerSyncService exists | YES | live service | none | low | keep |
| submit-answer uses it | YES | route delegates | none | low | keep |
| auto-save uses it | YES | route delegates | Redis dependency edge | medium | make Redis marker best-effort |
| auto-save-batch uses it | YES | route delegates | post-commit Redis response risk | medium | isolate Redis post-work |
| answer-journal/sync uses it | YES | route delegates | Redis idempotency dependency | medium | fallback strategy/metrics |
| session ownership validated | YES | user_id filters | none | low | keep |
| session status validated | YES | in_progress checks | late batch returns 404 not no-op | low | document/align behavior |
| valid question id checked | YES | cache/DB checks | none | low | keep |
| dedupe latest answer per question | YES | batch map and journal sequence | none | low | keep |
| no-op update skip | YES | single upsert where; batch has_changed | queue worker lacks no-op skip | medium | align queue worker |
| metadata merge | YES | helper used | none | low | keep |
| statement_answers merge | YES | helper/metadata | none | low | keep |
| idempotency journal event id | YES | Redis set TTL | Redis down behavior | medium | default-safe fallback/checker |
| runtime answered count update | YES | Redis set/session snapshot | best-effort uneven | medium | add metrics |
| Redis update best-effort | PARTIAL | single-answer yes; batch/journal gaps | response risk | medium | wrap post-commit marker failures |
| direct DB write default | YES | env direct | none | low | keep |
| queue/hybrid disabled by default | YES | env false/0 | none | low | keep |
| tests exist | PARTIAL | existing tests in repo | need more live mismatch/readiness tests | medium | add guard tests |
| final submit not regressed | YES currently | direct final submit priority | Phase 6 forced flush unproven | medium | test forced flush before enabling |
| APK old/new compatibility | YES | APK 1.0.8 smoke pass | continue monitoring | low | keep |

Phase 5 score: **17/20 for direct consolidation**, but **not complete enough to enable queue/hybrid**.

Decision:

- Phase 5 direct consolidation complete? **PARTIAL / mostly for active routes**.
- Phase 5 still has bypasses? **YES**, inactive queue/runtime buffer writer paths exist and must be aligned before activation.
- Phase 5 safe to finish in source? **YES**, with source-only/default-direct patches.
- Phase 5 safe to deploy? **PARTIAL**, only after normal preflight and operator approval; no queue/hybrid.
- Phase 5 queue/hybrid still blocked? **YES**.

## 16. Phase 6 readiness assessment

| Requirement | Status | Evidence | Gap | Risk | Needed before rollout |
|---|---|---|---|---|---|
| Redis capacity adequate | YES for shadow | 11MB used / 1.37GB max | production proof absent | medium | shadow memory telemetry |
| Redis eviction policy safe | NO | `allkeys-lru` | can evict answer keys | high | noeviction/isolated Redis/reserved memory |
| Runtime keys designed | YES | `runtime:session:*`, `runtime:answer_queue:*` | not observed live | medium | default-off shadow |
| TTL policy designed | PARTIAL | 4h TTL | cleanup after submit not proven | medium | cleanup + recovery window |
| latest-answer-per-question semantics | YES | Redis hash per question | consistency not proven | medium | checker |
| dirty question set | YES | Redis set | no deadletter | medium | deadletter/age metrics |
| answered_count runtime semantics | PARTIAL | count key and snapshot | exact scoring source still DB | medium | consistency metric |
| pending/processing/deadletter | PARTIAL | pending/processing only | no deadletter | high | add deadletter/retry age |
| worker flush implementation | PARTIAL | function exists | not dedicated/concurrency 1 | high | separate worker/queue |
| forced flush final submit | PARTIAL | hook exists | not load/chaos proven | high | tests + staging proof |
| fallback direct mode | PARTIAL | flags can return direct | operational rollback needs restart/env | medium | runbook + immediate toggle path |
| Redis failure behavior | NO/PARTIAL | direct single survives; buffer would fail | source-of-truth loss risk | high | fail-open shadow only, fail-closed prod |
| idempotency journal compatible | PARTIAL | event set | Redis idempotency dependency | medium | DB-compatible fallback/checker |
| consistency checker | NO | none found | no mismatch proof | high | add checker script |
| per-session cleanup after submit | PARTIAL | ack processing exists | runtime keys cleanup after submit unclear | medium | cleanup job |
| observability | PARTIAL | runtime/monitoring exists | no buffer pending/stale/mismatch dashboard | high | metrics endpoint |
| rollback to direct | YES conceptually | flags | needs tested runbook | medium | rollback drill |
| staged rollout controls | YES | percentage bucket | not operationally proven | medium | shadow/canary gates |
| percentage rollout | YES | deterministic bucket | not active | medium | canary test |
| tests exist | PARTIAL | existing runtime buffer tests referenced | need shadow/forced flush tests | high | add tests |
| load test plan exists | YES docs | production load-test prohibited | medium | isolated staging only |
| data loss prevention proven | NO | no shadow mismatch evidence | critical | high | 0 mismatch across stages |

Phase 6 production readiness score: **6/22**.

Phase 6 shadow/default-off readiness score: **12/22** if implemented as non-student-facing mirror only.

Decision:

- Ready for production queue/hybrid? **NO**.
- Ready for design-only/source patch default OFF? **YES/PARTIAL**.
- Ready for shadow mode default OFF after tests/metrics? **PARTIAL**.
- Ready for 1% canary? **NO**, until shadow proves 0 mismatch and Redis policy/worker observability are fixed.

## 17. Shadow-mode proposal for Phase 6

Do not activate in production yet. Proposed staged design:

### Stage 0 - audit only

Current task. No production change.

### Stage 1 - source patch, default OFF

Add:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
```

Behavior if enabled later in staging/test:

- Direct PostgreSQL write remains source of truth.
- Redis mirror write is best-effort only.
- Redis failure does not alter answer response.
- No final-submit/scoring reads from Redis.

### Stage 2 - staging/synthetic shadow

- Enable shadow only outside production or with synthetic sessions.
- Measure memory, TTL, stale keys, write latency.
- Run consistency checker against sampled sessions.

### Stage 3 - one internal real exam shadow

- Operator approval required.
- No student-facing dependency on Redis.
- 0 mismatch required.

### Stage 4 - 1-5% hybrid canary after approval

Only after:

- Redis eviction risk solved.
- Worker separate/healthy.
- Deadletter and age metrics present.
- Forced flush test passes.

### Stage 5 - 25-50%

Only after repeated 0 mismatch and final-submit success.

### Stage 6 - 100%

Only after several successful exam windows, rollback drill, and DB pressure improvement evidence.

Required admin-only health:

- pending sessions
- dirty question count
- oldest pending age
- processing age
- stale runtime sessions
- Redis memory estimate
- mismatch count
- last checker run
- worker alive
- last flush age

Required consistency checker:

- sample sessions
- compare DB latest answers vs Redis mirror by question ID and payload hash
- no raw answer content in logs
- report mismatch count only

## 18. Metrics needed before Phase 5/6

Metrics:

- answer save p50/p95/p99/max
- final submit success rate
- final submit p95/p99
- DB active max
- DB idle-in-transaction max
- PgBouncer waiting max
- Redis used memory
- Redis rejected connections
- Redis evicted keys
- runtime buffer pending sessions
- runtime buffer dirty questions
- runtime buffer stale keys
- queue oldest processing age
- deadletter count
- answer consistency mismatch count
- API 4xx/5xx/status-0 rate
- APK_TOKEN_REJECTED count
- active sessions count
- worker alive
- last flush age

Conservative current 300-user target pass criteria:

| Metric | 100 users | 300 users | 600 later |
|---|---:|---:|---:|
| Answer loss | 0 | 0 | 0 |
| Final submit success | 100% | 100% sampled/all observed | 100% sampled/all observed |
| Redis rejected/evicted | 0/0 | 0/0 | 0/0 |
| PgBouncer cl_waiting | 0 sustained | 0 sustained | 0 sustained |
| DB idle-in-tx | 0 sustained | near 0, no buildup | near 0, no buildup |
| Answer p95 | low seconds or better | must improve vs 15s historical | must improve before rollout |
| Final submit p95 | acceptable and stable | acceptable and stable | acceptable and stable |
| Runtime mismatch | 0 | 0 | 0 |
| Rollback | tested | immediate direct fallback | tested under load |

## 19. Test plan for next PRs

Audit only did not run the full test suite or load tests.

Required tests for future source patches:

```bash
python -m compileall app
pytest tests/test_runtime_policy.py -q
pytest tests/test_answer_sync_service_routing.py -q
pytest tests/test_answer_runtime_buffer.py -q
pytest tests/test_final_submit_service.py -q
pytest tests/test_exam_write_integrity_guards.py -q
pytest tests/test_production_readiness_defaults.py -q
```

If adding Phase 6 shadow:

```bash
pytest tests/test_answer_runtime_buffer_shadow.py -q
pytest tests/test_answer_runtime_buffer_consistency.py -q
pytest tests/test_final_submit_forced_flush.py -q
```

Scripts:

```bash
python -m py_compile scripts/analyze_answer_write_path.py
python -m py_compile scripts/check_answer_consistency.py  # if exists
python -m py_compile scripts/runtime_buffer_consistency_check.py  # if added
```

Docker:

```bash
docker compose -f docker-compose.production.yml config
```

JS:

```bash
node --check static/js/api.js
node --check static/js/admin/monitoring.js
```

Flutter only if APK touched:

```bash
cd flutter_client_code
flutter analyze --no-fatal-infos --no-fatal-warnings
flutter test
```

Forbidden artifact check:

```bash
git status --short | grep -E "(.apk|.aab|.jks|.keystore|key.properties|local.properties|.env|apk_builds|static/apk|flutter_client_code/build|backup|dump|.sql|.sqlite|.db|sessions.*.csv|summary.*.json)" && echo "BLOCKED: forbidden/sensitive file detected"
```

## 20. Risk register

| Risk | Severity | Evidence | Mitigation |
|---|---|---|---|
| Redis eviction loses answer buffer | Critical | `allkeys-lru` | Do not use Redis as source of truth; switch policy/instance before canary |
| Worker cannot keep up | High | Celery `solo` concurrency 1 | Separate answer flush worker/queue/concurrency |
| Final submit grades before buffer flush | Critical | forced flush unproven | Tests + staging proof + session-scoped flush only |
| Live differs from GitHub | Medium | checksum mismatch | Document/deploy only after approval |
| Redis marker failures affect non-P0 responses | Medium | batch/journal gaps | Make marker post-work best-effort |
| Historical direct-300 tail latency | High | p95/p99 docs | Timing instrumentation + DB pressure metrics |
| Journal idempotency Redis dependency | Medium | Redis read before apply | fallback/checker strategy |
| Queue worker semantics differ from service | Medium | legacy worker direct upsert no no-op skip | align before queue mode |

## 21. Rollout plan

Conservative plan:

1. Keep production direct safe-mode.
2. Finish Phase 5 direct consolidation source-only patches (no queue/hybrid).
3. Deploy only after preflight + operator approval.
4. Add timing/metrics and validate real low-traffic behavior.
5. Add Phase 6 shadow default-off code + tests.
6. Run staging/synthetic shadow.
7. Run one controlled internal shadow with direct DB source of truth.
8. Only after 0 mismatch, consider canary proposal.

## 22. Rollback plan

Current rollback is simple because direct mode is active:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
```

For future shadow/canary:

- Keep direct DB write as fallback/source of truth.
- Disable shadow/canary flag first.
- Drain/ignore Redis runtime keys only after recovery window.
- Do not delete keys during active exam.
- Confirm final-submit success and answer consistency.

## 23. Exact next PR recommendation

Commit 1 (docs already in this task):

```text
docs: record VPS architecture readiness for phase 5 and 6
```

Next code PR should be small/default-safe, not activation:

1. Add tests/guards proving production defaults keep queue/hybrid off.
2. Add source-only metrics for answer hot path if not already deployed.
3. Make batch/journal Redis post-work failures best-effort where safe.
4. Add default-off shadow metrics/checker design, not runtime source-of-truth.

Do **not** implement in next PR:

- production queue/hybrid activation
- Redis runtime buffer as source of truth
- final-submit Redis dependency beyond no-op guarded branch
- DB schema migration
- worker rewrite
- large `app/api/exams.py` split

## 24. Forbidden artifact check result

Report commit includes docs only. No APK/AAB, keystore, `.env`, key properties, DB dump, sqlite, CSV/session export, summary JSON, raw token/session token, or PII is included.

## 25. Production actions performed

| Action | Performed? |
|---|---:|
| Deploy | No |
| Restart | No |
| Migration | No |
| Load-test | No |
| Build APK | No |
| Edit `.env` | No |
| Enable queue/hybrid/runtime-buffer | No |
| Read-only health/source/env/DB/Redis/worker inspection | Yes |

Temporary audit commands/scripts were executed read-only and did not modify application state.

## 26. Final decision

| Question | Decision |
|---|---|
| Safe to finish Phase 5 direct consolidation? | **YES/PARTIAL** - source-only hardening is reasonable. |
| Safe to deploy Phase 5 source-only? | **PARTIAL** - only after preflight/operator approval; no queue/hybrid. |
| Safe to start Phase 6 shadow default-off? | **PARTIAL** - design/source patch only, default OFF, with tests/checker/metrics. |
| Safe to enable queue/hybrid production now? | **NO**. |
| Safe to make Redis source of truth now? | **NO**. |
| Safe to keep current direct safe-mode? | **YES**, with monitoring. |
