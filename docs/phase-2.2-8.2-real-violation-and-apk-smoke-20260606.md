# Phase 2.2/8.2 Real Violation and APK Smoke Validation — 2026-06-06

## Scope
Validation-only follow-up after the live rollout of inter-session refresh safeguards, violation pipeline health, and APK admin settings access.

No production load test was run. No answer save/final-submit logic was changed. Phase 5/6 queue/runtime-buffer remains disabled.

## GitHub Review
- Branch: `review/sanitized-root-20260531-115153`.
- Base reviewed: `abd99b9c374b78c21c3c53e23d06d05c17edbca1`.
- Head at start of validation: `abd99b9c374b78c21c3c53e23d06d05c17edbca1`.
- New commits since base at start: none.
- Forbidden artifact diff since base: none.

## VPS Precheck
- VPS path: `/root/ujian_online`.
- VPS is not a git checkout.
- Public `/health`: `200`.
- Postgres: accepting connections.
- Redis: `PONG`.
- Docker containers: API/admin/API data plane healthy.
- Redis rejected connections: `0`.
- Redis evicted keys: `0`.
- OOM logs last 24h: none observed.
- Disk `/`: about `52%` used.

### Exam/session safety before validation
- Active published exam windows: `0`.
- Active/in-progress/paused sessions: `0`.
- Active sessions after exam end: `0`.
- Recent final-submit logs in last 10 minutes: `0`.
- Long active DB queries >60s: `0`.
- Long idle-in-transaction DB sessions >60s: `0`.
- Next published exam start: `2026-06-08 07:30:00+07`.

### Safe-mode env status
Confirmed:
- `ANSWER_WRITE_MODE=direct`.
- `ANSWER_QUEUE_ENABLED=false`.
- `ANSWER_QUEUE_PERCENTAGE=0`.
- `EXAM_PEAK_MODE=true`.
- `VIOLATION_ASYNC_ENABLED=true`.
- `ADMIN_MONITORING_DETAIL_LEVEL=summary`.
- `MOBILE_APK_PRIMARY=true`.
- `SEB_DESKTOP_LEGACY_ENABLED=false`.
- `SEB_QR_ENABLED=false`.
- `SEB_DEBUG_ENDPOINTS_ENABLED=false`.
- `APK_BUILD_ENDPOINT_ENABLED=false`.
- `TELEGRAM_ALERTING_ENABLED=false`.
- `HEAVY_EXPORT_ENABLED=false` in env.
- `ANSWER_HOT_PATH_TIMING_ENABLED` unset/off.

## Inter-Session Refresh Validation
Dry-run was executed through the live backend path using the deployed `restart-safe` logic.

Result:
- `success=true`.
- `dry_run=true`.
- `active_sessions_count=0`.
- `running_exams_count=0`.
- `upcoming_exams_count=0` at validation time.
- `imminent_exams_count=0`.
- `minimum_gap_minutes=5`.
- `buffer_minutes=30`.
- `include_data_services=false`.
- DB/Redis/PgBouncer are excluded by default.
- Restart plan includes app plane services: `api`, `api2`–`api8`, `api_admin`, `api_admin2`, `celery_worker`, `celery_beat`, `nginx`.

Because the next exam was not within 30 minutes during validation, the live response had no buffer warning. Code markers and deployed source confirm the 30-minute operator buffer is warning-only and the 5-minute minimum gap is the hard block.

Actual inter-session restart was **not** executed in this validation turn.

## Violation Pipeline Health Before Synthetic Event
Initial live pipeline health:
- `enabled=true`.
- `mode=async`.
- `worker_alive=true`.
- `redis_pending=0`.
- `redis_deadletter=0`.
- `db_events_last_15m=0`.
- `db_events_last_24h=0`.
- `security_events_last_24h=83`.
- `apk_token_rejected_last_24h=83`.
- `sessions_with_violation_count_last_24h=0`.
- `suspicious_sessions_last_24h=0`.

Interpretation before synthetic event: pipeline is healthy/observable, but the current real production data still shows APK token/signature rejects rather than cheating violation events.

## Real Violation Event Synthetic E2E Probe
No existing non-PII test user/session was available:
- `test_users=0`.
- `recent_test_sessions=0`.

A temporary synthetic user/session was created against a non-deleted test exam and cleaned up immediately after validation. No real student PII was used.

### First probe note
The first synthetic attempt used a deleted test exam (`is_deleted=true`), which correctly did not appear in the dashboard aggregate because dashboard filters deleted exams. This identified that dashboard exclusion was expected for deleted exams, not a pipeline failure.

### Successful synthetic event probe
Second probe used non-deleted test exam `528`.

Event tested:
- `tab_switch`.
- Source: synthetic probe.
- Duration: 7 seconds.

Results:
- `/api/exams/log-violation` route function returned `status=queued`.
- Response time: about `22 ms`.
- Response `violation_count=1`.
- Redis pending after enqueue: `1`.
- Drain result: `1` event processed.
- DB after drain:
  - `exam_log_count=1`.
  - `last_event_type=violation_tab_switch`.
  - `session_violation_count=1`.
  - `session_status=in_progress`.
- Dashboard aggregate source after drain:
  - `total_violations: 0 -> 1`.
  - `type_breakdown_count: 0 -> 1`.
  - `top_offenders_count: 0 -> 1`.
  - `timeline_count: 0 -> 1`.
- Pipeline health after drain:
  - `db_events_last_15m=1`.
  - `db_events_last_24h=1`.
  - `redis_pending=0`.
  - `redis_deadletter=0`.
  - `sessions_with_violation_count_last_24h=1`.
  - warnings cleared during the synthetic event window.

Cleanup:
- Synthetic user leftovers: `0`.
- Synthetic sessions leftovers: `0`.
- Synthetic logs leftovers: `0`.
- Final pipeline health returned to no real violation events after cleanup.

Conclusion: endpoint -> Redis queue -> async drain -> DB `exam_logs` -> session aggregate -> dashboard aggregate source is functional. Real field absence is likely client/APK token rollout or client event emission, not backend pipeline.

## APK Admin Settings and Registration Status
Live UI/source markers:
- Advanced APK settings button live: `show-advanced-apk-settings=true`.
- APK token section live: `apk-token-section=true`.
- Ctrl+Shift+Meta/Windows shortcut support live: `e.metaKey=true`.

Read-only settings status:
- Settings row exists: yes.
- `allow_mobile_apps=true`.
- `token_validation_bypass=false`.
- Stable profile enabled: true.
- Accepted token count: `1`.
- Accepted signature count: `1`.
- New update token is set.
- New update signature count: `1`.
- Expected APK signature hash is registered: yes.
- Expected local APK build token is registered: **no**.
- Masked local token reference: `BUILD-2026...RO9U60`.

Important: full build token is intentionally not stored in this report.

## APK Smoke Status
Full device APK smoke was **not completed** in this validation turn because the local APK build token is not registered in the VPS admin settings. Existing `APK_TOKEN_REJECTED` counts also support that token/signature registration is still a rollout blocker.

APK distribution decision remains blocked until:
1. The local build token is registered in the correct stable/new-update profile.
2. Signature hash remains registered.
3. `token_validation_bypass` remains off.
4. A controlled physical device smoke passes login/start/autosave/violation/final-submit.

## Production Actions Performed
- No deploy performed in this turn.
- No restart performed in this turn.
- No DB migration performed.
- No production load test performed.
- Temporary synthetic validation rows were created and removed.
- No APK/AAB/keystore/env/backup artifact was committed.

## Tests / Checks
Validation checks performed:
- GitHub branch comparison from `abd99b9` to head: no new commits at start.
- VPS health and safe-mode checks.
- Restart-safe dry-run.
- Violation pipeline health before/after synthetic event.
- Synthetic event enqueue/drain/DB/dashboard aggregate validation.
- APK settings registration check with masked token output.
- Synthetic leftovers check.

No source code changed, so no compile/pytest/node validation was required in this turn.

## Remaining Blockers
1. Real client/APK violation event still needs device/browser smoke after token registration.
2. Local APK build token is not registered on VPS settings.
3. APK broad distribution remains blocked.
4. Manual browser verification of Admin Settings save flow remains pending.
5. Phase 4.3.2H answer timing instrumentation remains not live.
6. Phase 5/6 queue/runtime-buffer remains off and must not start.

## Next Recommended Action
1. Register the local APK build token in the new-update APK profile without enabling bypass.
2. Run one controlled physical APK smoke:
   - login test student,
   - start test exam,
   - autosave answer,
   - trigger safe violation event,
   - final submit,
   - confirm dashboard visibility.
3. If APK smoke passes, distribute to a small controlled batch first.
4. Use inter-session refresh operationally between sessions if RAM is high, but keep DB/Redis/PgBouncer excluded by default.

## Final Decision
- VPS safe for next exam: **YES**.
- Inter-session refresh usable: **YES**.
- Violation dashboard usable: **YES for backend/dashboard pipeline; PARTIAL for real field clients until APK/token smoke passes**.
- New APK safe to distribute: **NO/PARTIAL** because build token is not registered and physical smoke is pending.
- Phase 5/6 may start: **NO**.
