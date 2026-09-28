# MenuQR Backend

MenuQR is a multi-tenant SaaS backend for restaurants to manage digital,
QR-driven menus. This repository is the complete backend API: authentication,
multi-tenant organizations, RBAC, restaurants/branches, menus/categories/items/
modifiers, QR codes, staff invitations, subscriptions/entitlements, audit
logging, and a public unauthenticated menu endpoint — built with FastAPI,
PostgreSQL, and SQLAlchemy 2.x (async).

> **Status**: implementation-complete. Runtime verification (installing
> dependencies, running Postgres/Redis, running the migration, running the test
> suite, starting the server) has **not** been executed in the environment this
> was built in, because that environment has no network access and no
> Postgres/Redis available. See "Verifying this repository" below for the exact
> commands to run in your own environment, and the final report at the end of
> this conversation for what is and isn't verified.

---

## 1. Stack

- Python 3.12+
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2.x (async, `psycopg` v3 driver)
- Alembic
- Pydantic v2
- JWT auth (python-jose) + bcrypt (passlib)
- Redis (rate limiting; swappable/optional)
- pytest + pytest-asyncio + httpx (ASGI transport)
- Docker / Docker Compose
- Ruff, Black, mypy

## 2. Architecture

```
app/
  main.py                 FastAPI app, CORS, exception handlers, health checks
  core/                    config, database session, security (JWT/bcrypt), exceptions, logging
  api/
    deps.py                current-user + tenant-context dependencies (IDOR choke point)
    v1/                     one router module per resource, registered in router.py
  models/                  SQLAlchemy ORM models (one file per domain area) + enums
  schemas/                 Pydantic request/response models
  services/                business logic + tenant-ownership enforcement (the "real" layer)
  permissions/             centralized RBAC: permission catalog + role matrix + FastAPI dependency
  middleware/              rate limiting
  integrations/            storage (local/S3) abstraction
  jobs/                     background-job abstraction (see docs/background_jobs.md)
alembic/                   migrations
tests/                     pytest suite (api/, security/, unit/, factories/)
scripts/seed.py            development seed data
docs/                       architecture & flow documentation
```

Business logic lives in `app/services/*`, never in route handlers. Every
service function that reads/writes a tenant-scoped resource re-derives
ownership from the database (joining up to `tenant_id`) rather than trusting a
client-supplied ID — see `docs/multi_tenancy.md`.

## 3. Requirements

- Python 3.12+
- PostgreSQL 16+ (local or Docker)
- Redis (optional in dev — rate limiting silently falls back to an in-memory
  limiter if Redis is unreachable; required for a correct multi-instance
  production deployment)
- Docker + Docker Compose (optional, but the fastest way to get all of this running)

## 4. Installation (local, without Docker)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# edit .env: at minimum set a real JWT_SECRET and DATABASE_URL
```

## 5. Environment

Copy `.env.example` to `.env` and fill in real values. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+psycopg://...`) |
| `JWT_SECRET` | Signing secret for access/refresh tokens — **must** be a strong random value in production (`openssl rand -hex 32`) |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |
| `REDIS_URL` | Used for rate limiting |
| `EMAIL_PROVIDER` | `console` (dev, prints to stdout) or `smtp` |
| `STORAGE_BACKEND` | `local` or `s3` |

Full list documented inline in `.env.example`.

## 6. Database & migrations

Start Postgres (Docker):

```bash
docker compose up -d postgres
```

Run migrations from an empty database:

```bash
alembic upgrade head
```

This applies `alembic/versions/0001_initial.py`, which creates every table,
enum type, index, foreign key (with correct `ondelete` behavior), and unique
constraint described in `app/models/`. To create a new migration after
changing models:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## 7. Seed data

```bash
python scripts/seed.py
```

Creates a demo tenant ("Demo Bistro Group") with 5 staff accounts (one per
role), a restaurant with two branches, a published menu with categories,
items, and modifiers, and two QR codes. **Development credentials only** —
printed to stdout when the script runs, never hardcoded as "real" secrets.
See "Seed / demo credentials" in the final report for the exact values.

## 8. Running the API

```bash
uvicorn app.main:app --reload
```

API base URL: `http://localhost:8000/api/v1`

## 9. Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts `postgres`, `redis`, and `app` (which runs `alembic upgrade head`
automatically before starting `uvicorn`), all with health checks. The API is
then available at `http://localhost:8000`.

## 10. Tests

Tests require a real PostgreSQL instance (several columns use
Postgres-specific types — `INET`, `JSONB`, native `ENUM` — so SQLite cannot run
this schema):

```bash
docker compose up -d postgres
createdb -h localhost -U menuqr menuqr_test   # or: docker exec -it <container> createdb -U menuqr menuqr_test
export TEST_DATABASE_URL=postgresql+psycopg://menuqr:menuqr@localhost:5432/menuqr_test
pytest --cov=app --cov-report=term-missing
```

Each test runs inside a rolled-back transaction (see `tests/conftest.py`), so
the suite is deterministic and order-independent, and tests never send real
email (the email service is monkeypatched to capture messages instead).

## 11. Swagger / OpenAPI

Once the server is running:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Raw schema: `http://localhost:8000/openapi.json`

Every endpoint has a `summary`, is grouped under a tag, and documents its
request/response models via the Pydantic schemas in `app/schemas/`.

## 12. Authentication

JWT access tokens (15 min default) + rotating, persisted refresh tokens (30
day default). Full flow, including reuse detection, documented in
`docs/authentication.md`. Endpoints:

```
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
POST /api/v1/auth/verify-email
POST /api/v1/auth/resend-verification
```

## 13. RBAC

Five roles (Owner, Admin, Manager, Editor, Staff) mapped to a centralized
permission catalog in `app/permissions/definitions.py`. Every protected
endpoint depends on `require_permission(Perm.X)` — there are no scattered
`if role == "admin"` checks. Details and the full permission matrix are in
`docs/rbac.md`.

## 14. Multi-tenancy

The active tenant is resolved server-side from an `X-Tenant-ID` header **and**
the caller's `Membership` row — never trusted from a body/path/query
parameter alone. Every service function re-derives ownership by joining up to
`tenant_id` before returning/mutating anything. Full explanation in
`docs/multi_tenancy.md`.

## 15. Project structure

See section 2 above and `docs/architecture.md` for a deeper walkthrough
(including why settings/branding live under `restaurants.py` rather than a
separate router, and why modifiers are nested under menu items rather than
given their own top-level resource).

## 16. Production considerations

- Set `APP_ENV=production`, a strong random `JWT_SECRET`, and explicit
  `CORS_ORIGINS` (never a wildcard with credentials).
- Point `REDIS_URL` at a real Redis instance — the in-memory rate-limit
  fallback is per-process and not correct across multiple app instances.
- Set `STORAGE_BACKEND=s3` and the `S3_*` variables for uploaded assets
  (logos/covers) instead of the local filesystem.
- Set `EMAIL_PROVIDER=smtp` and the `SMTP_*` variables (or swap
  `app/services/email_service.py`'s `_smtp_send` for a provider SDK, e.g.
  SES/SendGrid, following the same `EmailMessage` interface).
- Run `alembic upgrade head` as a release step before starting new app
  instances (the Docker Compose `app` service already does this).
- `GET /health/ready` checks DB connectivity and is what your orchestrator's
  readiness probe should hit; `/health/live` is a pure liveness check.

## 17. What was consciously simplified

Documented explicitly rather than hidden:

- **Rate limiting** falls back to an in-memory counter if Redis is
  unreachable. Fine for local dev; for correct multi-instance production
  behavior, Redis must be reachable.
- **Background jobs** (`app/jobs/`) — invitation/verification/reset emails are
  currently sent inline (`await`ed directly in the request) via the email
  abstraction rather than dispatched to a queue. The interface is already
  isolated behind `app/services/email_service.py`, so swapping to a real task
  queue (Celery/RQ/arq) means wrapping those three call sites, not
  restructuring the domain logic. See `docs/background_jobs.md`.
- **Billing** is intentionally provider-agnostic (`app/services/subscription_service.py`)
  with `Subscription.provider`/`provider_ref` columns ready for a real
  processor; no Stripe integration is wired up, per the spec ("do not tightly
  couple to Stripe").
- **Restaurant groups**: `Tenant` and `Restaurant` are modeled as a 1-tenant-to-
  many-restaurants relationship (a restaurant group), but every router in this
  build operates against one restaurant at a time.

## 18. Deployment & handoff files

- `docs/DEPLOYMENT_CHECKLIST.md` — everything needed for local, Docker, production, CI/CD
- `docs/AI_INTEGRATION_HANDOFF.md` — what to do when the separate AI engineer delivers code
- `openapi.yaml` — API spec; regenerate with `make openapi` (`python scripts/export_openapi.py`)
- `docker-compose.prod.yml` — production overlay; `scripts/cleanup_tokens.py` — scheduled cleanup
