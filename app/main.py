from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.services.subscription_service import ensure_plans_seeded
from app.core.database import AsyncSessionLocal

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed the default plan catalog (Free/Pro/Business) on startup if missing.
    async with AsyncSessionLocal() as db:
        await ensure_plans_seeded(db)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "MenuQR is a multi-tenant SaaS platform for restaurants to manage digital, "
        "QR-driven menus. This API powers the restaurant-owner dashboard as well as "
        "the unauthenticated public menu experience."
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Authentication", "description": "Registration, login, tokens, password reset, email verification."},
        {"name": "Restaurants", "description": "Restaurant CRUD and branding/settings."},
        {"name": "Branches", "description": "Physical branch/location management."},
        {"name": "Members", "description": "Tenant staff membership and role management."},
        {"name": "Invitations", "description": "Invite, accept, resend, and revoke staff invitations."},
        {"name": "Menus", "description": "Menu lifecycle: draft, publish, unpublish, archive."},
        {"name": "Categories", "description": "Menu category management and ordering."},
        {"name": "Menu Items", "description": "Menu item CRUD, ordering, availability, and modifiers."},
        {"name": "QR Codes", "description": "QR code generation and lifecycle."},
        {"name": "Subscriptions", "description": "Billing-agnostic plans and entitlement enforcement."},
        {"name": "Audit Logs", "description": "Tenant activity audit trail."},
        {"name": "Public Menu", "description": "Unauthenticated public menu endpoint for diners."},
        {"name": "Health", "description": "Liveness/readiness probes."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router)

try:
    app.mount("/media", StaticFiles(directory=settings.LOCAL_STORAGE_DIR), name="media")
except Exception:
    # Local storage directory may not exist yet in some environments (e.g. when
    # STORAGE_BACKEND=s3); that's fine, it's only used for local dev uploads.
    pass


@app.get("/health", tags=["Health"], summary="Basic liveness/health check")
async def health():
    return {"status": "ok"}


@app.get("/health/live", tags=["Health"], summary="Liveness probe")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"], summary="Readiness probe (verifies DB connectivity)")
async def health_ready():
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:  # pragma: no cover - depends on live infra
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content={"status": "not_ready", "database": str(exc)})
