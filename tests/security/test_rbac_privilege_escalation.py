import pytest

from tests.conftest import auth_headers
from tests.factories.helpers import create_restaurant

pytestmark = pytest.mark.asyncio


async def _invite_and_accept(client, owner_token, tenant_id, email, role):
    invite_resp = await client.post(
        "/api/v1/invitations", json={"email": email, "role": role}, headers=auth_headers(owner_token, tenant_id)
    )
    assert invite_resp.status_code == 201
    invite_email = next(m for m in client.sent_emails if m.to == email)
    token = invite_email.body.split("token=")[1].strip()

    accept_resp = await client.post(
        "/api/v1/invitations/accept",
        json={"token": token, "password": "AcceptPass123", "full_name": "Invited Person"},
    )
    assert accept_resp.status_code == 200
    return accept_resp.json()["access_token"]


async def test_staff_role_cannot_create_restaurant(client, register_and_login):
    owner_token, tenant_id, _ = await register_and_login()
    staff_token = await _invite_and_accept(client, owner_token, tenant_id, "staffer@example.com", "staff")

    resp = await client.post(
        "/api/v1/restaurants", json={"name": "Should Fail"}, headers=auth_headers(staff_token, tenant_id)
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_staff_role_can_read_restaurant(client, register_and_login):
    owner_token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, owner_token, tenant_id)
    staff_token = await _invite_and_accept(client, owner_token, tenant_id, "reader@example.com", "staff")

    resp = await client.get(f"/api/v1/restaurants/{restaurant['id']}", headers=auth_headers(staff_token, tenant_id))
    assert resp.status_code == 200


async def test_editor_can_edit_menu_but_not_manage_members(client, register_and_login):
    owner_token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, owner_token, tenant_id)
    menu_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus", json={"name": "M"}, headers=auth_headers(owner_token, tenant_id)
    )
    menu = menu_resp.json()

    editor_token = await _invite_and_accept(client, owner_token, tenant_id, "editor2@example.com", "editor")

    update_resp = await client.patch(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}",
        json={"name": "Updated by editor"},
        headers=auth_headers(editor_token, tenant_id),
    )
    assert update_resp.status_code == 200

    invite_resp = await client.post(
        "/api/v1/invitations",
        json={"email": "shouldnotwork@example.com", "role": "staff"},
        headers=auth_headers(editor_token, tenant_id),
    )
    assert invite_resp.status_code == 403


async def test_manager_cannot_publish_beyond_permission_but_editor_cannot_publish(client, register_and_login):
    owner_token, tenant_id, _ = await register_and_login()
    restaurant = await create_restaurant(client, owner_token, tenant_id)
    menu_resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus", json={"name": "M"}, headers=auth_headers(owner_token, tenant_id)
    )
    menu = menu_resp.json()
    editor_token = await _invite_and_accept(client, owner_token, tenant_id, "editornopublish@example.com", "editor")

    resp = await client.post(
        f"/api/v1/restaurants/{restaurant['id']}/menus/{menu['id']}/publish",
        headers=auth_headers(editor_token, tenant_id),
    )
    assert resp.status_code == 403


async def test_admin_cannot_promote_self_to_owner(client, register_and_login):
    owner_token, tenant_id, _ = await register_and_login()
    admin_token = await _invite_and_accept(client, owner_token, tenant_id, "adm@example.com", "admin")

    members_resp = await client.get("/api/v1/members", headers=auth_headers(owner_token, tenant_id))
    admin_membership = next(m for m in members_resp.json()["items"] if m["email"] == "adm@example.com")

    resp = await client.patch(
        f"/api/v1/members/{admin_membership['membership_id']}",
        json={"role": "owner"},
        headers=auth_headers(admin_token, tenant_id),
    )
    assert resp.status_code == 400  # BusinessRuleError: ownership transfer unsupported here


async def test_admin_cannot_promote_manager_to_admin_or_higher(client, register_and_login):
    """A non-owner actor cannot assign a role >= their own rank (privilege escalation guard)."""
    owner_token, tenant_id, _ = await register_and_login()
    admin_token = await _invite_and_accept(client, owner_token, tenant_id, "adm2@example.com", "admin")
    _manager_token = await _invite_and_accept(client, owner_token, tenant_id, "mgr@example.com", "manager")

    members_resp = await client.get("/api/v1/members", headers=auth_headers(owner_token, tenant_id))
    manager_membership = next(m for m in members_resp.json()["items"] if m["email"] == "mgr@example.com")

    resp = await client.patch(
        f"/api/v1/members/{manager_membership['membership_id']}",
        json={"role": "admin"},
        headers=auth_headers(admin_token, tenant_id),
    )
    assert resp.status_code == 403


async def test_owner_can_promote_manager_to_admin(client, register_and_login):
    owner_token, tenant_id, _ = await register_and_login()
    await _invite_and_accept(client, owner_token, tenant_id, "mgr2@example.com", "manager")

    members_resp = await client.get("/api/v1/members", headers=auth_headers(owner_token, tenant_id))
    manager_membership = next(m for m in members_resp.json()["items"] if m["email"] == "mgr2@example.com")

    resp = await client.patch(
        f"/api/v1/members/{manager_membership['membership_id']}",
        json={"role": "admin"},
        headers=auth_headers(owner_token, tenant_id),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


async def test_member_cannot_change_own_role(client, register_and_login):
    owner_token, tenant_id, _ = await register_and_login()
    me_resp = await client.get("/api/v1/members", headers=auth_headers(owner_token, tenant_id))
    owner_membership = me_resp.json()["items"][0]

    resp = await client.patch(
        f"/api/v1/members/{owner_membership['membership_id']}",
        json={"role": "admin"},
        headers=auth_headers(owner_token, tenant_id),
    )
    assert resp.status_code == 400


async def test_owner_membership_cannot_be_removed(client, register_and_login):
    owner_token, tenant_id, _ = await register_and_login()
    admin_token = await _invite_and_accept(client, owner_token, tenant_id, "adm3@example.com", "admin")

    members_resp = await client.get("/api/v1/members", headers=auth_headers(owner_token, tenant_id))
    owner_membership = next(m for m in members_resp.json()["items"] if m["role"] == "owner")

    resp = await client.delete(
        f"/api/v1/members/{owner_membership['membership_id']}", headers=auth_headers(admin_token, tenant_id)
    )
    assert resp.status_code == 400
