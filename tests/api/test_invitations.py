import pytest

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _get_token_for(client, to_email):
    invite_email = next(
        m
        for m in client.sent_emails
        if m.to == to_email and "been invited to join" in m.subject
    )
    return invite_email.body.split("token=")[1].strip()


async def test_create_invitation(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    resp = await client.post(
        "/api/v1/invitations", json={"email": "invitee@example.com", "role": "editor"}, headers=auth_headers(token, tenant_id)
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "invitee@example.com"
    assert body["status"] == "pending"
    assert "token" not in body
    assert "token_hash" not in body


async def test_duplicate_pending_invitation_rejected(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    await client.post("/api/v1/invitations", json={"email": "dup@example.com", "role": "staff"}, headers=auth_headers(token, tenant_id))
    resp = await client.post("/api/v1/invitations", json={"email": "dup@example.com", "role": "staff"}, headers=auth_headers(token, tenant_id))
    assert resp.status_code == 409


async def test_cannot_invite_as_owner(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    resp = await client.post("/api/v1/invitations", json={"email": "wannabe@example.com", "role": "owner"}, headers=auth_headers(token, tenant_id))
    assert resp.status_code == 400


async def test_accept_invitation_new_user(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    await client.post("/api/v1/invitations", json={"email": "newperson@example.com", "role": "staff"}, headers=auth_headers(token, tenant_id))
    invite_token = await _get_token_for(client, "newperson@example.com")

    resp = await client.post(
        "/api/v1/invitations/accept", json={"token": invite_token, "password": "NewPersonPass123", "full_name": "New Person"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]

    members_resp = await client.get("/api/v1/members", headers=auth_headers(token, tenant_id))
    emails = [m["email"] for m in members_resp.json()["items"]]
    assert "newperson@example.com" in emails


async def test_accept_invitation_existing_user_no_password_required(client, register_and_login):
    owner_token, tenant_id, _ = await register_and_login()
    existing_token, _existing_tenant, existing_email = await register_and_login()

    await client.post("/api/v1/invitations", json={"email": existing_email, "role": "manager"}, headers=auth_headers(owner_token, tenant_id))
    for i, m in enumerate(client.sent_emails):
        print(f"  [{i}] TO={m.to} SUBJECT={getattr(m, 'subject', None)!r} BODY={m.body!r}")

    invite_token = await _get_token_for(client, existing_email)

    resp = await client.post("/api/v1/invitations/accept", json={"token": invite_token})
    assert resp.status_code == 200


async def test_accept_invitation_twice_fails(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    await client.post("/api/v1/invitations", json={"email": "onceonly@example.com", "role": "staff"}, headers=auth_headers(token, tenant_id))
    invite_token = await _get_token_for(client, "onceonly@example.com")

    first = await client.post("/api/v1/invitations/accept", json={"token": invite_token, "password": "OnceOnlyPass123", "full_name": "Once"})
    assert first.status_code == 200

    second = await client.post("/api/v1/invitations/accept", json={"token": invite_token, "password": "OnceOnlyPass123", "full_name": "Once"})
    assert second.status_code == 422


async def test_accept_invitation_invalid_token(client):
    resp = await client.post("/api/v1/invitations/accept", json={"token": "not-a-real-token", "password": "Whatever123", "full_name": "X"})
    assert resp.status_code == 422


async def test_revoke_invitation(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    invite_resp = await client.post(
        "/api/v1/invitations", json={"email": "revokeme@example.com", "role": "staff"}, headers=auth_headers(token, tenant_id)
    )
    invitation_id = invite_resp.json()["id"]

    revoke_resp = await client.post(f"/api/v1/invitations/{invitation_id}/revoke", headers=auth_headers(token, tenant_id))
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"

    invite_token = await _get_token_for(client, "revokeme@example.com")
    accept_resp = await client.post(
        "/api/v1/invitations/accept", json={"token": invite_token, "password": "RevokedPass123", "full_name": "R"}
    )
    assert accept_resp.status_code == 422


async def test_resend_invitation_issues_new_token(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    invite_resp = await client.post(
        "/api/v1/invitations", json={"email": "resendme@example.com", "role": "staff"}, headers=auth_headers(token, tenant_id)
    )
    invitation_id = invite_resp.json()["id"]
    old_token = await _get_token_for(client, "resendme@example.com")

    resend_resp = await client.post(f"/api/v1/invitations/{invitation_id}/resend", headers=auth_headers(token, tenant_id))
    assert resend_resp.status_code == 200

    new_invite_emails = [m for m in client.sent_emails if m.to == "resendme@example.com"]
    new_token = new_invite_emails[-1].body.split("token=")[1].strip()
    assert new_token != old_token

    # Old token must no longer work.
    old_accept = await client.post(
        "/api/v1/invitations/accept", json={"token": old_token, "password": "ResendPass123", "full_name": "R"}
    )
    assert old_accept.status_code == 422

    new_accept = await client.post(
        "/api/v1/invitations/accept", json={"token": new_token, "password": "ResendPass123", "full_name": "R"}
    )
    assert new_accept.status_code == 200


async def test_only_pending_invitation_can_be_revoked(client, register_and_login):
    token, tenant_id, _ = await register_and_login()
    invite_resp = await client.post(
        "/api/v1/invitations", json={"email": "alreadyrevoked@example.com", "role": "staff"}, headers=auth_headers(token, tenant_id)
    )
    invitation_id = invite_resp.json()["id"]
    await client.post(f"/api/v1/invitations/{invitation_id}/revoke", headers=auth_headers(token, tenant_id))

    second_revoke = await client.post(f"/api/v1/invitations/{invitation_id}/revoke", headers=auth_headers(token, tenant_id))
    assert second_revoke.status_code == 400
