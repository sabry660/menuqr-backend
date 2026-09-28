import pytest

from tests.conftest import auth_headers
from tests.factories.helpers import create_restaurant

pytestmark = pytest.mark.asyncio


async def test_qr_code_create_list_deactivate(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)

    create_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/qr-codes", json={"label": "Table 1"}, headers=auth_headers(token, tenant_id)
    )
    assert create_resp.status_code == 201
    qr = create_resp.json()
    assert qr["status"] == "active"
    assert restaurant["slug"] in qr["target_url"]

    list_resp = await client.get(f"/api/v1/restaurants/{restaurant['id']}/qr-codes", headers=auth_headers(token, tenant_id))
    assert list_resp.json()["pagination"]["total_items"] == 1

    deactivate_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/qr-codes/{qr['id']}/deactivate", headers=auth_headers(token, tenant_id)
    )
    assert deactivate_resp.json()["status"] == "inactive"


async def test_qr_code_invalid_branch_rejected(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/qr-codes",
        json={"label": "Bad", "branch_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers(token, tenant_id),
    )
    assert resp.status_code == 422


async def test_qr_cross_tenant_access_rejected(client, register_and_login):
    token_a, tenant_a, _ = await register_and_login()
    token_b, tenant_b, _ = await register_and_login()
    restaurant = await create_restaurant(client, token_a, tenant_a)
    qr_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/qr-codes", json={"label": "T1"}, headers=auth_headers(token_a, tenant_a)
    )
    qr_id = qr_resp.json()["id"]

    resp = await client.get(f"/api/v1/restaurants/{restaurant['id']}/qr-codes/{qr_id}", headers=auth_headers(token_b, tenant_b))
    assert resp.status_code in (403, 404)


async def test_settings_read_and_update(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)

    get_resp = await client.get(f"/api/v1/restaurants/{restaurant['id']}/settings", headers=auth_headers(token, tenant_id))
    assert get_resp.status_code == 200

    update_resp = await client.patch(
        f"/api/v1/restaurants/{restaurant['id']}/settings",
        json={"theme_color": "#112233", "social_links": {"instagram": "https://instagram.com/demo"}},
        headers=auth_headers(token, tenant_id),
    )
    assert update_resp.status_code == 200
    body = update_resp.json()
    assert body["theme_color"] == "#112233"
    assert body["social_links"]["instagram"] == "https://instagram.com/demo"


async def test_staff_cannot_update_settings(client, register_and_login):
    from tests.security.test_rbac_privilege_escalation import _invite_and_accept

    token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, token, tenant_id)
    staff_token = await _invite_and_accept(client, token, tenant_id, "settingsstaff@example.com", "staff")

    resp = await client.patch(
        f"/api/v1/restaurants/{restaurant['id']}/settings", json={"theme_color": "#ffffff"}, headers=auth_headers(staff_token, tenant_id)
    )
    assert resp.status_code == 403


async def test_subscription_defaults_to_free_plan(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    resp = await client.get("/api/v1/subscription", headers=auth_headers(token, tenant_id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_code"] == "free"
    assert body["max_branches"] == 1


async def test_subscription_change_plan(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    resp = await client.post("/api/v1/subscription/change-plan", json={"plan_code": "pro"}, headers=auth_headers(token, tenant_id))
    assert resp.status_code == 200
    assert resp.json()["plan_code"] == "pro"
    assert resp.json()["max_branches"] == 5


async def test_subscription_change_to_unknown_plan_rejected(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    resp = await client.post("/api/v1/subscription/change-plan", json={"plan_code": "enterprise-deluxe"}, headers=auth_headers(token, tenant_id))
    assert resp.status_code == 422


async def test_audit_log_records_actions(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    await create_restaurant(client, token, tenant_id, "Audited Place")

    resp = await client.get("/api/v1/audit-logs", headers=auth_headers(token, tenant_id))
    assert resp.status_code == 200
    actions = [row["action"] for row in resp.json()["items"]]
    assert "restaurant.created" in actions
    assert "tenant.created" in actions


async def test_audit_log_never_contains_secrets(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    await create_restaurant(client, token, tenant_id)
    resp = await client.get("/api/v1/audit-logs", headers=auth_headers(token, tenant_id))
    raw_text = resp.text.lower()
    assert "password" not in raw_text
    assert "hashed_password" not in raw_text
    assert "token_hash" not in raw_text


async def test_audit_log_requires_permission(client, register_and_login):
    from tests.security.test_rbac_privilege_escalation import _invite_and_accept

    owner_token, tenant_id, _ = await register_and_login()
    editor_token = await _invite_and_accept(client, owner_token, tenant_id, "editoraudit@example.com", "editor")

    resp = await client.get("/api/v1/audit-logs", headers=auth_headers(editor_token, tenant_id))
    assert resp.status_code == 403
