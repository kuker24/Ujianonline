# Phase 2.1/8.1 Violation Telemetry and Inter-Session Refresh Rollout — 2026-06-06

## Summary
This work safely deployed the inter-session refresh safeguards, violation pipeline health visibility, and APK admin settings access helpers to the live VPS without changing answer save/final-submit logic and without enabling Phase 5/6 queue/runtime-buffer.

## GitHub Status
- Branch: `review/sanitized-root-20260531-115153`.
- Latest head reviewed before work: `209a29b7bfb1d2461ed07e3033c708dd4c17816a`.
- New commits at start of work after `209a29b`: none.
- Source commit prepared and deployed: `b72a1f3863cd68655926407232ca24cbe991c06e` (`fix: surface violation health and inter-session refresh safeguards`).

## VPS Preflight
- VPS path: `/root/ujian_online`.
- VPS is still not a git checkout.
- Active published exam windows before deployment: `0`.
- Active/in-progress/paused sessions before deployment: `0`.
- Recent final-submit logs in last 10 minutes: `0`.
- Long active DB queries >60s: `0`.
- Long idle-in-transaction DB sessions >60s: `0`.
- Public health before deployment: `200`.
- Postgres: accepting connections.
- Redis: `PONG`.
- Redis rejected connections: `0`.
- Redis evicted keys: `0`.
- Disk `/`: about `52%` used.

## Safe-Mode Environment
Confirmed on VPS:
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

Phase 5/6 queue/runtime-buffer remains disabled.

## Files Deployed to VPS
Primary patch files:
- `app/api/monitoring.py`
- `app/api/monitoring_schemas.py`
- `static/js/admin/monitoring.js`
- `static/js/api.js`
- `static/js/api/modules/20-endpoints-grading-monitoring-templates.js`
- `templates/admin/monitoring.html`

APK admin settings access files:
- `templates/admin/settings.html`
- `static/js/api/modules/30-ui-shortcuts.js`

No APK/AAB/keystore/env/db dump/session artifacts were deployed or committed.

## File Backups and Checksums
Backup directories on VPS:
- `/root/ujian_online/deploy-backups/20260606_0111_74de0f8`
- `/root/ujian_online/deploy-backups/20260606_0121_34de3bc_hotfix`
- `/root/ujian_online/deploy-backups/20260606_0128_b72a1f3_hotfix_v2`
- `/root/ujian_online/deploy-backups/20260606_0138_apk_admin_ui`

Selected checksum changes:

| File | Before SHA256 | After SHA256 |
|---|---|---|
| `app/api/monitoring.py` | `ca1c152b7e320da71536f5f835e56133280e46704cafda1c4a8fc992a95c2182` | `3028d06197fe32e2eff53038d574d04352223c864059f2a122c5c9389f72bf30` |
| `app/api/monitoring_schemas.py` | `86d739669833e549cf95c307fee8b901302ef64d6c29110b9264fd2839bd4fe7` | `d36008f1e7198cd26961fb6efa9429c6b7d216f25f6674decbcc222419af2b1e` |
| `static/js/admin/monitoring.js` | `c40bffc1109cf95b21c52caf041f6f2617f915e35a32ea1574d6a0ccd0d0b459` | `a6748d3b80459f411324b92367fa7338352a95cda25fe5caa0b4d4e8fb383706` |
| `static/js/api.js` | `496159f50f46f86ffa407445c20427faea1972e62f176c323a4c8e2e2edffb74` | `7b19134da0d759a646057e0fc71ff5a44a7a2f2a8ffdf15b68d5bb40fee187eb` |
| `static/js/api/modules/20-endpoints-grading-monitoring-templates.js` | `664f60815c6f3d0b6156113c2f1107eef41cd18d53071f0a052ac909cc880f0c` | `b70813b8dd4ba93a84fd4158d6ebca444676d47c9f9dc2be88b9098dfc51eb22` |
| `templates/admin/monitoring.html` | `2ad1f72dce70b409da244626e9f5af4c60f97d7ccf7780c2944053a3c0472b89` | `e115c8d2eaa98235c73e3760fbd7cc92c6c6d2a7000140477b532f1832babbfd` |
| `templates/admin/settings.html` | `9f27511309e74cd98c851da8334e6f73f4aacffd280366b092b0f9a0e9cdd07b` | `5fa8316d82bf9276f3e01b701d821bfd5042efa34d5f57da6e365ebfdacf8462` |
| `static/js/api/modules/30-ui-shortcuts.js` | `1c489d2df81195cb1ec6749cf80d3d3e08b5d756c81b6da7676352d3214b4d29` | `9f3e06cd46f5190a11cc715867d4af3962303b3479f72d6494f9a763568bc02d` |

## Inter-Session Refresh Result
### Backend behavior now live
- Endpoint: `POST /api/monitoring/system/restart-safe`.
- Dry-run/preflight is supported.
- Active sessions >0: hard block.
- Current running exam window: hard block.
- Next exam within minimum safe gap (`5` minutes): hard block.
- Next exam within operator buffer (`30` minutes default): warning only, not hard block.
- `include_data_services=false` by default.
- Restart plan in dry-run excludes DB/Redis/PgBouncer by default.

### Frontend behavior now live
- Monitoring button uses clear label: `Refresh Server Antar Sesi`.
- Frontend runs dry-run first.
- Confirmation displays active sessions, running exams, next exam, warnings, and whether DB/Redis/PgBouncer are included.
- Default confirmation says data services are not included.

### Live dry-run result
Internal dry-run result after deployment:
- `success=true`.
- `mode=full`.
- `active_sessions_count=0`.
- `running_exams_count=0`.
- `upcoming_exams_count=0` at current audit time.
- `imminent_exams_count=0`.
- `minimum_gap_minutes=5`.
- `include_data_services=false`.
- Restart plan: `api`, `api2`–`api8`, `api_admin`, `api_admin2`, `celery_worker`, `celery_beat`, `nginx`.
- DB/Redis/PgBouncer excluded.

## Violation Pipeline Health Result
New admin-only endpoint is live:

```text
GET /api/monitoring/violation-pipeline-health
```

Unauthenticated request returns `401`, confirming admin protection.

Internal sanitized health result after deployment:
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
- Warning: APK token/signature rejects exist, but no real `violation_*` exam events are recorded.

Interpretation:
- The violation pipeline is observable now.
- Current data still shows APK token/signature issue, not actual cheating violation telemetry.
- Dashboard now has a summary area for pipeline health, but real cheating visibility remains partial until clients emit/flush real violation events and admin token/signature registration is fixed.

## APK Admin Settings Access
Now live on VPS:
- Advanced APK settings button marker: `show-advanced-apk-settings=true`.
- APK token section exists: `apk-token-section=true`.
- Meta/Windows shortcut support marker: `e.metaKey=true`.

No APK was distributed and no build token/secret was committed.

## Restart / Deployment Actions Performed
Deployment action: yes, file-level deployment to non-git VPS.

Restart action: yes, rolling app-plane service restart only.

Services restarted:
- `api`, `api2`, `api3`, `api4`, `api5`, `api6`, `api7`, `api8`
- `api_admin`, `api_admin2`

Services intentionally not restarted:
- `db`
- `redis`
- `pgbouncer`
- `celery_worker`
- `celery_beat`
- `nginx`

Note: dry-run restart plan can include celery/nginx for future inter-session refresh, but this deployment restart only recycled API/admin API services required to load Python code.

## Health After Deployment
- Public `/health`: `200`.
- Postgres: accepting connections.
- Redis: `PONG`.
- Redis rejected connections: `0`.
- Redis evicted keys: `0`.
- All API/admin containers healthy after rolling restart.
- DB/Redis/PgBouncer remained healthy and were not restarted.

## Memory Before / After
Before deployment:
- Host RAM used: about `3.6 GiB`.
- Host available: about `11 GiB`.
- `api_admin-1`: about `423.8 MiB`.
- API replicas: about `234–253 MiB`.

After deployment/restart:
- Host RAM used: about `3.2 GiB`.
- Host available: about `11 GiB`.
- `api_admin-1` / `api_admin2-1`: about `101.6 MiB` each.
- API replicas: about `227–238 MiB`.

This supports the prior diagnosis that app-plane worker recycling is useful between sessions when RAM appears high after traffic.

## Tests Run
Source-side validation:

```bash
git diff --check
python -m compileall app
pytest tests/test_violation_pipeline_health.py tests/test_restart_safe_guards.py tests/test_production_readiness_defaults.py -q
node --check static/js/admin/monitoring.js
node --check static/js/api.js
```

Result:
- Python compile passed.
- Targeted pytest passed: `17 passed`.
- Node syntax checks passed.
- Forbidden artifact check passed.

VPS-side validation:
- `python3 -m py_compile app/api/monitoring.py app/api/monitoring_schemas.py` passed.
- `node --check` was skipped on VPS where Node is not installed.
- Public health stayed `200` after each rolling service restart.
- Internal endpoint validation passed after timezone/model fallback hotfixes.

## Forbidden Artifact Check
No forbidden/sensitive artifact was committed or deployed:
- no APK/AAB,
- no keystore,
- no `key.properties`,
- no `local.properties`,
- no `.env`,
- no DB dump/backup/sqlite,
- no CSV/session/summary JSON artifacts,
- no raw token/session/PII.

## Rollback Instructions
Restore the relevant backup directory, then restart app-plane API/admin services.

Example for the full primary patch rollback:

```bash
cd /root/ujian_online
BACKUP=/root/ujian_online/deploy-backups/20260606_0111_74de0f8
cp -a "$BACKUP/app/api/monitoring.py" app/api/monitoring.py
cp -a "$BACKUP/app/api/monitoring_schemas.py" app/api/monitoring_schemas.py
cp -a "$BACKUP/static/js/admin/monitoring.js" static/js/admin/monitoring.js
cp -a "$BACKUP/static/js/api.js" static/js/api.js
cp -a "$BACKUP/static/js/api/modules/20-endpoints-grading-monitoring-templates.js" static/js/api/modules/20-endpoints-grading-monitoring-templates.js
cp -a "$BACKUP/templates/admin/monitoring.html" templates/admin/monitoring.html

docker compose -f docker-compose.production.yml restart \
  api api2 api3 api4 api5 api6 api7 api8 api_admin api_admin2
curl -k https://man1rokanhulu.cloud/health
```

For APK admin UI rollback:

```bash
cd /root/ujian_online
BACKUP=/root/ujian_online/deploy-backups/20260606_0138_apk_admin_ui
cp -a "$BACKUP/templates/admin/settings.html" templates/admin/settings.html
cp -a "$BACKUP/static/js/api/modules/30-ui-shortcuts.js" static/js/api/modules/30-ui-shortcuts.js
```

Git rollback if needed:

```bash
git revert b72a1f3863cd68655926407232ca24cbe991c06e
```

## Remaining Blockers
- Real cheating/violation events still have not been proven end-to-end from current clients.
- APK token/signature registration remains required before distributing the new APK.
- Manual admin verification of APK settings save flow remains pending.
- Phase 4.3.2H answer timing instrumentation remains not live.
- Phase 5/6 remains blocked and disabled.

## Final Phase Status
| Area | Status |
|---|---|
| Inter-session refresh | Live and usable with safer guards. |
| Phase 2.1 violation pipeline health | Live, observable, admin-only. |
| Phase 8.1 dashboard visibility | Partial/live summary visibility; real cheating events still absent. |
| APK rollout prep | Partial; admin access helpers live, registration/smoke pending. |
| Phase 5/6 queue/runtime-buffer | Still blocked/off. |

## Final Decision
- VPS safe for next exam: **YES**, current direct safe-mode health is good.
- Inter-session refresh usable: **YES**, with dry-run/confirm and no DB/Redis/PgBouncer by default.
- Violation dashboard usable: **PARTIAL**, pipeline health visible but no real cheating events yet.
- New APK safe to distribute: **PARTIAL/NO**, wait for token/signature registration and limited smoke.
- Phase 5/6 may start: **NO**.
