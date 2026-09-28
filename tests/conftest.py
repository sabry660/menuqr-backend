"""Shared pytest fixtures.

IMPORTANT: Several models use PostgreSQL-specific types (INET, JSONB, native
ENUM), so this test suite requires a real PostgreSQL instance -- SQLite cannot
run these migrations. Point TEST_DATABASE_URL at a disposable Postgres database,
e.g. the `postgres` service in docker-compose.yml:

    docker compose up -d postgres
    export TEST_DATABASE_URL=postgresql+psycopg://menuqr:menuqr@localhost:5432/menuqr_test
    pytest

Each test runs inside an outer transaction that is rolled back afterwards, so
tests never see each other's data and never depend on execution order.
"""
import asyncio
import os
import uuid
from decimal import Decimal
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("EMAIL_PROVIDER", "console")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://menuqr:menuqr@localhost:5432/menuqr_test"),
)

from app.core.database import Base, get_db  # noqa: E402
from app.core.config import settings  # noqa: E402
import app.models  # noqa: E402,F401
from app.main import app  # noqa: E402
from app.services import email_service  # noqa: E402
from app.services.subscription_service import ensure_plans_seeded  # noqa: E402

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await engine.connect()
    trans = await connection.begin()
    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    session = session_factory()

    await ensure_plans_seeded(session)

    yield session

    await session.close()
    await trans.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # Never send real emails in tests; capture them instead so tests can assert on
    # verification/invitation/reset tokens being "sent" without hitting the network.
    sent_emails: list[email_service.EmailMessage] = []

    async def _fake_send(message: email_service.EmailMessage) -> None:
        sent_emails.append(message)

    email_service.send = _fake_send

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.sent_emails = sent_emails  # type: ignore[attr-defined]
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def register_and_login(client: AsyncClient):
    """Returns an async helper: await register_and_login() -> (access_token, tenant_id, user_email)."""

    async def _do(email: str | None = None, tenant_name: str | None = None):
        email = email or f"user_{uuid.uuid4().hex[:10]}@example.com"
        tenant_name = tenant_name or f"Tenant {uuid.uuid4().hex[:6]}"
        payload = {
            "email": email,
            "password": "SuperSecret123",
            "full_name": "Test User",
            "tenant_name": tenant_name,
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201, resp.text

        login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "SuperSecret123"})
        assert login_resp.status_code == 200, login_resp.text
        tokens = login_resp.json()

        me_resp = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        assert me_resp.status_code == 200
        tenant_id = me_resp.json()["memberships"][0]["tenant_id"]

        return tokens["access_token"], tenant_id, email

    return _do


def auth_headers(access_token: str, tenant_id: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "X-Tenant-ID": tenant_id}
