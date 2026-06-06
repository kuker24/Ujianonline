# Phase 5.3 Backend API and Frontend Static Audit

Date: 2026-06-07

## 1. Scope

This audit investigates why the admin monitoring dashboard may report problems in:

```text
backend_api
frontend_static
```

The audit was read-only on production:

```text
no deploy
no restart
no .env change
no docker-compose.production.yml change
no DB migration or DDL
no Redis/PostgreSQL/PgBouncer restart
no queue/hybrid/runtime-buffer enablement
no APK/AAB action
no production load-test
```

## 2. GitHub state

Compared base and branch head before audit:

```text
base: 6b39d4db4986e35c9d538c20b02c8e57e18fae36
head: 6b39d4db4986e35c9d538c20b02c8e57e18fae36
commits base..head: 0
```

No new commits were present before the audit.

## 3. Executive summary

### Frontend static

Production static serving itself is healthy:

```text
local/public static asset probes: 200
nginx static_404 over sampled window: 0
nginx static_5xx over sampled window: 0
live key static checksums match GitHub head
nginx and API containers see the same mounted static files
```

The real frontend/static issue is source hygiene:

```text
scripts/verify_frontend_bundles.sh fails
14 committed bundles are out of sync with module sources
```

This is dangerous because a future rebuild from stale modules can overwrite currently safer committed bundles, especially `static/js/admin/monitoring.js`.

### Backend API

Backend health endpoints are up, but there is real admin API reliability noise:

```text
only 2 nginx 500s found in 240m sample
several 499 client-cancelled admin monitoring/user endpoints
API logs include asyncpg InternalClientError / ConnectionDoesNotExistError / BrokenPipeError
```

Primary root cause found:

```text
simple auth lookup select(User) triggers eager selectin loading of large relationships
```

Evidence from live read-only SQL instrumentation:

```json
{"statements_count":15,"table_hints":["users","exams","exam_sessions","questions","exam_sessions","unknown","unknown","answers","answers","exam_logs","exam_sessions","questions","exam_logs","unknown","unknown"]}
```

A proposed `load_only + noload` identity lookup reduces this to one SQL statement:

```json
{"statements_count":1,"table_hints":["users"]}
```

## 4. Production HTTP/static evidence

Core endpoints and assets returned 200:

```text
http://127.0.0.1/health                                  200
https://127.0.0.1/health                                 200
https://man1rokanhulu.cloud/health                       200
https://127.0.0.1/api/runtime/policy                     200
https://127.0.0.1/static/js/api.js                       200
https://127.0.0.1/static/js/auth.js                      200
https://127.0.0.1/static/js/exam-system.js               200
https://127.0.0.1/static/js/admin/monitoring.js          200
https://127.0.0.1/static/css/admin.css                   200
https://127.0.0.1/static/css/student.css                 200
https://127.0.0.1/static/components/sidebar.html         200
https://127.0.0.1/static/sw.js                           200
https://man1rokanhulu.cloud/static/js/api.js             200
https://man1rokanhulu.cloud/static/js/auth.js            200
https://man1rokanhulu.cloud/static/js/admin/monitoring.js 200
https://man1rokanhulu.cloud/static/css/admin.css         200
```

Nginx/API static mount checksums matched for key files.

## 5. Live checksum evidence

Live VPS checksums matched GitHub head for sampled files:

```text
7b19134da0d759a646057e0fc71ff5a44a7a2f2a8ffdf15b68d5bb40fee187eb  static/js/api.js
c2e18a607d6d930720249c4147942d0a4b10726252fb17c6033d61e9b446623b  static/js/auth.js
65db58a40506c313644fa70f3d85cc6c215937024f22180e59318b395d994e02  static/js/exam-system.js
a6748d3b80459f411324b92367fa7338352a95cda25fe5caa0b4d4e8fb383706  static/js/admin/monitoring.js
7e5c0bdce4085148c3058ff3e6c16529c60ef623c060abf4d5678fce072ce1ef  static/css/admin.css
f6929dc917c2f27a4c05a1a54fc9c69fd4b6957991fed32945a3436c3436a545  static/css/student.css
f5e79d830759fbc90c49097218e3a6ff28ca49906772e172c67c70aebbaf75dd  static/components/sidebar.html
05b71f33f983e310e4909bd4bfe54080eeaea50e20eb35eff8331480125ef5d6  static/sw.js
e115c8d2eaa98235c73e3760fbd7cc92c6c6d2a7000140477b532f1832babbfd  templates/admin/monitoring.html
f240b2f21165d95c3e10306a4f6ecc26a42f076a6092a7d838e72819d2ead463  templates/student/exam.html
```

## 6. Frontend static dashboard-probe nuance

The frontend static layer in `app/core/ops_summary.py` builds a probe URL from the request Host header.

Observed behavior from inside the API container:

```json
{
  "man1rokanhulu.cloud": {
    "public_base": "https://man1rokanhulu.cloud",
    "static_probe_status": 200
  },
  "127.0.0.1": {
    "public_base": "http://127.0.0.1",
    "static_probe_error": "All connection attempts failed"
  },
  "103.175.218.56": {
    "public_base": null,
    "static_probe_error": "probe_url_missing"
  }
}
```

Interpretation:

```text
If admin monitoring is opened through the public domain, frontend static probe is healthy.
If it is opened through an untrusted IP/internal Host, ops_summary can report frontend_static critical even though Nginx public static serving is fine.
```

## 7. Frontend bundle source-sync failure

Local clean source validation:

```text
python -m compileall app: PASS
python -m pytest ...: unavailable in system interpreter
scripts/verify_frontend_bundles.sh: FAIL
```

Out-of-sync bundles reported:

```text
static/js/api.js
static/js/admin/monitoring.js
static/js/exam-builder.js
static/js/exam-templates.js
static/js/seb-builder.js
static/js/profile-modal.js
static/js/activity-logs.js
static/js/alarm-system.js
static/js/sidebar-loader.js
static/js/notifications.js
static/js/performance-optimizer.js
static/js/auth.js
static/js/admin-core.js
static/js/header-user.js
```

Most differences are newline/minor formatting. The high-risk difference is `static/js/admin/monitoring.js`:

```text
committed bundle contains safer restart flow:
- dry-run preflight before execution
- include_data_services=false by default
- UI shows DB/Redis/PgBouncer restart = TIDAK
- success message says app-plane services restarted

module source is older/unsafe:
- no preflight confirm details
- include_data_services follows fullRestartAvailable
- future rebuild could reintroduce DB/Redis/PgBouncer restart from UI
```

Therefore the repo should not run frontend bundle rebuilds until module sources are synced to the committed safe bundles.

## 8. Backend API evidence

Nginx 5xx paths in the sampled window:

```json
{"count":1,"status":500,"method":"GET","path":"/api/admin/stats/dashboard"}
{"count":1,"status":500,"method":"GET","path":"/api/admin/users/advanced-search"}
```

Nginx 499 client-cancelled admin endpoints included:

```text
/api/admin/monitoring/system/ops-summary
/api/admin/monitoring/active-exams
/api/admin/v1/settings/timezone
/api/admin/users/student-classes
/api/admin/users/advanced-search
/api/admin/monitoring/system/metrics
```

API exception summary included:

```text
asyncpg.exceptions._base.InternalClientError: cannot switch to state 11; another operation (2) is in progress
asyncpg.exceptions.ConnectionDoesNotExistError: connection was closed in the middle of operation
sqlalchemy.exc.DBAPIError: connection was closed in the middle of operation
BrokenPipeError: [Errno 32] Broken pipe
```

Slow request evidence before DBAPI/BrokenPipe errors:

```text
GET /api/grading/stats took ~24s
GET /api/activity/logs took ~75s
```

## 9. Backend root cause

The `User` model has eager selectin relationships:

```python
created_exams = relationship(..., lazy="selectin")
exam_sessions = relationship(..., lazy="selectin")
```

Related models also use `lazy="selectin"`, including session answers/logs/questions. As a result, a plain auth lookup:

```python
select(User).where(User.id == token_data.user_id)
```

can cascade into extra queries over:

```text
exams
exam_sessions
questions
answers
exam_logs
question_options/question_tags
```

This explains:

```text
admin API requests become unexpectedly heavy
browser/admin polling cancels slow requests (499)
connection can be closed/cancelled mid-operation
asyncpg reports another operation/closed connection errors
occasional 500 is surfaced on unrelated admin endpoints sharing the same pattern
```

## 10. Minimal backend fix plan

Source-only; do not deploy without separate approval.

### 10.1 Add lightweight user identity load options

Add a helper near `app/core/security.py`:

```python
from sqlalchemy.orm import load_only, noload

USER_IDENTITY_LOAD_OPTIONS = (
    load_only(
        User.id,
        User.username,
        User.full_name,
        User.role,
        User.student_class,
        User.job_title,
        User.is_active,
        User.profile_picture,
        User.last_login,
    ),
    noload(User.created_exams),
    noload(User.exam_sessions),
)
```

Use it for:

```text
_resolve_authenticated_user()
get_current_user_for_refresh()
```

Expected result:

```text
auth lookup SQL count: 15 -> 1
no answers/exam_logs loaded during auth
```

### 10.2 Fix admin user endpoints that instantiate User ORM rows

At minimum:

```text
/api/users/advanced-search
/api/users/{user_id}
```

should use lightweight projection or `load_only + noload` to avoid relationship cascades.

Existing `list_users` and `students-by-class` already use lightweight column projection.

### 10.3 Convert read-only endpoints away from write DB dependency where safe

Candidates:

```text
GET /api/grading/stats uses get_db but should use get_db_read if no writes are performed
GET /api/activity/logs uses get_db and also runs auto-prune; split read endpoint from maintenance/prune side effect
```

Do not remove retention controls; move prune to a scheduled/explicit path rather than a dashboard GET if confirmed safe.

### 10.4 Add regression tests

Add tests proving:

```text
security auth User lookup does not eager-load exams/sessions/answers/logs
advanced user search does not eager-load user relationships
frontend bundle verification passes
monitoring module source keeps include_data_services=false by default
```

## 11. Minimal frontend/static fix plan

Source-only; do not deploy without separate approval.

```text
sync module sources to the currently committed safe bundles
run scripts/verify_frontend_bundles.sh until clean
add/keep tests that fail if admin monitoring module rebuild regresses restart safety
```

Important: do not blindly accept rebuild output from stale modules because it would regress the committed safer `static/js/admin/monitoring.js` bundle.

## 12. Production recommendation

No emergency rollback is recommended from this audit.

Current production should remain:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
```

Do not enable Phase 6 shadow/queue/hybrid while this admin API/auth eager-loading issue is unresolved.

Recommended next action:

```text
Prepare a source-only Phase 5.4 patch for:
1. lightweight auth/user ORM loading
2. frontend bundle module-source synchronization
3. regression tests
```

Deployment of that patch to VPS must be a separate controlled step with preflight, backup, checksum, and app-plane-only restart approval.
