import pytest

from tests.conftest import auth_headers
from tests.factories.helpers import create_restaurant

pytestmark = pytest.mark.asyncio


async def test_missing_tenant_header_rejected(client, register_and_login):
    token, _tenant_id, _email = await register_and_login()
    resp = await client.get("/api/v1/restaurants", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422  # missing required header


async def test_tenant_header_for_tenant_user_does_not_belong_to_is_rejected(client, register_and_login):
    token_a, _tenant_a, _ = await register_and_login()
    _token_b, tenant_b, _ = await register_and_login()

    resp = await client.get("/api/v1/restaurants", headers=auth_headers(token_a, tenant_b))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_cross_tenant_get_restaurant_is_rejected(client, register_and_login):
    token_a, tenant_a, _ = await register_and_login()
    token_b, tenant_b, _ = await register_and_login()

    restaurant = await create_restaurant(client, token_a, tenant_a, "Tenant A Diner")

    # Tenant B user, correctly scoped to THEIR OWN tenant, tries to fetch Tenant A's restaurant ID.
    resp = await client.get(f"/api/v1/restaurants/{restaurant['id']}", headers=auth_headers(token_b, tenant_b))
    assert resp.status_code == 404  # not "403 forbidden" -- we don't confirm the resource exists at all


async def test_cross_tenant_patch_restaurant_is_rejected(client, register_and_login):
    token_a, tenant_a, _ = await register_and_login()
    token_b, tenant_b, _ = await register_and_login()
    restaurant = await create_restaurant(client, token_a, tenant_a, "Tenant A Diner")

    resp = await client.patch(
        f"/api/v1/restaurants/{restaurant['id']}", json={"name": "Hacked"}, headers=auth_headers(token_b, tenant_b)
    )
    assert resp.status_code == 404


async def test_cross_tenant_delete_restaurant_is_rejected(client, register_and_login):
    token_a, tenant_a, _ = await register_and_login()
    token_b, tenant_b, _ = await register_and_login()
    restaurant = await create_restaurant(client, token_a, tenant_a, "Tenant A Diner")

    resp = await client.delete(f"/api/v1/restaurants/{restaurant['id']}", headers=auth_headers(token_b, tenant_b))
    assert resp.status_code == 404


async def test_restaurant_list_is_scoped_to_tenant(client, register_and_login):
    token_a, tenant_a, _ = await register_and_login()
    token_b, tenant_b, _ = await register_and_login()

    await create_restaurant(client, token_a, tenant_a, "A's Place")
    await create_restaurant(client, token_b, tenant_b, "B's Place")

    resp_a = await client.get("/api/v1/restaurants", headers=auth_headers(token_a, tenant_a))
    names_a = [r["name"] for r in resp_a.json()["items"]]
    assert "A's Place" in names_a
    assert "B's Place" not in names_a


async def test_cross_tenant_branch_access_via_forged_restaurant_id_rejected(client, register_and_login):
    """Tenant B tries to reach Tenant A's branch by guessing branch_id even though
    the restaurant_id in the path also belongs to Tenant A -- both IDs must fail
    ownership since Tenant B has no membership in Tenant A."""
    token_a, tenant_a, _ = await register_and_login()
    token_b, tenant_b, _ = await register_and_login()

    restaurant = await create_restaurant(client, token_a, tenant_a)
    branch_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/branches",
        json={"name": "Main Branch"},
        headers=auth_headers(token_a, tenant_a),
    )
    assert branch_resp.status_code == 201
    branch = branch_resp.json()

    resp = await client.get(
        f"/api/v1/restaurants/{restaurant['id']}/branches/{branch['id']}",
        headers=auth_headers(token_b, tenant_b),
    )
    assert resp.status_code in (403, 404)
