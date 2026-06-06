# Phase 5.1 Direct Hardening and Phase 6 Shadow Readiness - 2026-06-06

## 1. Latest GitHub head reviewed

Branch: `review/sanitized-root-20260531-115153`

Reviewed base/head before work:

```text
298a46848deff03ff54b754b5498d7d8a8190321
docs: record VPS architecture readiness for phase 5 and 6
```

`base..head` had 0 new commits at start of this work. No forbidden artifacts or queue/hybrid activation were found before patching.

## 2. Files changed

Source/config:

- `.env.example`
- `app/config.py`
- `app/services/answer_sync_service.py`
- `app/services/answer_runtime_buffer.py`
- `app/tasks/answer_processor.py`
- `docker-compose.production.yml`
- `scripts/runtime_buffer_consistency_check.py`

Tests:

- `tests/test_answer_sync_service_routing.py`
- `tests/test_answer_runtime_buffer_shadow.py`
- `tests/test_answer_runtime_buffer_consistency.py`
- `tests/test_answer_runtime_buffer.py` (covered by validation; no source change)
- `tests/test_exam_write_integrity_guards.py`
- `tests/test_production_readiness_defaults.py`

## 3. Runtime behavior changed or not

Default production behavior remains direct safe-mode:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
```

No public endpoint contract changed. No DB schema changed. No migration was added. Final submit still reads/graduates persisted PostgreSQL state and does not depend on Redis shadow data.

Runtime behavior changes only when explicitly configured later:

- Shadow mirror helper exists but is default OFF.
- Shadow mirror stores only deterministic answer payload hashes, not raw answer text.
- Shadow mirror failures are best-effort and do not affect answer responses.
- Queue/hybrid/runtime buffer production routing remains OFF.

## 4. Production defaults confirmation

| Flag | Default after patch | Status |
|---|---:|---|
| `ANSWER_WRITE_MODE` | `direct` | OK |
| `ANSWER_QUEUE_ENABLED` | `false` | OK |
| `ANSWER_QUEUE_PERCENTAGE` | `0` | OK |
| `ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED` | `false` | OK |
| `ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE` | `0` | OK |
| `ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS` | `14400` | OK |
| `ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT` | `100` | OK |

These defaults were added to config/compose/example env and covered by tests.

## 5. Phase 5 hardening summary

Implemented small hardening in `AnswerSyncService`:

1. Added `_safe_update_session_answers_marker()` for Redis answer marker updates after durable DB work.
2. Single-answer marker update remains best-effort.
3. Batch autosave post-commit `update_session_answers()` is now best-effort.
4. Journal post-commit `update_session_answers()` is now best-effort.
5. Journal idempotency read failure now returns explicit `503 Retry-After: 1` instead of silently treating unknown event IDs as new.

Important distinction:

- Initial journal idempotency check remains required because silent failure could duplicate client event application.
- Post-commit marker write is best-effort because the DB write is already durable and retry behavior remains safe enough for direct mode.

## 6. Redis failure behavior summary

| Flow | Redis failure behavior after patch |
|---|---|
| `/submit-answer` after DB commit | marker/shadow failure is best-effort; response can still be `saved` |
| `/auto-save-batch` after DB commit | marker/shadow failure is best-effort; DB persistence remains successful |
| `/answer-journal/sync` initial idempotency read | explicit 503/retry; do not silently duplicate unknown events |
| `/answer-journal/sync` post-commit marker | best-effort; DB direct write already completed |
| Phase 6 shadow mirror | best-effort and default OFF |
| Final submit | no dependency on Redis shadow mirror |

## 7. Queue worker alignment status

`app/tasks/answer_processor.py` remains a legacy queue worker. This patch does not enable it.

A production guard comment and test were added documenting that queue/hybrid must stay disabled until the worker is proven to match `AnswerSyncService` semantics:

- no-op update skip
- metadata merge
- statement_answers merge
- active-session status rules
- final-submit forced flush compatibility
- deadletter/age metrics
- rollback behavior

## 8. Phase 6 shadow readiness summary

Added default-off config:

```text
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_TTL_SECONDS=14400
ANSWER_RUNTIME_BUFFER_CONSISTENCY_SAMPLE_LIMIT=100
```

Added helper functions in `answer_runtime_buffer.py`:

- `shadow_session_answers_key(session_id)`
- `shadow_session_meta_key(session_id)`
- `answer_payload_hash(payload)`
- `is_runtime_answer_buffer_shadow_enabled()`
- `is_runtime_answer_buffer_shadow_enabled_for_session(...)`
- `record_runtime_answer_shadow(...)`

Shadow semantics:

- PostgreSQL direct write remains source of truth.
- Redis stores hash-only mirror data.
- Redis mirror failure returns 0 and logs debug only.
- Final submit does not read shadow mirror.
- Queue/hybrid are not enabled.

## 9. Consistency checker summary

Added read-only script:

```text
scripts/runtime_buffer_consistency_check.py
```

Purpose:

- sample submitted/in-progress/completed sessions;
- compare PostgreSQL latest answer payload hashes vs Redis shadow hashes when shadow keys exist;
- output JSON summary only;
- do not print raw answers, student PII, tokens, or Redis values.

Required summary fields:

```json
{
  "checked_sessions": 0,
  "checked_answers": 0,
  "missing_in_redis": 0,
  "extra_in_redis": 0,
  "payload_hash_mismatch": 0,
  "stale_runtime_sessions": 0,
  "redis_errors": 0
}
```

The checker is read-only and was validated with `--help` plus `py_compile`.

## 10. Redis `allkeys-lru` warning

Audit found live Redis `maxmemory-policy=allkeys-lru`. This remains unsafe for answer buffer as source-of-truth because answer keys could be evicted.

Decision remains:

- Shadow mode may be designed because DB remains source of truth.
- Production buffer/canary requires `noeviction` or isolated Redis instance/db with reserved memory, AOF verified, no evictions/rejections, deadletter/age metrics, and final-submit forced flush tests.
- This patch does not change Redis config.

## 11. Tests run and results

Validation used dummy non-secret local env values because the safe worktree has no `.env`.

```bash
git diff --check
python -m compileall app
pytest tests/test_production_readiness_defaults.py -q
pytest tests/test_answer_sync_service_routing.py -q
pytest tests/test_answer_runtime_buffer.py -q
pytest tests/test_final_submit_service.py -q
pytest tests/test_exam_write_integrity_guards.py -q
pytest tests/test_answer_runtime_buffer_shadow.py -q
pytest tests/test_answer_runtime_buffer_consistency.py -q
python -m py_compile scripts/runtime_buffer_consistency_check.py
python scripts/runtime_buffer_consistency_check.py --help
```

Results:

- `test_production_readiness_defaults.py`: 7 passed
- `test_answer_sync_service_routing.py`: 25 passed
- `test_answer_runtime_buffer.py`: 12 passed
- `test_final_submit_service.py`: 6 passed
- `test_exam_write_integrity_guards.py`: 12 passed
- `test_answer_runtime_buffer_shadow.py`: 5 passed
- `test_answer_runtime_buffer_consistency.py`: 3 passed
- `compileall`, `py_compile`, `--help`, and `git diff --check`: PASS

## 12. Forbidden artifact check

Checked `git status --short` against forbidden patterns:

- APK/AAB: none
- keystore/JKS/key.properties/local.properties: none
- `.env`: none
- DB dump/sql/sqlite/db: none
- backup/session CSV/summary JSON: none
- raw token/session/PII artifacts: none

## 13. Production action

| Action | Status |
|---|---:|
| Deploy to VPS | No |
| Restart VPS/container | No |
| Migration/schema change | No |
| Production load-test | No |
| APK build/change | No |
| Queue/hybrid activation | No |
| Runtime buffer production dependency | No |

## 14. Rollback

If this source patch is not desired, rollback is a normal Git revert. Runtime defaults remain unchanged, so production can continue with:

```text
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
ANSWER_RUNTIME_BUFFER_SHADOW_ENABLED=false
ANSWER_RUNTIME_BUFFER_SHADOW_PERCENTAGE=0
```

No data migration rollback is needed.

## 15. Final decision

| Decision | Result |
|---|---|
| Phase 5 direct consolidation improved | YES |
| Phase 6 production ready | NO |
| Phase 6 shadow default-off ready | PARTIAL/YES for source-only guarded readiness |
| Queue/hybrid production | NO |
| Redis as answer source-of-truth | NO |
| Safe to review as source-only PR | YES |

## 16. Remaining blockers before Phase 6 production

1. Redis eviction policy must not be `allkeys-lru` for source-of-truth answer keys.
2. Dedicated answer flush worker/concurrency and queue age/deadletter metrics are required.
3. Final-submit forced flush needs tests and staging proof.
4. Shadow consistency checker must show 0 mismatch across staged runs.
5. Direct rollback runbook must be tested.
6. Operator approval is required before any canary.
