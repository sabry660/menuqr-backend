"""Black-box test helpers: create resources via the real HTTP API rather than
touching the DB directly, so tests exercise the same code paths as real clients.
"""
from httpx import AsyncClient

from tests.conftest import auth_headers


async def create_restaurant(client: AsyncClient, token: str, tenant_id: str, name: str = "Test Restaurant") -> dict:
    resp = await client.post(
        "/api/v1/restaurants", json={"name": name}, headers=auth_headers(token, tenant_id)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_menu(client: AsyncClient, token: str, tenant_id: str, restaurant_id: str, name: str = "Menu") -> dict:
    resp = await client.post(
        f"/api/v1/restaurants/{restaurant_id}/menus", json={"name": name}, headers=auth_headers(token, tenant_id)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_category(client: AsyncClient, token: str, tenant_id: str, restaurant_id: str, menu_id: str, name: str = "Category") -> dict:
    resp = await client.post(
        f"/api/v1/restaurants/{restaurant_id}/menus/{menu_id}/categories",
        json={"name": name},
        headers=auth_headers(token, tenant_id),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_item(
    client: AsyncClient, token: str, tenant_id: str, restaurant_id: str, menu_id: str, category_id: str,
    name: str = "Item", price: str = "9.99",
) -> dict:
    resp = await client.post(
        f"/api/v1/restaurants/{restaurant_id}/menus/{menu_id}/categories/{category_id}/items",
        json={"name": name, "price": price},
        headers=auth_headers(token, tenant_id),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def full_menu_tree(client: AsyncClient, token: str, tenant_id: str) -> dict:
    """Creates restaurant -> menu -> category -> item and returns all four dicts."""
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    category = await create_category(client, token, tenant_id, restaurant["id"], menu["id"])
    item = await create_item(client, token, tenant_id, restaurant["id"], menu["id"], category["id"])
    return {"restaurant": restaurant, "menu": menu, "category": category, "item": item}
