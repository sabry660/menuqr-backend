import pytest

from tests.conftest import auth_headers
from tests.factories.helpers import create_category, create_item, create_menu, create_restaurant

pytestmark = pytest.mark.asyncio


async def test_public_menu_requires_no_auth(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id, "Public Test Diner")
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    category = await create_category(client, token, tenant_id, restaurant["id"], menu["id"])
    await create_item(client, token, tenant_id, restaurant["id"], menu["id"], category["id"], "Public Item")
    await client.post(f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/publish", headers=auth_headers(token, tenant_id))

    resp = await client.get(f"/api/v1/public/{restaurant['slug']}/menu")
    assert resp.status_code == 200
    body = resp.json()
    assert body["restaurant_name"] == "Public Test Diner"
    assert body["menus"][0]["categories"][0]["items"][0]["name"] == "Public Item"


async def test_public_menu_hides_draft_menus(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    await create_menu(client, token, tenant_id, restaurant["id"])  # left as draft, never published

    resp = await client.get(f"/api/v1/public/{restaurant['slug']}/menu")
    assert resp.status_code == 200
    assert resp.json()["menus"] == []


async def test_public_menu_hides_archived_and_invisible_items(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    category = await create_category(client, token, tenant_id, restaurant["id"], menu["id"])
    visible_item = await create_item(client, token, tenant_id, restaurant["id"], menu["id"], category["id"], "Visible")
    hidden_item = await create_item(client, token, tenant_id, restaurant["id"], menu["id"], category["id"], "Hidden")

    await client.patch(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/categories/{category['id']}/items/{hidden_item['id']}",
        json={"is_visible": False},
        headers=auth_headers(token, tenant_id),
    )
    await client.post(f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/publish", headers=auth_headers(token, tenant_id))

    resp = await client.get(f"/api/v1/public/{restaurant['slug']}/menu")
    item_names = [i["name"] for i in resp.json()["menus"][0]["categories"][0]["items"]]
    assert "Visible" in item_names
    assert "Hidden" not in item_names


async def test_public_menu_never_leaks_internal_fields(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    await client.post(f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/publish", headers=auth_headers(token, tenant_id))

    await client.patch(
        f"/api/v1/restaurants/{restaurant['id']}/settings",
        json={"internal_notes": "SECRET SUPPLIER PRICING - DO NOT LEAK"},
        headers=auth_headers(token, tenant_id),
    )

    resp = await client.get(f"/api/v1/public/{restaurant['slug']}/menu")
    raw_text = resp.text
    assert "SECRET SUPPLIER PRICING" not in raw_text
    assert "tenant_id" not in raw_text
    assert "internal_notes" not in raw_text


async def test_public_menu_unknown_restaurant_404(client):
    resp = await client.get("/api/v1/public/does-not-exist/menu")
    assert resp.status_code == 404


async def test_public_menu_hides_archived_restaurant(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    await client.delete(f"/api/v1/restaurants/{restaurant['id']}", headers=auth_headers(token, tenant_id))

    resp = await client.get(f"/api/v1/public/{restaurant['slug']}/menu")
    assert resp.status_code == 404
