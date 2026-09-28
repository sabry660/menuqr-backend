# Deployment Readiness Checklist

Legend: [x] file/config is in the repository. [ ] action YOU must perform in your environment.

## Local setup
- [x] `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `pytest.ini`, `Makefile`
- [x] `.env.example` (template) and `.env` (dev-only values)
- [x] `scripts/seed.py` (demo data), `README.md` (setup steps)
- [ ] Create venv, `pip install -r requirements-dev.txt`, start Postgres, `alembic upgrade head`, `python scripts/seed.py`, `uvicorn app.main:app --reload`
- [ ] Create the `menuqr_test` database and set `TEST_DATABASE_URL`, then `pytest`

## Database & migrations
- [x] `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_initial.py` (upgrade + downgrade)
- [x] Plans (Free/Pro/Business) auto-seeded on app startup
- [ ] Run `alembic upgrade head` against production DB before starting new app versions
- [ ] Run `alembic check` to confirm no model/migration drift
- [ ] Set up automated DB backups + a restore drill

## Environment / configuration
- [x] Every variable documented in `.env.example`
- [ ] Create `.env.production` (never commit): `APP_ENV=production`, strong `JWT_SECRET` (`openssl rand -hex 32`), real `DATABASE_URL`, `REDIS_URL`, explicit `CORS_ORIGINS`, `FRONTEND_URL`
- [ ] `EMAIL_PROVIDER=smtp` + `SMTP_*` (or swap `_smtp_send` for your provider SDK)
- [ ] `STORAGE_BACKEND=s3` + `S3_*` if using uploads
- [ ] Replace the dev `JWT_SECRET` and delete/replace the shipped `.env` before any real deployment

## Docker deployment
- [x] `Dockerfile` (non-root user, healthcheck), `.dockerignore`
- [x] `docker-compose.yml` (dev: app + postgres + redis, healthchecks, auto-migrate)
- [x] `docker-compose.prod.yml` (external DB/Redis, separate `migrate` job, 4 workers, `cleanup` job profile)
- [ ] `docker compose up --build` to verify locally
- [ ] Prod: `docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build`

## CI/CD
- [x] `.github/workflows/ci.yml`: lint, format check, mypy, migrations, drift check, tests, boot check, OpenAPI sync check
- [ ] Push repo to GitHub and confirm the workflow passes
- [ ] Add a deploy job (registry push + rollout) for your hosting target; store secrets in the CI secret store

## Documentation
- [x] `README.md`, `docs/` (architecture, auth, RBAC, multi-tenancy, invitations, menus, public menu, QR, subscriptions, storage, email, jobs, errors)
- [x] `openapi.yaml` (+ regenerate via `python scripts/export_openapi.py`; also writes `docs/openapi.json`)
- [x] `docs/AI_INTEGRATION_HANDOFF.md`

## Security / configuration
- [x] Central RBAC, server-side tenant isolation, hashed tokens, rate limiting, structured log redaction, explicit CORS list
- [x] `.gitignore`
- [ ] Terminate TLS in front of the app (load balancer / reverse proxy); app runs with `--proxy-headers`
- [ ] Confirm Redis is reachable in production (rate limiting falls back to per-process memory otherwise)
- [ ] Rotate any credential that was ever committed or shared

## Operations
- [x] `/health`, `/health/live`, `/health/ready`
- [x] `scripts/cleanup_tokens.py` (purge expired tokens, expire stale invitations)
- [ ] Schedule cleanup daily (`docker compose -f docker-compose.prod.yml run --rm cleanup`)
- [ ] Wire logs (JSON in production) to your log platform; add uptime + error monitoring
- [ ] Decide on a real task queue if email volume grows (see `docs/background_jobs.md`)
