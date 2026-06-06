# Phase 5.4 Auth Lightweight Loading and Frontend Bundle Sync

Date: 2026-06-07

## 1. Latest GitHub head reviewed

Reviewed branch before patching:

```text
branch: review/sanitized-root-20260531-115153
base:   0f938952388f80f56048c12ab6541448657e1aa7
head:   0f938952388f80f56048c12ab6541448657e1aa7
new commits before work: none
```

Phase 5.4 source commits prepared from that base:

```text
3ec8768 fix: use lightweight auth user loading
b94b656 fix: sync frontend bundle modules with safe monitoring flow
```

## 2. Production action

```text
VPS deploy: NO
VPS restart: NO
.env change: NO
docker-compose.production.yml change: NO
DB migration/schema change: NO
production load-test: NO
APK/AAB action: NO
Phase 6 shadow/queue/hybrid activation: NO
```

Production remains intended direct safe-mode:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
```

## 3. Files changed

Backend/API:

```text
app/core/security.py
app/api/auth.py
app/api/users.py
app/api/grading.py
```

Backend tests:

```text
tests/test_auth_identity_loading.py
tests/test_admin_user_lightweight_queries.py
```

Frontend bundle/source sync:

```text
scripts/build_*_bundle.sh
static/js/**/*.js bundle/module files touched by source sync
```

Frontend tests:

```text
tests/test_frontend_bundle_sync.py
tests/test_restart_safe_guards.py
tests/test_auto_restart_scheduler_modal.py
```

## 4. Backend root cause

The Phase 5.3 audit found that a plain auth lookup:

```python
select(User).where(User.id == token_data.user_id)
```

could trigger `lazy="selectin"` relationship cascades from `User` into large related tables:

```text
exams
exam_sessions
questions
answers
exam_logs
question_options/question_tags
```

Live read-only proof from the audit:

```json
{"statements_count":15,"table_hints":["users","exams","exam_sessions","questions","exam_sessions","unknown","unknown","answers","answers","exam_logs","exam_sessions","questions","exam_logs","unknown","unknown"]}
```

The proposed lightweight path reduced that to one users-only SQL statement:

```json
{"statements_count":1,"table_hints":["users"]}
```

## 5. Backend fix summary

Added explicit lightweight load options in `app/core/security.py`:

```python
USER_IDENTITY_LOAD_OPTIONS = (
    load_only(...identity/role/is_active fields...),
    noload(User.created_exams),
    noload(User.exam_sessions),
)

USER_RESPONSE_LOAD_OPTIONS = (
    load_only(...UserResponse fields...),
    noload(User.created_exams),
    noload(User.exam_sessions),
)
```

Applied to:

```text
_resolve_authenticated_user()
get_current_user_for_refresh()
_load_user_response()
```

Admin user endpoint changes:

```text
/api/users/advanced-search now uses column projection, not User ORM rows.
/api/users/{user_id} now uses column projection, not User ORM rows.
/admin user mutation lookups use USER_RESPONSE_LOAD_OPTIONS.
username existence checks use User.id projection.
CSV user export uses projection instead of User ORM rows.
```

`GET /api/grading/stats` now uses `get_db_read` because it is read-only.

`GET /api/activity/logs` was intentionally not changed in this patch because it currently has opportunistic auto-prune write behavior. Splitting that read path from pruning remains a follow-up.

## 6. Auth behavior unchanged confirmation

No auth weakening was introduced:

```text
JWT decode/expiry validation remains unchanged.
Inactive users remain blocked.
Role checks remain unchanged.
No token bypass was added.
No public endpoint was added.
APK token/signature validation was not touched.
```

## 7. Frontend bundle mismatch summary

Before Phase 5.4, `scripts/verify_frontend_bundles.sh` failed because committed bundles and module sources were not aligned.

High-risk mismatch from the audit:

```text
committed static/js/admin/monitoring.js had safer restart flow,
but static/js/admin/monitoring/modules/00-core-ops-and-sessions.js was older/stale.
```

Phase 5.4 synced module sources and generated bundles so future rebuilds preserve the safe behavior.

The bundle build scripts were also adjusted to avoid generated trailing blank lines while keeping bundle verification deterministic.

## 8. Monitoring restart safety behavior preserved

Required safe behavior now exists in source module and generated bundle:

```text
dry-run/preflight before executing restart: YES
include_data_services=false by default: YES
UI shows DB/Redis/PgBouncer restart = TIDAK: YES
active sessions >0 hard block: backend guard unchanged
running exam window hard block: backend guard unchanged
next exam <5 minutes hard block: backend guard unchanged
next exam <30 minutes warning, not hard block: backend guard unchanged
success text says app-plane services restarted: YES
auto-restart scheduler also keeps data services excluded by default: YES
```

## 9. Validation results

Commands run:

```text
python -m compileall app
SECRET_KEY=test-secret-key DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test PYTHONPATH=. uv run --with-requirements requirements.txt --with pytest pytest tests/test_production_readiness_defaults.py tests/test_restart_safe_guards.py tests/test_frontend_bundle_sync.py tests/test_answer_sync_service_routing.py tests/test_auth_identity_loading.py tests/test_admin_user_lightweight_queries.py tests/test_auto_restart_scheduler_modal.py -q
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
```

Note: the system Python did not have `pytest`; validation used `uv run --with-requirements requirements.txt --with pytest ...` with dummy non-production `SECRET_KEY` and `DATABASE_URL` for import-time settings.

## 10. Forbidden artifact check

Checked staged/working tree filenames for sensitive/forbidden artifacts:

```text
.apk/.aab: none
.jks/.keystore/key.properties/local.properties: none
.env: none
backup/dump/sqlite/db/sql: none
session CSV/summary JSON: none
raw token/session/PII/full build token: none observed in changed files
```

Result:

```text
Forbidden artifact check: PASS
```

## 11. Rollback instructions

Source rollback only:

```bash
git revert b94b656
git revert 3ec8768
```

If later deployed to VPS and rollback is needed, use a separate controlled VPS rollback plan:

```text
1. confirm no active sessions/running exam windows/final submit drain
2. backup current live files
3. restore previous app/frontend source files by checksum
4. app-plane-only rolling restart
5. verify /health, effective answer settings, static assets, logs
```

Do not restart DB/Redis/PgBouncer for this rollback unless separately approved.

## 12. Remaining follow-ups

```text
1. Split GET /api/activity/logs read path from opportunistic auto-prune write behavior.
2. Continue monitoring GET /api/grading/stats after read-pool switch.
3. Consider broader ORM relationship strategy review; User auth/admin paths are fixed first.
4. Phase 6 shadow remains OFF until separately approved.
5. Queue/hybrid/runtime-buffer production remains NO-GO.
```

## 13. Final decision

```text
Backend API auth eager-load fixed: YES
Frontend bundle source sync fixed: YES
Safe for source review: YES
Safe for controlled VPS deploy plan: YES, after separate operator approval and deploy plan
Phase 6 shadow/queue/hybrid may start: NO
```
