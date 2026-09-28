import pytest

from tests.conftest import auth_headers
from tests.factories.helpers import create_restaurant

pytestmark = pytest.mark.asyncio


async def test_create_restaurant_generates_unique_slug(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    r1 = await create_restaurant(client, token, tenant_id, "Joe's Diner")
    r2 = await create_restaurant(client, token, tenant_id, "Joe's Diner")
    assert r1["slug"] != r2["slug"]
    assert r1["slug"].startswith("joes-diner")


async def test_list_restaurants_paginated(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    for i in range(3):
        await create_restaurant(client, token, tenant_id, f"Place {i}")
    resp = await client.get("/api/v1/restaurants?page=1&page_size=2", headers=auth_headers(token, tenant_id))
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["pagination"]["total_items"] == 3
    assert body["pagination"]["total_pages"] == 2


async def test_update_restaurant(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    resp = await client.patch(
        f"/api/v1/restaurants/{restaurant['id']}", json={"description": "Updated desc"}, headers=auth_headers(token, tenant_id)
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated desc"


async def test_archive_restaurant_removes_from_list(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    resp = await client.delete(f"/api/v1/restaurants/{restaurant['id']}", headers=auth_headers(token, tenant_id))
    assert resp.status_code == 204

    list_resp = await client.get("/api/v1/restaurants", headers=auth_headers(token, tenant_id))
    ids = [r["id"] for r in list_resp.json()["items"]]
    assert restaurant["id"] not in ids


async def test_get_nonexistent_restaurant_404(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    resp = await client.get("/api/v1/restaurants/00000000-0000-0000-0000-000000000000", headers=auth_headers(token, tenant_id))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_create_and_list_branches(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)

    resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/branches",
        json={"name": "Main Street", "address": "1 Main St"},
        headers=auth_headers(token, tenant_id),
    )
    assert resp.status_code == 201
    branch = resp.json()
    assert branch["status"] == "active"

    list_resp = await client.get(f"/api/v1/restaurants/{restaurant['id']}/branches", headers=auth_headers(token, tenant_id))
    assert list_resp.json()["pagination"]["total_items"] == 1


async def test_branch_plan_limit_enforced(client, register_and_login):
    """Free plan defaults to max_branches=1; the second branch must be rejected."""
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)

    first = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/branches", json={"name": "Branch 1"}, headers=auth_headers(token, tenant_id)
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/branches", json={"name": "Branch 2"}, headers=auth_headers(token, tenant_id)
    )
    assert second.status_code == 402
    assert second.json()["error"]["code"] == "PLAN_LIMIT_EXCEEDED"


async def test_update_and_delete_branch(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    branch_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/branches", json={"name": "Branch A"}, headers=auth_headers(token, tenant_id)
    )
    branch = branch_resp.json()

    update_resp = await client.patch(
        f"/api/v1/restaurants/{restaurant['id']}/branches/{branch['id']}",
        json={"name": "Branch A Renamed"},
        headers=auth_headers(token, tenant_id),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Branch A Renamed"

    delete_resp = await client.delete(
        f"/api/v1/restaurants/{restaurant['id']}/branches/{branch['id']}", headers=auth_headers(token, tenant_id)
    )
    assert delete_resp.status_code == 204

    get_resp = await client.get(
        f"/api/v1/restaurants/{restaurant['id']}/branches/{branch['id']}", headers=auth_headers(token, tenant_id)
    )
    assert get_resp.json()["status"] == "archived"
