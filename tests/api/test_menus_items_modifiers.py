import pytest

from tests.conftest import auth_headers
from tests.factories.helpers import create_category, create_item, create_menu, create_restaurant

pytestmark = pytest.mark.asyncio


async def test_menu_lifecycle_draft_to_published(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    assert menu["status"] == "draft"

    publish_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/publish", headers=auth_headers(token, tenant_id)
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["status"] == "published"

    unpublish_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/unpublish", headers=auth_headers(token, tenant_id)
    )
    assert unpublish_resp.json()["status"] == "draft"


async def test_category_create_and_reorder(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    cat_a = await create_category(client, token, tenant_id, restaurant["id"], menu["id"], "A")
    cat_b = await create_category(client, token, tenant_id, restaurant["id"], menu["id"], "B")

    reorder_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/categories/reorder",
        json={"ordered_ids": [cat_b["id"], cat_a["id"]]},
        headers=auth_headers(token, tenant_id),
    )
    assert reorder_resp.status_code == 200
    ordered = reorder_resp.json()
    assert ordered[0]["id"] == cat_b["id"]
    assert ordered[0]["position"] == 0


async def test_reorder_with_wrong_id_set_rejected(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    await create_category(client, token, tenant_id, restaurant["id"], menu["id"], "A")

    resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/categories/reorder",
        json={"ordered_ids": ["00000000-0000-0000-0000-000000000000"]},
        headers=auth_headers(token, tenant_id),
    )
    assert resp.status_code == 422


async def test_item_uses_decimal_price_not_float(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    category = await create_category(client, token, tenant_id, restaurant["id"], menu["id"])
    item = await create_item(client, token, tenant_id, restaurant["id"], menu["id"], category["id"], price="12.34")
    assert item["price"] == "12.34"  # serialized as a string, not a lossy float


async def test_item_price_must_be_positive(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    category = await create_category(client, token, tenant_id, restaurant["id"], menu["id"])
    resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/categories/{category['id']}/items",
        json={"name": "Free Item", "price": "0.00"},
        headers=auth_headers(token, tenant_id),
    )
    assert resp.status_code == 422


async def test_item_reorder(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    category = await create_category(client, token, tenant_id, restaurant["id"], menu["id"])
    item_a = await create_item(client, token, tenant_id, restaurant["id"], menu["id"], category["id"], "Item A")
    item_b = await create_item(client, token, tenant_id, restaurant["id"], menu["id"], category["id"], "Item B")

    resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/categories/{category['id']}/items/reorder",
        json={"ordered_ids": [item_b["id"], item_a["id"]]},
        headers=auth_headers(token, tenant_id),
    )
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == item_b["id"]


async def test_modifier_group_creation_with_options(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    category = await create_category(client, token, tenant_id, restaurant["id"], menu["id"])
    item = await create_item(client, token, tenant_id, restaurant["id"], menu["id"], category["id"])

    resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/categories/{category['id']}/items/{item['id']}/modifier-groups",
        json={
            "name": "Size",
            "is_required": True,
            "min_selections": 1,
            "max_selections": 1,
            "options": [{"name": "Small"}, {"name": "Large", "price_delta": "2.00"}],
        },
        headers=auth_headers(token, tenant_id),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["options"]) == 2


async def test_modifier_group_min_exceeds_max_rejected(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    category = await create_category(client, token, tenant_id, restaurant["id"], menu["id"])
    item = await create_item(client, token, tenant_id, restaurant["id"], menu["id"], category["id"])

    resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/categories/{category['id']}/items/{item['id']}/modifier-groups",
        json={"name": "Bad", "min_selections": 3, "max_selections": 1},
        headers=auth_headers(token, tenant_id),
    )
    print("DEBUG STATUS:", resp.status_code)
    print("DEBUG BODY:", resp.text)
    assert resp.status_code == 400


async def test_menu_item_plan_limit_enforced(client, register_and_login):
    """Free plan defaults to max_menu_items=30."""
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    menu = await create_menu(client, token, tenant_id, restaurant["id"])
    category = await create_category(client, token, tenant_id, restaurant["id"], menu["id"])

    for i in range(30):
        item_resp = await client.post(
            f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/categories/{category['id']}/items",
            json={"name": f"Item {i}", "price": "5.00"},
            headers=auth_headers(token, tenant_id),
        )
        assert item_resp.status_code == 201, item_resp.text

    over_limit = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/categories/{category['id']}/items",
        json={"name": "One Too Many", "price": "5.00"},
        headers=auth_headers(token, tenant_id),
    )
    assert over_limit.status_code == 402
