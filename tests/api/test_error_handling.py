import pytest

from tests.conftest import auth_headers
from tests.factories.helpers import create_restaurant

pytestmark = pytest.mark.asyncio


async def test_validation_error_shape(client):
    resp = await client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "x", "full_name": "", "tenant_name": ""})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "errors" in body["error"]["details"]


async def test_not_found_error_shape(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    resp = await client.get("/api/v1/restaurants/00000000-0000-0000-0000-000000000000", headers=auth_headers(token, tenant_id))
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "message" in body["error"]


async def test_malformed_uuid_in_path_returns_422(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    resp = await client.get("/api/v1/restaurants/not-a-uuid", headers=auth_headers(token, tenant_id))
    assert resp.status_code == 422


async def test_protected_endpoint_without_token_401(client):
    resp = await client.get("/api/v1/restaurants", headers={"X-Tenant-ID": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_FAILED"


async def test_protected_endpoint_with_garbage_token_401(client):
    resp = await client.get(
        "/api/v1/restaurants",
        headers={"Authorization": "Bearer not.a.valid.jwt", "X-Tenant-ID": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 401


async def test_stack_trace_never_leaked(client, register_and_login):
    """Even for unexpected shapes, the response must never look like a raw traceback."""
    token, tenant_id, _ = await register_and_login()
    resp = await client.patch(
        f"/api/v1/restaurants/00000000-0000-0000-0000-000000000000",
        json={"currency": "US"},  # too short - triggers validation, not a crash, but exercise the path
        headers=auth_headers(token, tenant_id),
    )
    assert resp.status_code in (404, 422)
    assert "Traceback" not in resp.text
    assert "File \"" not in resp.text


async def test_health_endpoints(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    resp_live = await client.get("/health/live")
    assert resp_live.status_code == 200


async def test_password_never_returned_anywhere(client, register_and_login):
    token, tenant_id, email = await register_and_login()
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    raw = resp.text
    assert "hashed_password" not in raw
    assert "SuperSecret123" not in raw


async def test_pagination_bounds_validated(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    resp = await client.get("/api/v1/restaurants?page=0", headers=auth_headers(token, tenant_id))
    assert resp.status_code == 422

    resp2 = await client.get("/api/v1/restaurants?page_size=1000", headers=auth_headers(token, tenant_id))
    assert resp2.status_code == 422
