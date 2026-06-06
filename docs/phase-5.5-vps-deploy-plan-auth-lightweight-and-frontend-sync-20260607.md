# Phase 5.5 VPS Deploy Plan — Auth Lightweight and Frontend Bundle Sync

Date: 2026-06-07

## 1. Purpose

Controlled VPS deployment plan for Phase 5.4 source patch:

```text
Backend: lightweight auth/user loading to reduce ORM eager-loading pressure.
Admin users: advanced search/detail use lightweight projection.
Grading stats: read-only DB dependency.
Frontend: committed bundles and module sources synchronized.
Restart-safe UI: data services remain excluded by default.
```

This document is a plan only. It does not approve or perform deployment.

## 2. Latest GitHub head reviewed

```text
branch: review/sanitized-root-20260531-115153
base:   508b3b9b49419b83587aeeee3425f4a19dc8b067
head:   508b3b9b49419b83587aeeee3425f4a19dc8b067
new commits before plan: none
```

Required Phase 5.4 commits are present:

```text
3ec8768 fix: use lightweight auth user loading
b94b656 fix: sync frontend bundle modules with safe monitoring flow
508b3b9 docs: record phase 5.4 auth and frontend bundle sync
```

## 3. Source status confirmed

Confirmed in source:

```text
USER_IDENTITY_LOAD_OPTIONS uses load_only + noload(User.created_exams/exam_sessions).
_resolve_authenticated_user() uses USER_IDENTITY_LOAD_OPTIONS.
get_current_user_for_refresh() uses USER_IDENTITY_LOAD_OPTIONS.
_load_user_response() uses USER_RESPONSE_LOAD_OPTIONS.
/api/users/advanced-search uses projection, not full User ORM rows.
/api/users/{user_id} uses projection, not full User ORM rows.
GET /api/grading/stats uses get_db_read.
GET /api/activity/logs intentionally unchanged due to auto-prune write behavior.
static/js/admin/monitoring.js and module source keep safe restart flow.
Phase 6 shadow/queue/hybrid remains OFF in source defaults.
```

## 4. Source validation before deploy

Validation commands completed before writing this plan:

```bash
python -m compileall app
SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test PYTHONPATH=. uv run --with-requirements requirements.txt --with pytest pytest \
  tests/test_production_readiness_defaults.py \
  tests/test_restart_safe_guards.py \
  tests/test_frontend_bundle_sync.py \
  tests/test_answer_sync_service_routing.py \
  tests/test_auth_identity_loading.py \
  tests/test_admin_user_lightweight_queries.py \
  tests/test_auto_restart_scheduler_modal.py \
  -q
scripts/verify_frontend_bundles.sh
node --check static/js/api.js
node --check static/js/admin/monitoring.js
git diff --check
```

Results:

```text
compileall: PASS
pytest targeted suite: 78 passed
verify_frontend_bundles.sh: PASS (28 bundles)
node --check static/js/api.js: PASS
node --check static/js/admin/monitoring.js: PASS
git diff --check: PASS
forbidden artifact check: PASS
```

## 5. Hard deployment constraints

Do not deploy if any hard gate fails.

Forbidden actions:

```text
Do not enable Phase 6 shadow.
Do not enable queue/hybrid.
Do not change ANSWER_WRITE_MODE.
Do not change .env or .env.*.
Do not overwrite docker-compose.production.yml.
Do not run production load-test.
Do not change APK/AAB or APK registration.
Do not run DB migration/schema change.
Do not restart DB/Redis/PgBouncer.
Do not commit/deploy keystore/JKS/key.properties/local.properties.
Do not deploy dumps/backups/sqlite/sql/session CSV/summary JSON/token artifacts.
```

Expected effective production defaults after deployment:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
EXAM_PEAK_MODE=true
VIOLATION_ASYNC_ENABLED=true
ADMIN_MONITORING_DETAIL_LEVEL=summary
MOBILE_APK_PRIMARY=true
```

## 6. Operator approval gate

Deployment requires explicit operator approval in a later step, for example:

```text
approve deploy Phase 5.4
```

Without that approval, stop after this plan.

## 7. VPS preflight gates

Run read-only preflight before copying files.

Hard stop gates:

```text
active in-progress sessions = 0
running exam windows = 0
final-submit/drain active = 0
DB long active queries >60s = 0
DB idle-in-transaction = 0
Redis rejected connections = 0
Redis evicted keys = 0
local /health = 200
public /health = 200
API/admin app-plane containers healthy
DB/PgBouncer/Redis healthy
operator approval present
```

Resource gates:

```text
disk not near full
memory available acceptable
next exam start known
no production load-test process running
```

Recommended read-only checks:

```bash
curl -fsS http://127.0.0.1/health
curl -fsS https://man1rokanhulu.cloud/health
cd /root/ujian_online && docker compose -f docker-compose.production.yml ps
cd /root/ujian_online && docker compose -f docker-compose.production.yml exec -T redis redis-cli PING
```

Use explicit compose file only:

```text
docker compose -f docker-compose.production.yml ...
```

## 8. Files to deploy

### Backend runtime files

```text
app/core/security.py
app/api/auth.py
app/api/users.py
app/api/grading.py
```

### Frontend/static files

Deploy changed static/module files from Phase 5.4, including served bundles and their module sources:

```text
static/js/activity-logs.js
static/js/admin-core.js
static/js/admin/monitoring.js
static/js/admin/monitoring/modules/00-core-ops-and-sessions.js
static/js/alarm-system.js
static/js/api-error-handler.js
static/js/api-error-handler/modules/00-api-error-handler-core.js
static/js/api.js
static/js/api/modules/30-ui-shortcuts.js
static/js/auth.js
static/js/auth/modules/10-auth-bootstrap-utils.js
static/js/bootstrap-modal-fix.js
static/js/custom-confirm.js
static/js/custom-confirm/modules/00-custom-confirm-core.js
static/js/dashboard-widgets.js
static/js/empty-state.js
static/js/exam-builder.js
static/js/exam-builder/modules/00-bootstrap-settings-events.js
static/js/exam-scheduling.js
static/js/exam-scheduling/modules/00-exam-scheduling-core.js
static/js/exam-system.js
static/js/exam-templates.js
static/js/exam-templates/modules/10-exam-templates-bootstrap.js
static/js/header-user.js
static/js/media-library.js
static/js/media-library/modules/00-sanitize-and-render-utils.js
static/js/media-library/modules/10-media-library-class.js
static/js/mobile-nav.js
static/js/modern-modals.js
static/js/modern-modals/modules/00-styles-utilities-static-modal.js
static/js/notifications.js
static/js/performance-optimizer.js
static/js/performance-optimizer/modules/10-performance-optimizer-bootstrap-export.js
static/js/profile-modal.js
static/js/profile-modal/modules/20-avatar-sync-and-bootstrap.js
static/js/seb-auth-diagnostic.js
static/js/seb-builder.js
static/js/sidebar-loader.js
static/js/sidebar-loader/modules/10-sidebar-loader-bootstrap.js
static/js/toast.js
static/js/toast/modules/00-toast-core.js
static/js/universal-modal-fix.js
static/js/universal-modal-fix/modules/00-universal-modal-fix-core.js
static/js/user-management.js
static/js/user-management/modules/00-user-management-core.js
```

### Source-hygiene scripts

Optional but recommended if the VPS source tree should retain the same bundle-verification behavior as GitHub:

```text
scripts/build_*_bundle.sh
```

These scripts are not runtime-served assets. They must not trigger any build on production unless explicitly needed for verification. Prefer deploying the changed scripts only as source files, not executing a production rebuild.

### Files explicitly not deployed

```text
.env
.env.*
docker-compose.production.yml
APK/AAB
flutter_client_code/build
keystore/JKS/key.properties/local.properties
DB dump/backup/sql/sqlite/db
session CSV/summary JSON
node_modules
raw token/secret files
tests unless specifically needed for source audit only
docs unless specifically desired for live documentation only
```

## 9. Backup and checksum plan

Create backup directory:

```bash
BACKUP_DIR=/root/ujian_online_backups/phase-5.4-auth-frontend-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$BACKUP_DIR"
```

For every deployed file:

```text
1. verify existing live file path or record MISSING
2. copy existing file to backup preserving path
3. record pre-copy sha256
4. copy GitHub source file to VPS path
5. record post-copy sha256
6. compare post-copy sha256 with source sha256
7. preserve normal ownership/permissions
```

Record checksums into the deploy result document.

## 10. Deployment procedure after approval

Only after approval:

```text
1. run preflight and confirm all hard gates pass
2. create backup directory
3. upload selected files to a temp directory
4. backup each live file and record pre checksums
5. copy backend files
6. copy frontend/static/module files
7. optionally copy changed build scripts as source files only
8. do not change .env
9. do not run migration
10. do not restart DB/Redis/PgBouncer
11. restart app-plane only
```

App-plane restart scope:

```text
api
api2
api3
api4
api5
api6
api7
api8
api_admin
api_admin2
```

Do not restart by default:

```text
db
pgbouncer
redis
nginx
celery/worker/beat
prometheus/grafana
```

If static files are bind-mounted through Nginx, Nginx restart should not be needed.

## 11. Post-deploy validation

Immediately validate:

```text
https://man1rokanhulu.cloud/health = 200
http://127.0.0.1/health = 200
API/admin app-plane containers healthy
DB/PgBouncer/Redis still healthy and not restarted
effective answer env remains direct/queue-off/shadow-off
```

Backend functional checks:

```text
admin auth/login safe check
refresh endpoint safe check if available
/api/admin/users/advanced-search returns 200
/api/users/{safe_user_id} returns 200 if safe admin/test user exists
/api/admin/stats/dashboard returns 200
/api/grading/stats returns 200
no ImportError/ModuleNotFoundError/Traceback
```

Frontend/static checks:

```text
/static/js/admin/monitoring.js returns 200
/static/js/api.js returns 200
admin monitoring page loads
restart-safe UI preflight text is present
DB/Redis/PgBouncer restart = TIDAK by default
include_data_services=false confirmed in served JS
success text says app-plane services restarted
```

Optional safe source check on VPS:

```text
scripts/verify_frontend_bundles.sh
```

If scripts are not deployed or dependencies are unsuitable on VPS, record that bundle verification was source-only before deploy.

## 12. Observation window

Observe for at least 30 minutes after restart or until next quiet checkpoint.

Record:

```text
health endpoints
API/admin container health
nginx 500 count
nginx 499 count on admin endpoints
API asyncpg InternalClientError/ConnectionDoesNotExistError/BrokenPipeError count
HTTP 503/409 burst count
static 404/5xx count
memory/disk
Redis rejected/evicted
DB long active queries
DB idle-in-transaction
queue/hybrid routing count = 0
runtime shadow activation count = 0
```

Expected improvement:

```text
auth/admin user requests are lighter
advanced-search/dashboard noise should reduce
frontend static source/bundle mismatch is no longer a deploy risk
```

## 13. Rollback plan

Rollback triggers:

```text
health fails
auth/login breaks
admin user endpoints break
dashboard/static breaks
500 burst appears
startup/import error appears
restart-safe UI regresses
queue/hybrid/shadow unexpectedly activates
```

Rollback steps:

```text
1. confirm no active sessions/running exam/final-submit drain
2. restore files from backup directory
3. app-plane-only rolling restart
4. verify health and direct safe-mode env
5. do not restart DB/Redis/PgBouncer unless separately approved
```

## 14. Deploy result report requirement

After an approved deployment, create:

```text
docs/phase-5.5-vps-deploy-result-auth-lightweight-and-frontend-sync-20260607.md
```

The result document must include:

```text
latest GitHub head reviewed
new commits found before deploy, if any
operator approval text
VPS preflight result
files deployed
files explicitly not deployed
backup directory
pre/post checksums
restart scope
services not restarted
effective env after restart
health after deploy
backend checks
frontend checks
restart-safe UI validation
observation result
error/log summary
source validation result
forbidden artifact check
production action performed
rollback reference
final PASS/FAIL/PARTIAL decision
```

## 15. Final decision for this plan

```text
Deploy plan created: YES
Source validation before deploy: PASS
Ready to request operator approval: YES
Deployment performed by this plan document: NO
Phase 6 shadow remains OFF: YES
Queue/hybrid remains OFF: YES
```
