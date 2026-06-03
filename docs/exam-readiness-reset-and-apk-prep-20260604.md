# Operational Freeze — Exam Readiness Reset + APK Preparation

Tanggal pemeriksaan: 2026-06-04 WIB

Scope:

- Stop sementara eksperimen/perubahan performa backend karena sistem akan dipakai ujian.
- Verifikasi VPS siap ujian dalam direct safe-mode.
- Bersihkan leftover synthetic/load-test yang jelas.
- Audit kesiapan APK source/build planning tanpa membangun APK.

Tidak dilakukan:

- Tidak deploy commit baru.
- Tidak restart container/service.
- Tidak menjalankan load-test baru.
- Tidak menjalankan migration/schema change.
- Tidak membuka Phase 5.
- Tidak build APK/AAB.
- Tidak commit/export backup, token, CSV, summary JSON, APK/AAB, keystore, atau `.env`.

## 1. GitHub State

Latest branch reviewed:

```text
09da48cb956401df5c11406fc0752bed59f70e3f perf: instrument direct answer write latency
```

Comparison:

```text
base: 09da48cb956401df5c11406fc0752bed59f70e3f
head: review/sanitized-root-20260531-115153
```

Result:

```text
No new commits after 09da48c at review time.
```

Visible CI/status:

```text
Dependency Graph workflow: success. No real app test CI observed for this branch.
```

## 2. VPS Deployed Code Markers

VPS path:

```text
/root/ujian_online
```

VPS directory is not a git checkout:

```text
git_rev=NOT_GIT_CHECKOUT
```

Host and API container markers in `app/services/answer_sync_service.py`:

| Marker | Status |
|---|---:|
| `changed_answer_payload` | true |
| peak-mode progress skip | true |
| `SUBMIT-ANSWER-TIMING` | false |

Interpretation:

- Phase 4.3.2G runtime patch is deployed.
- Phase 4.3.2H instrumentation commit `09da48c` is **not deployed** to VPS.
- This is acceptable for exam freeze because instrumentation is not needed unless diagnosing and should remain off by default.

## 3. Env Safe-Mode Status

Runtime env sampled from API container:

| Setting | Value | Target | Status |
|---|---|---|---|
| `ANSWER_WRITE_MODE` | `direct` | `direct` | OK |
| `ANSWER_QUEUE_ENABLED` | `false` | `false` | OK |
| `ANSWER_QUEUE_PERCENTAGE` | `0` | `0` | OK |
| `EXAM_PEAK_MODE` | `true` | `true` | OK |
| `VIOLATION_ASYNC_ENABLED` | `true` | `true` | OK |
| `ADMIN_MONITORING_DETAIL_LEVEL` | `summary` | `summary` | OK |
| `MOBILE_APK_PRIMARY` | `true` | `true` | OK |
| `SEB_DESKTOP_LEGACY_ENABLED` | `false` | `false` | OK |
| `SEB_QR_ENABLED` | `false` | `false` | OK |
| `SEB_DEBUG_ENDPOINTS_ENABLED` | `false` | `false` | OK |
| `APK_BUILD_ENDPOINT_ENABLED` | `false` | `false` | OK |
| `TELEGRAM_ALERTING_ENABLED` | `false` | `false` | OK |
| `HEAVY_EXPORT_ENABLED` | `false` | `false` | OK |
| `ANSWER_HOT_PATH_TIMING_ENABLED` | unset | off/false | OK |

No env change was needed.

## 4. Docker / Container Status

`docker compose -f docker-compose.production.yml ps` showed all primary services up/healthy:

- API replicas: `api` through `api8` healthy.
- Admin API replicas: `api_admin`, `api_admin2` healthy.
- PostgreSQL healthy.
- PgBouncer healthy.
- Redis healthy.
- Nginx healthy.
- Celery worker/beat healthy.
- Prometheus/Grafana healthy.

No restart was performed.

## 5. Health and Resource Checks

| Check | Result |
|---|---|
| Public API `/health` | `200` |
| Admin API internal `/health` | `200` |
| PostgreSQL `pg_isready` | accepting connections |
| PgBouncer `pg_isready` | accepting connections |
| Redis `PING` | `PONG` |
| Redis rejected connections | `0` |
| Redis evicted keys | `0` |
| Nginx config test | successful |
| Long active query >5s | `0` |
| Long idle-in-transaction >5s | `0` |
| Load-test process running | none found |
| Disk `/` | 48% used |
| Memory | 15Gi total, about 11Gi available |
| Load average | low at recheck |

## 6. Exam / Session State

Read-only aggregate DB checks:

| Check | Result |
|---|---:|
| Active published exam windows | `0` |
| Global in-progress/active sessions | `0` |
| Next published exam start | `2026-06-04 07:30:00 WIB` |
| Sessions without user linkage | `0` |
| Terminal sessions without score | `5` |

Notes:

- `terminal_sessions_without_score=5` was observed as aggregate only and was not modified.
- No real data was changed.

## 7. Synthetic / Load-Test Data Status

Known synthetic prefixes checked:

- `LOADTEST_SYNTHETIC_20260604_PHASE432F_`
- `LOADTEST_SYNTHETIC_20260604_PHASE432G_`
- `LOADTEST_X_PHASE432G`
- `LOADTEST_`
- `SYNTHETIC_`

Aggregate result:

| Synthetic entity | Count |
|---|---:|
| Users | `0` |
| Exams | `0` |
| Sessions | `0` |
| Questions | `0` |
| Answers | `0` |
| Exam logs | `0` |
| Security events | `0` |
| User activity logs | `0` |

DB cleanup action:

```text
No DB cleanup needed because exact synthetic counts were already 0.
```

## 8. Temporary File Cleanup

Earlier exact temporary files removed from VPS `/tmp`:

- `/tmp/phase432g_cleanup.sql`
- `/tmp/ujianonline-phase432f-target-pip.log`
- `/tmp/ujianonline-phase432f-help-host.txt`
- `/tmp/phase432g_load_test_help.txt`
- `/tmp/phase432g_run_tier.sh`

Final `/tmp` candidate check for phase/load-test/synthetic/session/token/summary/monitor files returned no candidates.

No backup, uploads, static/media files, or APK release assets were removed.

## 9. Backup Status

Latest observed backup:

```text
/root/ujian_online/backups/backup_20260604_021501.sql.gz
```

Details:

| Field | Value |
|---|---|
| Size | `11,910,935 bytes` |
| Timestamp | `2026-06-04 02:15:07 +0700` |
| gzip test | pass |

No new backup was created and no backup was exported/committed.

## 10. Component Status Table

| Component | Status | Notes |
|---|---|---|
| Backend API health | Bisa dipakai | `/health=200` |
| Admin API health | Bisa dipakai | internal health 200 |
| Database/Postgres | Bisa dipakai | accepting connections |
| PgBouncer | Bisa dipakai | accepting connections |
| Redis | Bisa dipakai | rejected/evicted 0 |
| Nginx | Bisa dipakai | config test OK |
| Direct answer save | Bisa dipakai | direct mode enabled |
| Final submit | Bisa dipakai | no new change; previous samples OK |
| Cheating detection | Bisa dipakai | async enabled; nginx shed status unchanged |
| Admin monitoring | Bisa dipakai | summary-only |
| Heavy exports | Jangan dipakai | disabled for exam window |
| Telegram alerting | Jangan dipakai | disabled |
| SEB desktop legacy | Jangan dipakai by default | optional/off |
| Android/APK runtime | Perlu verifikasi APK build | primary target, source present |
| APK build endpoint | Jangan dipakai | disabled in production |
| Queue/hybrid/runtime-buffer | Jangan dipakai | off; Phase 5 blocked |
| Load-test helper | Jangan dipakai saat ujian | only outside live exam window |
| Hot-path timing instrumentation | Perlu approval/diagnosis | not deployed on VPS; default off |
| Synthetic data status | Bisa dipakai / clean | no leftovers |
| Backup status | Bisa dipakai for emergency | latest gzip pass |

## 11. What Can Be Used Now

USABLE NOW:

- Direct answer write mode.
- Final submit.
- Cheating detection async/aggregate path.
- Admin dashboard summary monitoring.
- Android/APK runtime as target.
- Existing source APK review/build planning.

USABLE WITH CAUTION:

- Current backend under direct mode at moderate load.
- Phase 4.3.2G patch.
- Hot-path timing instrumentation only after explicit deploy/enable for diagnosis.
- Load-test helper only outside live exam window.

NOT READY / DO NOT USE:

- Phase 5 hybrid/queue/runtime-buffer.
- Direct-600 confidence.
- Heavy exports during exam.
- APK build endpoint in production.
- SEB debug endpoints.
- Production load test during real exam window.
- Raw data export.
- Committing APK/AAB/keystore/env/backup/CSV/summary JSON.

## 12. APK Source Readiness

Source files inspected:

- `flutter_client_code/pubspec.yaml`
- `flutter_client_code/lib/config.dart`
- `flutter_client_code/lib/main.dart`
- `flutter_client_code/lib/services/`
- `flutter_client_code/lib/pages/`
- `flutter_client_code/android/app/build.gradle`
- `flutter_client_code/android/app/src/main/AndroidManifest.xml`
- `flutter_client_code/android/app/src/main/res/xml/network_security_config.xml`
- `flutter_client_code/android/app/proguard-rules.pro`
- `flutter_client_code/sxb_dependencies.yaml`
- `tools/apk_builder_gui.py`
- `tools/apk_builder_gui/apk_builder_config.json`

Confirmed in `flutter_client_code/lib/config.dart`:

| Check | Result |
|---|---|
| API URL | `https://man1rokanhulu.cloud/` |
| `forceHttps` | `true` |
| `allowCleartextTraffic` | `false` |
| `answerJournalSyncIntervalSeconds` | `6` |
| `answerJournalBatchSize` | `80` |
| `enableKiosk` | `true` |
| `blockScreenshot` | `true` |
| `detectRoot` | `true` |
| `blockTaskSwitch` | `true` |

Confirmed in Android release config:

| Check | Result |
|---|---|
| `applicationId` | `com.school.examapp` |
| `compileSdk` | `36` |
| `targetSdk` | `35` |
| release `minifyEnabled` | `true` |
| release `shrinkResources` | `true` |
| signing config | expects local `key.properties` |
| release manifest cleartext | `false` |
| release network security config | cleartext `false` |

Native security/kiosk checks:

- Native `MainActivity.kt` has kiosk channel.
- `FLAG_SECURE` screenshot/screen-record blocking exists when exam starts.
- Hardware keys/back behavior are partially blocked during exam.
- Signature verification channel exists.

## 13. APK Build Blockers

APK is not ready for release build yet:

1. Flutter CLI is not available in the local environment:

   ```text
   flutter_not_available
   ```

2. Java is available:

   ```text
   OpenJDK 17.0.19
   ```

3. `tools/apk_builder_gui/apk_builder_config.json` still contains stale local HTTP URL:

   ```text
   http://192.168.18.120:8000
   ```

   This must be updated through APK Builder GUI or config workflow before any release build.

4. Static source mismatch likely blocks `flutter analyze/build`:

   `flutter_client_code/lib/pages/exam_page.dart` calls methods/parameters not present in `flutter_client_code/lib/services/security_service.dart`, including:

   - `initialize(runInitialChecks: false, startPeriodicChecks: false)`
   - `SecurityService.disableClipboard()`
   - `SecurityService.checkKeyboardSecurity()`
   - `SecurityService.getJsToDisableAutocomplete()`
   - `_securityService.startPeriodicChecks()`
   - `_securityService.startAntiCheatMonitoring(...)`
   - `_securityService.stopPeriodicChecks()`
   - `_securityService.stopAntiCheatMonitoring()`

5. Release signing is not verified in this environment. `key.properties` and keystore must remain local/secret and must not be committed.

6. `config.dart` currently has `answerJournalSyncIntervalSeconds=6`, while APK Builder GUI profile now enforces safer minimums for `ux_offline_first` generation. Do not change runtime tuning without operator approval.

## 14. APK Dry Checks

Executed:

```text
python -m pytest tests/test_apk_builder_gui_config.py -q
```

Result:

```text
3 passed
```

Not executed because Flutter CLI unavailable:

- `flutter pub get`
- `flutter analyze`
- `flutter test`
- `flutter build apk --release`

No APK/AAB was built.

## 15. Forbidden Artifact Check

No dirty forbidden artifacts were found in the VPS working tree status.

Local tracked artifact check did not show committed APK/AAB/keystore/build outputs. Existing tracked SQL/backup scripts are project tooling, not generated production DB dumps:

- `app/migrations/create_materialized_views.sql`
- `docker/init.sql`
- backup utility scripts/docs

No `.env`, APK/AAB, keystore, secret, CSV, summary JSON, or raw student data was committed.

## 16. Decisions

Backend/VPS:

```text
VPS siap ujian mode direct safe-mode.
```

Performance work:

```text
Stop performance experiments for exam window.
Phase 5 remains blocked.
```

APK:

```text
APK preparation not ready for release build yet.
Fix source mismatch, update APK Builder config, verify Flutter toolchain, then run dry checks before any signed release build.
```

## 17. Rollback Notes

No production deploy was performed in this readiness reset, so there is no new deployment rollback.

If branch instrumentation commit must be reverted:

```bash
git revert 09da48cb956401df5c11406fc0752bed59f70e3f
```

If the Phase 4.3.2G runtime patch must be reverted later in an approved safe window:

```bash
git revert be684df9ac8730c3342376bd55a519621dcf7ece
```
