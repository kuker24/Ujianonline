# VPS Phase Status and Inter-Session Memory Findings — 2026-06-06

## Scope
Read-only VPS audit, phase mapping, violation telemetry investigation, memory diagnosis, and inter-session refresh fix planning/implementation in source.

No production restart, deployment, migration, or load test was performed during this audit.

## GitHub Review
- Branch reviewed: `review/sanitized-root-20260531-115153`.
- Initial latest GitHub head reviewed: `a89257c2b5fa9ca497e652c3b463733614e28a92` (`docs: record APK build success`).
- New commits after `a89257c` at the start of this audit: none.
- Forbidden artifact diff check from `a89257c` to branch head: no APK/AAB/keystore/env/db dump/session artifact found.
- Source fix prepared after audit: `f97e68f2e08e5f1d60f32ed818351138e9b642f6` (`fix: allow safe inter-session service refresh`).

## VPS Deployed Source Status
- VPS host: `adminujian`.
- VPS app directory: `/root/ujian_online`.
- VPS app directory is **not a git checkout** (`GIT_WORKTREE=no`).
- VPS deployed commit cannot be resolved via `git rev-parse`.
- VPS is effectively behind GitHub source for multiple recent source/docs commits.

### Runtime Marker Evidence on VPS
| Marker | VPS status | Interpretation |
|---|---:|---|
| `changed_answer_payload` in `app/services/answer_sync_service.py` | true | Phase 4.3.2G no-op answer update guard is live. |
| peak-mode progress skip marker | true | Peak-mode progress broadcast/fallback skip is live. |
| `SUBMIT-ANSWER-TIMING` | false | Phase 4.3.2H timing instrumentation is not live. |
| `e.metaKey` / advanced APK shortcut JS | false | Admin APK shortcut fix is not live on VPS. |
| `show-advanced-apk-settings` button in settings template | false | Admin visible APK settings button is not live on VPS. |
| `apk-token-section` | true | Legacy token section exists. |
| Flutter `initialize({ ... })` compatibility | false | New APK source compile fix is source/local only, not VPS. |
| Flutter clipboard/security compatibility methods | mostly true | Some methods exist, but latest full contract is not live. |
| APK build success doc | missing | Docs commit is GitHub only, not VPS. |
| Violation async router/service | true | Async violation code exists on VPS. |
| Monitoring aggregate/dashboard code | true | Aggregate dashboard code exists on VPS. |

## Runtime Environment Safe-Mode Status
Observed values from VPS `.env`/compose defaults:

| Variable | Status |
|---|---|
| `ANSWER_WRITE_MODE=direct` | OK |
| `ANSWER_QUEUE_ENABLED=false` | OK |
| `ANSWER_QUEUE_PERCENTAGE=0` | OK |
| `EXAM_PEAK_MODE=true` | OK |
| `VIOLATION_ASYNC_ENABLED=true` | OK |
| `ADMIN_MONITORING_DETAIL_LEVEL=summary` | OK |
| `MOBILE_APK_PRIMARY=true` | OK |
| `SEB_DESKTOP_LEGACY_ENABLED=false` | OK |
| `SEB_QR_ENABLED=false` | OK |
| `SEB_DEBUG_ENDPOINTS_ENABLED=false` | OK |
| `APK_BUILD_ENDPOINT_ENABLED=false` | OK |
| `TELEGRAM_ALERTING_ENABLED=false` | OK |
| `HEAVY_EXPORT_ENABLED=false` | OK in env; compose fallback still has default true if env removed |
| `ANSWER_HOT_PATH_TIMING_ENABLED` | unset/off |

Phase 5/queue/runtime-buffer is **not active**.

## Docker and Health Status
- API replicas: `api`, `api2`–`api8` all healthy.
- Admin API replicas: `api_admin`, `api_admin2` healthy.
- Celery worker/beat healthy.
- Nginx container healthy.
- Postgres healthy.
- PgBouncer healthy.
- Redis healthy.
- Prometheus/Grafana healthy.
- Container uptimes during audit: app/data services up about 11 hours; Prometheus/Grafana up about 2 days.
- Public `/health` via Nginx: `200`.
- Public HTTPS `/health`: `200`.
- Direct host ports `127.0.0.1:8000/8001` are not published; connection refused is expected for direct host curls.
- Host `nginx -t` command is not available because Nginx runs in container.

## DB Safety Checks
Read-only DB findings:

| Check | Result |
|---|---:|
| Active published exam windows now | 0 |
| Next published exam start | `2026-06-08 07:30:00+07` |
| In-progress sessions | 0 |
| Active sessions after exam end | 0 |
| Terminal sessions without score | 0 |
| Submitted/completed/finished sessions last 24h | 567 |
| Synthetic/load-test users | 0 |
| Synthetic/load-test sessions | 0 |
| Postgres connections total | 66 |
| Long active queries >60s | 0 |
| Long idle-in-transaction >60s | 0 |

## Redis Status
- `PING`: `PONG`.
- Used memory: `13.15M`.
- Peak memory: `16.68M`.
- Maxmemory: `1.37G`.
- Fragmentation ratio: `1.60`.
- Rejected connections: `0`.
- Evicted keys: `0`.
- DB size: `1376` keys.
- Pattern counts: `*violation* = 0`, `*answer* = 1340`, `*session* = 1340`, `runtime:* = 5`.
- TTL sample: answer/session/runtime samples all had positive TTL; no sampled key without expiry.
- No Redis cleanup was performed.

## Memory Diagnosis
Current host status during audit:

| Metric | Value |
|---|---:|
| RAM total | 15 GiB |
| RAM used | 3.6 GiB |
| RAM free | 8.6 GiB |
| Buff/cache | 3.5 GiB |
| Available | 11 GiB |
| Swap total | 2.0 GiB |
| Swap used | 4 MiB |
| Disk `/` | 52% used |
| OOM killer logs last 24h | none found |

Top current memory owners:
- API/admin Python workers collectively own most app RSS.
- `api_admin-1` was the largest current app container at about `433.7 MiB / 768 MiB`.
- Student API replicas were about `234–252 MiB` each.
- Postgres was about `407 MiB / 5.5 GiB`.
- Redis was about `16 MiB / 1.75 GiB`.
- Celery worker/beat were about `80 MiB` / `74 MiB`.
- Nginx was about `122 MiB`.

Current memory is **not under pressure**. The field report that RAM stays high between close sessions is most consistent with app-plane worker RSS/page-cache behavior after exam traffic, not Redis key accumulation and not Postgres runaway at the time of audit. Linux page cache is also reclaimable and should not be confused with unreclaimable memory pressure.

Likely current memory owner classification:
- API/admin worker memory growth: plausible primary during/after exam traffic; current state moderate.
- Celery worker memory growth: not evident in current snapshot.
- Redis key accumulation: not evident; memory tiny and TTLs sane.
- Postgres connection/session memory: not evident; connections idle, no long active/idle-tx queries.
- Linux page cache: contributes to displayed used memory but is reclaimable.
- Unknown residual: needs before/after exam snapshots to prove leak vs normal high-water behavior.

## Cheating / Violation Telemetry Findings
### Pipeline status
- Client code exists for `/api/exams/log-violation` in web exam JS and Flutter APK source.
- Endpoint exists on VPS via `app/api/violation_events.py`.
- Auth path uses hot-path authenticated user dependency.
- `VIOLATION_ASYNC_ENABLED=true` on VPS.
- Async service queues to Redis key `runtime:violation:pending` and writes DB `exam_logs` in drain loop.
- Dashboard aggregate code exists.

### Live data status
- `security_events` last 24h: `83`, all `APK_TOKEN_REJECTED`, severity `high`.
- `security_events` last event at: `2026-06-05 03:52:47+07`.
- `exam_logs` last 24h event types: `SCORE_BREAKDOWN=568`, `SESSION_START=567`, `EXAM_SUBMITTED=539`, `EXAM_AUTO_SUBMITTED_TIMEOUT=29`.
- `exam_logs` violation-like count query matched `539`, likely due submit payload text, not actual logged violation event types.
- Sessions with `violation_count > 0` in last 24h: `0`.
- Sessions `is_suspicious=true` in last 24h: `0`.
- Redis `*violation*` keys: `0` at audit time.

### Log status
- API logs show async violation drain loop errors around restart/DNS transient windows:
  - Redis `Connection has data`.
  - Temporary DNS failure resolving Redis.
- No durable pending violation backlog was present during audit.

### Interpretation
Violation telemetry is **not end-to-end proven live** for real cheating events. The dashboard likely has nothing meaningful to show because no counted violation events reached/persisted as `violation_*` exam logs or session `violation_count`, while security middleware is recording APK token rejects separately as `security_events`.

Most likely failure modes to investigate next:
1. Old APK/web client did not emit real violation events in the exam flow.
2. Events are best-effort dropped on Redis/auth/session validation failure.
3. Async drain loop can miss events during Redis/DNS instability, although no backlog remained.
4. Dashboard summary mode shows aggregate only and does not surface `security_events` such as `APK_TOKEN_REJECTED` as cheating feed.
5. APK clients may be rejected by token/signature before exam telemetry can work if admin token/signature is not registered.

Recommended next patch: Phase 2.1 + 8.1 Violation Telemetry Recovery and Dashboard Visibility:
- Add sanitized `GET /api/monitoring/violation-pipeline-health`.
- Include Redis pending/deadletter lengths, DB events last 15m/24h, last event timestamp, worker alive signal.
- Surface aggregate count, last type, last time, severity in summary dashboard.
- Keep violation path best-effort and never block answer/final submit.

## Inter-Session Restart / Refresh Findings
### Current VPS behavior
- Existing endpoint: `POST /api/monitoring/system/restart-safe`.
- Existing frontend button: Monitoring page `restartSystemSafelyFromOps()`.
- Existing auto restart scheduler exists.
- Host restart worker exists and is active via `ujian-host-full-restart.path`.
- Host full restart status file indicates the previous full restart succeeded.
- Full restart backend is configured via signal files under `/app/runtime_control`.

### Root cause of 30-minute failure
The backend hard-blocked restart when any published exam starts within `restart_buffer_minutes`.
The UI and auto scheduler default buffer is 30 minutes. Therefore, even with `active_sessions_count=0`, a next exam within about 30 minutes causes `RESTART_GUARD_BLOCKED`.

### Safety issue found
The current frontend/manual request used `include_data_services=true` when full restart backend is available. That means the plan can include `pgbouncer`, `redis`, and `db`. For normal inter-session memory cleanup, this is unnecessarily broad and riskier than recycling app services only.

### Source fix prepared
Commit `f97e68f2e08e5f1d60f32ed818351138e9b642f6` changes source behavior:
- Backend still blocks if active sessions exist.
- Backend still blocks if an exam is currently running.
- Backend blocks if next exam is within the minimum safe gap (`5` minutes).
- Exams within the operator buffer (for example 30 minutes) now produce warnings instead of hard-blocks.
- Dry-run response includes checks, warnings, minimum gap, and next exam start.
- Manual restart default no longer includes data services (`include_data_services=false`).
- Frontend button now runs dry-run preflight first and shows exact preflight details before confirmation.
- Frontend confirmation shows whether DB/Redis/PgBouncer are included; default is `TIDAK`.

This source fix was **not deployed to VPS** during audit.

## Phase Status Table
| Phase | Target | GitHub/source status | VPS live status | Evidence | Risk | Next action |
|---|---|---|---|---|---|---|
| 0 | Audit/classification | Partial docs/audits exist | Partial | Multiple docs; VPS not git checkout | Source/live drift | Keep deployment manifest/checksum. |
| 1 | Feature flags/mobile-first safe-mode | Applied | Mostly applied | Safe env flags direct/off/mobile primary | Env drift if `.env` removed (`HEAVY_EXPORT` compose fallback true) | Keep env pinned and document. |
| 2 | Violation async efficient path | Source exists | Partial/incomplete | Router/service live, async flag true, but no real violation counts | Cheating info not visible | Phase 2.1 pipeline health + counters. |
| 3 | APK runtime policy | Source/local APK ready | Not validated live rollout | APK source/build success local; VPS admin token fix not live | Old clients/token rejects | Register token/signature; limited rollout. |
| 4 | APK/web backoff+jitter | Partial source | Not fully validated | Client resilience source exists; APK not deployed | Unknown field behavior | Validate with new APK. |
| 5 | AnswerSyncService direct path | Direct no-op patch in source | Partially applied | `changed_answer_payload=true`, peak skip true; timing marker false | Direct-300 remains NO-GO historically | Do not change answer path now; later 4.3.2H. |
| 6 | Redis runtime buffer | Source exists | Not active | `ANSWER_QUEUE_ENABLED=false`, percentage 0 | Phase 6 unsafe for exam | Keep disabled. |
| 7 | Final submit priority | Source guarded | Not newly changed | No active final-submit issue in audit | Must not regress | Leave stable path untouched. |
| 8 | Admin cheating dashboard aggregate-first | Source exists | Partial/incomplete | Summary dashboard code live; data missing/not surfaced | Operator sees no cheating info | Phase 8.1 dashboard visibility. |
| 9 | APK release/debug cleanup | Source/local build success | Not VPS/distribution confirmed | APK built locally, doc not on VPS | Token/signature rollout pending | Register admin settings before distribution. |
| 10 | SEB PC/Desktop legacy/off | Source/env | Mostly applied by flags | SEB desktop/QR/debug flags false | Legacy users unsupported intentionally | Keep off unless approved. |
| 11 | Admin UI simplification | Source partial | Partial | Existing monitoring UI; new APK button not live | Operator workflow gaps | Deploy selected UI fixes after exam-safe window. |
| 12 | Split `app/api/exams.py` | Source partial | Partial | Violation router split live; exams still large | Maintainability | Continue only after operational fixes. |

## APK Status
- Local APK build success: yes.
- APK artifact committed: no.
- APK deployed/distributed: unknown/no evidence from VPS audit.
- Build token registered in admin: unknown/not verified.
- Signature registered in admin: unknown/not verified.
- Signature hash to register remains: `297ad1bfc6ed358684ad699569daf4a6565847790211ce726bf53da580ef3187`.
- Safe to distribute new APK: not yet, until admin token/signature registration and limited smoke rollout are confirmed.

## Cleanup / Restart / Production Actions
- Cleanup performed: none.
- Restart performed: no.
- Deploy performed: no.
- Migration performed: no.
- Production load test performed: no.
- Redis keys deleted: no.
- DB writes performed: no.

## Risks
1. VPS is not a git checkout, making exact commit provenance unavailable.
2. VPS is behind GitHub/source for APK admin UI, APK source fixes, Android toolchain docs, and restart fix.
3. Violation telemetry has code but no verified real cheating events persisted to dashboard aggregates.
4. Existing live restart flow can include data services and is blocked by 30-minute buffer until source fix is deployed.
5. API/admin worker RSS can grow during heavy exam traffic; before/after snapshots are needed to quantify leak vs normal high-water behavior.

## Rollback
For source patch `f97e68f` if needed:

```bash
git revert f97e68f2e08e5f1d60f32ed818351138e9b642f6
```

No VPS rollback was needed because no deploy/restart was performed.

## Next Recommended Actions
1. Deploy only the inter-session refresh fix in an approved exam-safe window, then test dry-run first.
2. Add Phase 2.1 + 8.1 violation pipeline health endpoint and dashboard aggregate visibility.
3. Register APK build token/signature in admin settings, then run limited APK rollout/smoke.
4. During next exam day, capture memory snapshots before session, immediately after session, and before next session to identify API/admin RSS growth vs reclaimable cache.
5. Do not enable Phase 5/6 queue/runtime-buffer.

## Final Decision
| Decision | Status |
|---|---|
| VPS ready for next exam in current direct safe-mode | Yes, based on current health and no active sessions, but cheating telemetry remains incomplete. |
| Safe to distribute new APK | Not yet; requires admin token/signature registration and limited smoke rollout. |
| Safe to enable Phase 5/6 | No. Keep queue/runtime-buffer disabled. |
| Safe to use restart antar sesi now on VPS | Existing live flow is available but can be blocked by 30-minute gap and can include data services; prefer deploy source fix first or use manual app-plane-only command with explicit approval. |
