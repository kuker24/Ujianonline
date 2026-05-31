# AGENTS.md
Guidance for coding agents in this repository.
This file replaces stale notes from older AI runs and keeps only active project guidance.

## Project Overview
- Stack: FastAPI, SQLAlchemy async, PostgreSQL, Redis, Celery, Nginx.
- Main entrypoint: `app/main.py`.
- Main runtime orchestration: `docker-compose.production.yml`.
- High-impact modules: `app/config.py`, `app/database.py`, `app/api/exams.py`.

## Rule Files Check
- Cursor rules: not found (`.cursor/rules/`, `.cursorrules`).
- Copilot rules: not found (`.github/copilot-instructions.md`).
- If these files are added later, treat them as additional constraints.

## Build, Run, Lint, and Test Commands
### 1) Local setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```
### 2) Run API locally (without Docker)
```bash
python -m app.main
```
Alternative:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
### 3) Run full stack with Docker (recommended)
```bash
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs -f api
```
### 4) Rebuild services
```bash
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml build --no-cache
docker compose -f docker-compose.production.yml up -d
```
### 5) Lint and static checks
There is no pinned linter config file (`ruff.toml`, `mypy.ini`, `pyproject.toml`) in repo root.
Use these safe checks unless project tooling is added:
```bash
python -m compileall app
python scripts/check_security.py
```
Optional (if installed by your environment):
```bash
ruff check app scripts
mypy app
```
### 6) Test commands
- `pytest` exists in dependencies, but there is currently no committed `tests/` directory.
- When tests are added, use these commands:
Run all tests:
```bash
pytest -q
```
Run a single test file:
```bash
pytest tests/path/test_file.py -q
```
Run a single test function:
```bash
pytest tests/path/test_file.py::test_name -q
```
Run one class method test:
```bash
pytest tests/path/test_file.py::TestClass::test_name -q
```
### 7) Smoke/system checks
```bash
python scripts/system_check.py
```

## Code Style and Conventions
### Python and formatting
- Target Python 3.11 semantics (aligned with `docker/Dockerfile.production`).
- 4-space indentation, clear naming, and readable lines (prefer <= 100 chars).
- Keep endpoint functions slim; move heavy logic to helpers/services.
- Remove dead code and unused comments from prior edits.

### Imports
- Order imports: standard library, third-party, local `app.*` modules.
- Avoid unused imports.
- Use local/function imports only when needed (cycle breaks or optional heavy deps).

### Typing and schema usage
- Add type hints for public functions and non-trivial returns.
- Use `AsyncSession` for DB dependency signatures.
- Use Pydantic schemas for request/response payloads instead of untyped dicts.
- Keep field constraints in schema definitions (`Field(...)`, pattern/min/max).

### Naming
- `snake_case`: variables, functions, modules.
- `PascalCase`: classes, Pydantic/ORM models.
- `UPPER_SNAKE_CASE`: constants.
- Keep API route naming consistent with existing `/api/...` patterns.

### Database access and transactions
- Use `get_db_write()` for INSERT/UPDATE/DELETE.
- Use `get_db_read()` for SELECT.
- Keep SQLAlchemy async style (`select(...)`, `await db.execute(...)`, etc.).
- Do not bypass dependency-managed transaction/rollback behavior without a strong reason.

### Error handling and logging
- Use `HTTPException` with accurate status codes and user-safe messages.
- Log unexpected errors with context (`logger.error(..., exc_info=True)`).
- Do not leak internals, secrets, or stack traces in API responses.
- Prefer explicit 4xx errors for validation/auth/permission/not-found paths.

### Security-sensitive code
- Preserve SEB/SXB enforcement and validation flow.
- Preserve sanitization, rate limiting, account lockout, CAPTCHA, and audit logging behavior.
- JWT token expiry is intentionally longer (120 minutes) for exam sessions.

## Runtime Gotchas
1. HTTPS redirect middleware is intentionally disabled for Cloudflare SSL termination.
2. `redirect_slashes=False` is intentional to avoid 307 body-loss issues.
3. Middleware order is critical and execution is reverse of add order.
4. Keep Redis/Celery wiring consistent with scheduler/task configuration.

## Middleware Add Order (`app/main.py`)
1. `CORSMiddleware`
2. `SecurityHeadersMiddleware`
3. `RateLimitMiddleware` (unless `DISABLE_RATE_LIMIT=true`)
4. `SXBEnforcerMiddleware`
5. `LoggingMiddleware`
6. `PerformanceMonitoringMiddleware`

## Environment and Config Rules
- Central settings: `app/config.py` from `.env`.
- `DEBUG=true` only for development (enables docs routes).
- `DISABLE_RATE_LIMIT=true` is for development only.
- Telegram alerts require `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_IDS`.

## Agent Working Rules for This Repo
- Prefer small, surgical changes over broad rewrites.
- Validate edits with runnable checks (compile, smoke test, or pytest if tests exist).
- Do not delete project tooling/infrastructure folders unless explicitly requested.
- Keep this file updated if build/test/style practices change.
