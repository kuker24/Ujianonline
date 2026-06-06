# Phase 5.6 Activity Logs Read Path Fix

Date: 2026-06-07

## 1. Latest GitHub head reviewed

Before source work:

```text
branch: review/sanitized-root-20260531-115153
base: 2c423b2c7e056c02c86d7122bf3ff66dc5452d9c
head: 2c423b2c7e056c02c86d7122bf3ff66dc5452d9c
new commits before work: none
```

Forbidden precheck:

```text
forbidden artifact check: PASS
queue/hybrid/shadow activation check: PASS
```

## 2. Root cause summary

Phase 5.6 observation showed Phase 5.5 auth/user fixes were live and healthy, but admin API noise persisted around:

```text
GET /api/activity/logs took ~74015 ms
ConnectionDoesNotExistError cluster isolated to api_admin/activity logs
BrokenPipeError cluster isolated to api_admin/activity logs
```

The endpoint still had two reliability risks:

```text
1. GET /api/activity/logs called opportunistic auto-prune, so dashboard reads could perform writes.
2. GET /api/activity/logs used select(UserActivityLog).options(selectinload(UserActivityLog.user)), which can instantiate ORM rows and load User relationship paths instead of a lightweight projection.
```

## 3. Files changed

```text
app/api/activity.py
tests/test_activity_logs_read_only.py
tests/test_activity_logs_lightweight_queries.py
```

## 4. Read/prune split summary

`GET /api/activity/logs` is now a pure read endpoint:

```text
no opportunistic prune
no delete
no truncate
no smart prune
no write dependency
```

Cleanup remains available only through the explicit role-protected maintenance path:

```text
DELETE /api/activity/logs/reset?mode=all
DELETE /api/activity/logs/reset?mode=smart
```

That endpoint continues to use `get_db_write` and requires `get_current_active_admin`.

The auto-prune helper was removed from read paths to prevent dashboard polling from holding write-pool connections or deleting data during GET requests.

## 5. GET /api/activity/logs read-only status

```text
GET /api/activity/logs read-only: YES
uses get_db_read: YES
uses get_db/get_db_write: NO
performs prune/delete/truncate: NO
```

Other activity read endpoints were also moved to read dependency where safe:

```text
GET /api/activity/stats -> get_db_read, no auto-prune
GET /api/activity/event-types -> get_db_read
GET /api/activity/my-logs -> get_db_read and lightweight projection
```

## 6. Query/projection summary

`GET /api/activity/logs` now uses explicit column projection and outer join:

```text
UserActivityLog.id
UserActivityLog.user_id
User.full_name AS user_name
User.role AS user_role
UserActivityLog.event_type
UserActivityLog.event_data
UserActivityLog.ip_address
UserActivityLog.created_at
```

It no longer uses:

```text
selectinload(UserActivityLog.user)
select(UserActivityLog) ORM row loading
result.scalars().all()
log.user access
```

Count query is now a simple filtered activity-log count:

```text
select count(user_activity_logs.id)
```

instead of counting a subquery that inherits ORM eager-load shape.

## 7. Response compatibility note

Response shape remains compatible with the existing frontend:

```text
logs[].id
logs[].user_id
logs[].user_name
logs[].user_role
logs[].event_type
logs[].event_data
logs[].ip_address
logs[].created_at
total
page
per_page
total_pages
```

Fallback behavior is preserved:

```text
missing/deleted user -> user_name = "Unknown"
missing event_data -> {}
```

Default/max pagination remains bounded:

```text
per_page default = 50
per_page max = 200
```

## 8. Tests added

New tests:

```text
tests/test_activity_logs_read_only.py
tests/test_activity_logs_lightweight_queries.py
```

Coverage includes:

```text
GET /api/activity/logs uses get_db_read
GET /api/activity/logs has no prune/delete/write side effects
Prune/reset path remains explicit admin maintenance endpoint
Read activity endpoints do not call auto-prune
Per-page cap remains bounded
List query uses projection + outer join
List query does not instantiate UserActivityLog ORM rows
List query does not eager-load User relationships
Simple count query is used
Response shape remains frontend-compatible
GET /api/activity/my-logs uses projection and get_db_read
```

## 9. Validation results

Commands run:

```bash
python -m compileall app
SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test PYTHONPATH=. uv run --with-requirements requirements.txt --with pytest pytest \
  tests/test_production_readiness_defaults.py \
  tests/test_auth_identity_loading.py \
  tests/test_admin_user_lightweight_queries.py \
  tests/test_activity_logs_read_only.py \
  tests/test_activity_logs_lightweight_queries.py \
  tests/test_frontend_bundle_sync.py \
  tests/test_restart_safe_guards.py \
  -q
scripts/verify_frontend_bundles.sh
node --check static/js/api.js
node --check static/js/admin/monitoring.js
git diff --check
```

Results:

```text
compileall: PASS
pytest targeted suite: 61 passed
verify_frontend_bundles.sh: PASS (28 bundles)
node --check static/js/api.js: PASS
node --check static/js/admin/monitoring.js: PASS
git diff --check: PASS
```

## 10. Forbidden artifact check

```text
APK/AAB: none
keystore/JKS/key.properties/local.properties: none
.env/.env.*: none
DB dump/backup/sql/sqlite/db: none
session CSV/summary JSON: none
raw token/session/student PII/answer content: none
```

Result:

```text
Forbidden artifact check: PASS
```

## 11. Production action performed

```text
deploy: NO
restart: NO
.env change: NO
migration/schema change: NO
production load-test: NO
APK action: NO
queue/hybrid activation: NO
Phase 6 shadow activation: NO
DB/Redis/PgBouncer restart: NO
```

This is source-only and requires a separate controlled VPS deploy approval before going live.

## 12. Rollback plan

Source rollback:

```bash
git revert 8c2e071
git revert f0d919b
```

If later deployed to VPS and rollback is needed:

```text
1. confirm active sessions/running exam/final-submit drain are all zero
2. restore prior app/api/activity.py from the deploy backup directory
3. app-plane-only rolling restart
4. verify /health, /api/activity/logs, env direct-safe-mode, and logs
5. do not restart DB/Redis/PgBouncer unless separately approved
```

## 13. Final decision

```text
Activity logs read path fixed: YES
Admin API noise source fixed in source: YES, pending controlled deploy and observation
Safe for controlled VPS deploy plan: YES
Phase 6 production may start: NO
Phase 6 shadow may start: NO until this source fix is deployed and observed clean
Queue/hybrid may start: NO
```
