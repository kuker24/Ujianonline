# Ujianonline

Online examination platform: exam setup, question bank, session monitoring, and asynchronous grading.

This repository is the exam system that the portfolio also refers to as **SIAB1**. It is separate from [SIAB2 / abensi](https://github.com/kuker24/abensi), which handles school attendance.

## Why it exists

Schools need a way to run computer-based exams without treating the whole stack as a single admin page. This project keeps exam definitions, questions, student sessions, and grading as distinct pieces, with a FastAPI backend and a Flutter client.

## Core features

- Exam and session management
- Question bank
- Async grading / answer processing
- Session monitoring and alerts
- Safe Exam Browser (SEB) integration for locked-down desktop sittings
- Flutter / APK client for the student path
- Health, metrics, and operational docs for exam-day monitoring

## Architecture

```text
Flutter / APK client          Admin web
        │                          │
        └──────────┬───────────────┘
                   ▼
              FastAPI API
                   │
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
 PostgreSQL      Redis        Celery workers
                                 │
                                 ▼
                         grading / exports
```

Longer internal map: [`ARCHITECTURE.md`](ARCHITECTURE.md). Deployment notes: [`DEPLOYMENT.md`](DEPLOYMENT.md). Code tour: [`CODEBASE.md`](CODEBASE.md).

## Tech stack

- Python / FastAPI
- PostgreSQL + SQLAlchemy
- Redis + Celery
- Flutter client
- Docker Compose
- Prometheus / Grafana (ops path)
- Safe Exam Browser hooks

## Screenshots

No anonymous product screenshots are published in this repo yet. Until they are, treat the architecture and source as the proof layer.

## How to run (local)

This is a development sketch, not a production recipe. Generate your own secrets. Do not reuse example passwords.

```bash
cp .env.example .env
# fill SECRET_KEY, JWT_SECRET_KEY, and the SEB keys
docker compose -f docker-compose.production.yml up -d --build
```

See `DEPLOYMENT.md` and `.env.example` for the full variable list. Health is typically exposed as a `/health`-style endpoint once the API is up.

## Security considerations

- JWT auth and password hashing on the API
- Account lockout / brute-force controls
- SEB config and browser exam keys for locked sittings
- CSRF and security headers in the middleware stack
- Audit / activity logging

Do not publish real SEB keys, JWT secrets, Telegram tokens, or student exam data. The example env file is a template only.

## Project status

Active codebase on the default branch `review/sanitized-root-20260531-115153`. The branch name is historical (a sanitized review snapshot). Other branches explore a SIAB1 rebrand and UI work. There is no `main` branch yet.

I use this as a real exam-ops system, not a tutorial repo. Docs in `docs/` are operator notes; some are dated and Indonesian.

## Related

- Attendance / academic system: [SIAB2 (abensi)](https://github.com/kuker24/abensi)
- Portfolio: https://kuker24.github.io/portfolio/
