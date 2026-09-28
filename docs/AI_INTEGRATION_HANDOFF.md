# After Receiving the AI Engineer's Code

Nothing in this repository integrates AI yet. This is the task list for when the AI code arrives.

## 1. First: get answers from the AI engineer
Do not start integrating until you have, in writing:
- [ ] What the AI does (inputs -> outputs) and which MenuQR features it serves (e.g. menu/item text, translation, image tagging, recommendations)
- [ ] Runtime shape: Python library, HTTP service, or hosted-model API calls
- [ ] Resource needs (CPU/GPU/RAM), cold-start time, typical and worst-case latency
- [ ] Which external providers/API keys it needs
- [ ] Whether it needs to read MenuQR data (which fields) or only receives data per request

## 2. Decide: inside this backend or a separate service
- [ ] **Separate service (default recommendation)** if it has heavy/different dependencies, needs GPU, is slow, or scales differently. Backend calls it over HTTP.
- [ ] **In-process** only if it is a light library/thin wrapper around a hosted API with no conflicting dependencies and fast responses.
- [ ] Record the decision in `docs/`.

## 3. Where the code goes
- Separate service: its own repo/folder (e.g. `ai-service/`) with its own Dockerfile; backend gets only a thin client.
- Backend-side glue (either option):
  - [ ] Client/adapter: `app/integrations/ai_client.py` (HTTP client, timeouts, retries, error mapping)
  - [ ] Business logic: `app/services/ai_service.py` (tenant checks, plan limits, audit logging)
  - [ ] Router: `app/api/v1/ai.py`, registered in `app/api/v1/router.py`
  - [ ] Schemas: `app/schemas/ai.py`
  - [ ] Long-running work: `app/jobs/` (needs a real queue; see `docs/background_jobs.md`)

## 4. API / integration layer needed
- [ ] Get the AI service's OpenAPI spec or a written contract: endpoints, request/response schemas, error codes, size limits
- [ ] Define MenuQR-facing endpoints (tenant-scoped, under `/api/v1/`) that the frontend calls; the frontend must never call the AI service directly
- [ ] For slow tasks: submit -> job id -> poll/status endpoint (not a long blocking request)
- [ ] Map AI errors/timeouts to the existing error format (`{"error": {code, message, details}}`)
- [ ] Update `openapi.yaml` (`python scripts/export_openapi.py`)

## 5. Authentication / authorization
- [ ] User -> backend: unchanged (Bearer JWT + `X-Tenant-ID`, RBAC via `require_permission`)
- [ ] Add new permission(s) (e.g. `ai.use`) in `app/permissions/definitions.py` and assign to roles
- [ ] Backend -> AI service: service-to-service credential (API key or short-lived signed token), sent from the backend only; never exposed to the frontend or users
- [ ] The AI service must not trust tenant/user IDs from callers on its own; the backend resolves the tenant, then passes only the data needed
- [ ] Keep the AI service on a private network (not publicly exposed)
- [ ] Never send passwords, tokens, or other tenants' data to the AI; never log prompts containing personal data without a decision on retention

## 6. Environment variables / keys (typical; confirm with the AI engineer)
- [ ] Backend: `AI_SERVICE_URL`, `AI_SERVICE_API_KEY`, `AI_REQUEST_TIMEOUT_SECONDS`, `AI_ENABLED`
- [ ] Add each to `app/core/config.py`, `.env.example`, `.env.production`, both compose files, README
- [ ] AI service: its own provider keys (e.g. model-provider key) live only in the AI service's environment
- [ ] Store all keys in your secret manager / CI secrets

## 7. Dependencies
- [ ] Separate service: nothing new in this backend beyond an HTTP client (`httpx` is already in `requirements.txt`)
- [ ] In-process: add the AI engineer's pinned packages to `requirements.txt`; check for version conflicts; rebuild the image
- [ ] Ask for a pinned `requirements.txt` (or lockfile) from the AI engineer either way

## 8. Docker / Compose changes
- [ ] Add an `ai` service to `docker-compose.yml` and `docker-compose.prod.yml` (image/build, env, healthcheck, private network, resource limits, GPU settings if needed)
- [ ] Add `depends_on` (service_healthy) from `app` to `ai` if AI is required at startup, or make AI failures non-fatal
- [ ] Set `AI_SERVICE_URL` to the compose service name (e.g. `http://ai:9000`)
- [ ] Add build/publish of the AI image to CI

## 9. Database changes
Only if the feature needs persistence; ask the AI engineer what must be stored.
- [ ] New models in `app/models/`, imported in `app/models/__init__.py`
- [ ] `alembic revision --autogenerate -m "add ai tables"`, review it, `alembic upgrade head`
- [ ] Likely candidates: job/request records (tenant_id, status, result), usage counters for plan limits, stored outputs
- [ ] Every new table carries `tenant_id` and is queried through the same ownership checks as existing resources
- [ ] Add plan entitlements (e.g. monthly AI requests) in `subscription_service.py`; add audit log actions

## 10. What the AI engineer must provide
- [ ] Source code + README (setup, run, config)
- [ ] Pinned dependencies and a working Dockerfile
- [ ] Complete list of env vars/keys and what each does
- [ ] API contract (OpenAPI or equivalent) with example requests/responses and error codes
- [ ] Model/provider names and versions, licenses, data-handling/retention notes
- [ ] Health endpoint(s) and expected startup time
- [ ] Performance limits (max input size, rate limits, timeouts)
- [ ] Tests and sample data so you can verify it independently
- [ ] Any DB schema it expects

## 11. Connecting Backend + AI + Frontend
- [ ] Run the AI service alone and confirm its health endpoint and a sample call
- [ ] Add the backend client/service/router and env vars; confirm backend -> AI call works with the service credential
- [ ] Verify tenant isolation: tenant A cannot trigger or read tenant B's AI results
- [ ] Verify RBAC: roles without `ai.use` get 403
- [ ] Verify failure behavior: AI down/slow -> clean error, rest of the API unaffected
- [ ] Regenerate `openapi.yaml`, hand it to the frontend developer
- [ ] Frontend calls only MenuQR endpoints; add loading/error/retry states for slow AI calls
- [ ] Update README/docs and `docs/DEPLOYMENT_CHECKLIST.md`

## 12. Final deployment steps after integration
- [ ] Add AI env vars to `.env.production`
- [ ] Run migrations (`alembic upgrade head`)
- [ ] Build/push backend and AI images
- [ ] Deploy AI service first, confirm healthy, then deploy backend
- [ ] Smoke test: health endpoints, login, one AI call end-to-end
- [ ] Set up monitoring, cost/usage alerts for provider spend, and rate limits on AI endpoints
- [ ] Have a rollback plan (disable via `AI_ENABLED=false`)
